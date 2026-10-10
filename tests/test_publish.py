import json
import subprocess

import pytest

import scripts.site as site


@pytest.fixture
def repository(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, check=True,
                              capture_output=True, text=True).stdout

    git('init', '-b', 'main')
    git('config', 'user.name', 'Publish Test')
    git('config', 'user.email', 'publish@example.test')
    git('config', 'commit.gpgsign', 'false')
    git('config', 'core.hooksPath', '/dev/null')
    monkeypatch.setattr(site, 'ROOT', tmp_path)

    def snapshot(notes, commit=False):
        docs = tmp_path / 'docs'
        docs.mkdir(exist_ok=True)
        for path in docs.rglob('*.md'):
            path.unlink()
        records = []
        for path, title, body in notes:
            target = docs / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)
            records.append({'path': path, 'title': title})
        (docs / 'publication.json').write_text(json.dumps({'notes': records}))
        git('add', '-A', '--', 'docs')
        if commit:
            git('commit', '-m', 'Initial snapshot')

    return tmp_path, git, snapshot


@pytest.mark.parametrize(('before', 'after', 'expected'), [
    ([], [('courses/高斯 定理.md', '高斯定理', 'new')],
     'feat: add 「高斯定理」'),
    ([('courses/a.md', '旧标题', 'old')], [('courses/a.md', '新标题', 'new')],
     'docs: update 「新标题」'),
    ([('courses/a.md', '高斯定理', 'old')], [],
     'docs: remove 「高斯定理」'),
    ([(f'courses/{i}.md', str(i), 'old') for i in range(3)],
     [(f'courses/{i}.md', str(i), 'new') for i in range(5)],
     'docs: add 2 notes, update 3 notes'),
    ([('a.md', 'A', 'old'), ('b.md', 'B', 'old')],
     [('b.md', 'B', 'new'), ('c.md', 'C', 'new')],
     'docs: add 1 note, update 1 note, remove 1 note'),
    ([], [('courses/含\n换行.md', ' 多行\n 标题 ', 'new')],
     'feat: add 「多行 标题」'),
])
def test_commit_message_describes_staged_note_changes(repository, before, after, expected):
    _, _, snapshot = repository
    snapshot(before, commit=True)
    snapshot(after)
    assert site.publication_commit_message() == expected


def test_commit_message_uses_index_instead_of_unstaged_files(repository):
    root, _, snapshot = repository
    snapshot([], commit=True)
    snapshot([('a.md', '已暂存标题', 'new')])
    (root / 'docs/publication.json').write_text(json.dumps({
        'notes': [{'path': 'a.md', 'title': '未暂存标题'}]
    }))
    assert site.publication_commit_message() == 'feat: add 「已暂存标题」'


def test_asset_change_does_not_count_unchanged_notes(repository):
    root, git, snapshot = repository
    snapshot([('a.md', 'A', 'unchanged')], commit=True)
    (root / 'docs/image.png').write_bytes(b'changed image')
    git('add', '--', 'docs/image.png')
    assert site.publication_commit_message() == 'docs: update public snapshot'


def test_first_manifest_is_supported(repository):
    root, git, snapshot = repository
    (root / 'README.md').write_text('Site')
    git('add', 'README.md')
    git('commit', '-m', 'Initialize site')
    snapshot([('a.md', '', 'new')])
    assert site.publication_commit_message() == 'feat: add 「a」'


@pytest.mark.parametrize('changed', [True, False])
def test_publish_commits_generated_message_only_when_content_changes(repository, monkeypatch, changed):
    root, git, snapshot = repository
    (root / '.gitignore').write_text('local.toml\n')
    git('add', '.gitignore')
    snapshot([], commit=True)
    original_commit = git('rev-parse', 'HEAD')
    (root / 'local.toml').write_text('vault = "unused"\n')
    git('remote', 'add', 'origin', 'https://github.com/example/site.git')
    original_run = site.run
    pushed = []
    deployed = []

    def local_run(*args, **kwargs):
        if args[:2] == ('git', 'push'):
            pushed.append(args)
            return ''
        kwargs['cwd'] = root
        return original_run(*args, **kwargs)

    monkeypatch.setattr(site, 'run', local_run)
    monkeypatch.setattr(site, 'config', lambda: {
        'site': {'branch': 'main', 'repository': 'example/site'}
    })
    monkeypatch.setattr(site, 'status', lambda *args, **kwargs: None)
    monkeypatch.setattr(site, 'prepare', lambda **kwargs: snapshot(
        [('a.md', '高斯定理', 'new')] if changed else []
    ))
    monkeypatch.setattr(site, 'await_deployment', deployed.append)

    site.publish()

    head = git('rev-parse', 'HEAD')
    if changed:
        assert head != original_commit
        assert git('log', '-1', '--format=%s').strip() == 'feat: add 「高斯定理」'
    else:
        assert head == original_commit
    assert pushed == [('git', 'push', 'origin', 'main')]
    assert deployed == [head.strip()]
