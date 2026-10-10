#!/usr/bin/env python3
"""检查、预览并发布网站；GitHub Actions 仅构建已导出的公开内容。"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen
import webbrowser
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.exporter import Exporter, ExportError
from scripts.jekyll import stage as stage_jekyll
from scripts.astro import stage as stage_astro

RUNTIME = ROOT / '.runtime'
STATUS = RUNTIME / 'status.json'
ENV = dict(os.environ)
ENV['PATH'] = ENV.get('PATH', '') + ':/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
# Obsidian does not inherit the interactive shell's Ruby PATH.
for ruby_bin in ('/usr/local/opt/ruby@3.3/bin', '/opt/homebrew/opt/ruby@3.3/bin'):
    if Path(ruby_bin, 'ruby').exists():
        ENV['PATH'] = ruby_bin + ':' + ENV.get('PATH', '')
        break
ENV['BUNDLE_GEMFILE'] = str(ROOT / 'Gemfile')
ENV.setdefault('BUNDLE_PATH', str(RUNTIME / 'bundle'))
ENV['JEKYLL_ENV'] = 'production'
ENV['ASTRO_TELEMETRY_DISABLED'] = '1'


def config():
    return tomllib.loads((ROOT / 'publish.toml').read_text())


def status(phase, **values):
    current = {}
    if STATUS.exists():
        current = json.loads(STATUS.read_text())
    current.update(phase=phase, updated_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'), **values)
    RUNTIME.mkdir(exist_ok=True)
    temp = STATUS.with_suffix('.tmp')
    temp.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n')
    temp.replace(STATUS)
    print(phase, flush=True)


def run(*args, capture=False, timeout=180, cwd=ROOT, env=None):
    result = subprocess.run(args, cwd=cwd, env=env or ENV, text=True, stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None, timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout or '').strip() if capture else ''
        raise ExportError(f'命令失败（{args[0]}，退出码 {result.returncode}）' + (f'：{detail}' if detail else ''))
    return result.stdout.rstrip('\n') if capture else ''


def validate(site: Path):
    site = site.resolve()
    prefix = urlsplit(config()['site']['url']).path.rstrip('/')
    errors = []
    soups = {}
    for page in site.rglob('*.html'):
        soups[page] = BeautifulSoup(page.read_text(), 'html.parser')
    if not (site / 'index.html').exists():
        raise ExportError('构建结果缺少首页')
    for page, soup in soups.items():
        for element in soup.select('a[href], img[src], script[src], link[href]'):
            attr = 'src' if element.name in {'img', 'script'} else 'href'
            target = element.get(attr, '')
            parsed = urlsplit(target)
            if parsed.scheme in {'http', 'https', 'mailto', 'tel', 'data'} or target.startswith('//'):
                continue
            if parsed.scheme:
                errors.append(f'{page.relative_to(site)}：不支持的资源地址 {target}')
                continue
            path = unquote(parsed.path)
            if path.startswith('/'):
                if prefix and path.startswith(prefix + '/'):
                    path = path[len(prefix)+1:]
                elif prefix and path != prefix:
                    errors.append(f'绕过项目路径的链接：{target}')
                    continue
                else:
                    path = path.lstrip('/')
                destination = site / path
            elif not path:
                destination = page
            else:
                destination = page.parent / path
            destination = destination.resolve()
            if not destination.is_relative_to(site):
                errors.append(f'链接超出网站：{target}')
                continue
            if destination.is_dir():
                destination /= 'index.html'
            if not destination.exists():
                errors.append(f'{page.relative_to(site)}：缺失资源 {target}')
            elif path.endswith('/') and destination.is_file() and destination.name != 'index.html':
                errors.append(f'{page.relative_to(site)}：文件链接不能以斜杠结尾 {target}')
            elif parsed.fragment and element.name == 'a' and destination.suffix == '.html':
                linked_soup = soups.get(destination)
                if linked_soup and not linked_soup.find(id=unquote(parsed.fragment)):
                    errors.append(f'{page.relative_to(site)}：标题锚点不存在 {target}')
    if errors:
        raise ExportError('\n'.join(errors[:30]))
    return len(soups)


def publication_dates():
    """Reuse saved first-publication dates, bootstrapping old notes from Git."""
    return {path: record['published_at'] for path, record in publication_records().items()}


def publication_records():
    """Reuse publication/update state and bootstrap legacy manifests from Git."""
    manifest_path = ROOT / 'docs/publication.json'
    if not manifest_path.exists():
        return {}
    records = {}
    for note in json.loads(manifest_path.read_text())['notes']:
        path = note['path']
        history = run('git', 'log', '--format=%cI', '--', 'docs/' + path,
                      capture=True).splitlines()
        published_at = note.get('published_at') or (history[-1] if history else None)
        if not published_at:
            continue
        record = {'published_at': published_at}
        updated_at = note.get('updated_at')
        # Older manifests did not store update times. Multiple commits touching
        # the public note provide a reliable one-time migration source.
        if not updated_at and len(history) > 1:
            updated_at = history[0]
        if updated_at:
            record['updated_at'] = updated_at
        content_hash = note.get('content_hash')
        snapshot = ROOT / 'docs' / path
        if not content_hash and snapshot.is_file():
            content_hash = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        if content_hash:
            record['content_hash'] = content_hash
        records[path] = record
    return records


def build_snapshot(docs: Path, work: Path, theme: str | None = None):
    settings = yaml.safe_load((ROOT / '_config.yml').read_text())
    if settings['url'] + settings.get('baseurl', '') + '/' != config()['site']['url']:
        raise ExportError('_config.yml 中的网址必须与 publish.toml 一致')
    theme = theme or config()['site'].get('theme', 'chirpy')
    if theme == 'pure':
        work.mkdir(parents=True, exist_ok=True)
        data = stage_astro(docs, work, ROOT / 'site-template', settings, config().get('labels', {}))
        npm = shutil.which('npm', path=ENV.get('PATH'))
        if not npm or not (ROOT / 'node_modules/astro').exists():
            raise ExportError('请安装 Node.js 22.12+ 并在网站目录执行 npm ci（见 README）')
        env = {**ENV, 'ASTRO_CONTENT_FILE': str(data.resolve()),
               'ASTRO_PUBLIC_DIR': str((work / 'public').resolve()),
               'ASTRO_OUT_DIR': str((work / 'site').resolve())}
        run(npm, 'run', 'build', env=env, timeout=300)
        return validate(work / 'site')
    if theme != 'chirpy':
        raise ExportError('未知主题：' + theme)
    stage_jekyll(docs, work / 'source', ROOT / 'site-template', settings, config().get('labels', {}))
    bundle = shutil.which('bundle', path=ENV.get('PATH'))
    if not bundle:
        raise ExportError('找不到 bundle，请先安装 Ruby 3.3 和 Gemfile 中的依赖（见 README）')
    run(bundle, 'exec', 'jekyll', 'build', '--source', str(work / 'source'),
        '--destination', str(work / 'site'))
    return validate(work / 'site')


def install_snapshot(source: Path):
    if (ROOT / 'site').exists():
        shutil.rmtree(ROOT / 'site')
    shutil.move(str(source), ROOT / 'site')


def build(theme=None):
    """CI builds the committed public snapshot, without local.toml or the Vault."""
    RUNTIME.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='site-', dir=RUNTIME) as temporary:
        work = Path(temporary)
        pages = build_snapshot(ROOT / 'docs', work, theme)
        install_snapshot(work / 'site')
    print(f'网站构建与链接校验通过：{pages} 个页面。', flush=True)


def prepare(write_export=False, theme=None):
    if not (ROOT / 'local.toml').exists():
        raise ExportError('请先将 local.example.toml 复制为 local.toml 并设置 vault 路径')
    local = tomllib.loads((ROOT / 'local.toml').read_text())
    RUNTIME.mkdir(exist_ok=True)
    status('正在导出并检查笔记')
    with tempfile.TemporaryDirectory(prefix='build-', dir=RUNTIME) as temporary:
        stage = Path(temporary)
        exporter = Exporter(Path(local['vault']), config(), ROOT / 'site-template')
        manifest = exporter.export(stage / 'docs', publication_records())
        status('正在构建网站', notes=len(manifest['notes']), images=len(manifest['images']))
        pages = build_snapshot(stage / 'docs', stage, theme)
        # 所有检查通过后才替换站点快照，失败不会影响已有导出或线上页面。
        install_snapshot(stage / 'site')
        if write_export:
            if (ROOT / 'docs').is_symlink():
                raise ExportError('docs 不能是符号链接')
            if (ROOT / 'docs').exists():
                shutil.rmtree(ROOT / 'docs')
            shutil.move(str(stage / 'docs'), ROOT / 'docs')
        for warning in exporter.warnings:
            print('提示：' + warning, flush=True)
        print(f'检查通过：{len(manifest["notes"])} 篇笔记、{len(manifest["images"])} 张图片、{pages} 个页面。', flush=True)
        return manifest


def preview(theme=None):
    prepare(theme=theme)
    preview_root = RUNTIME / 'preview'
    preview_root.mkdir(exist_ok=True)
    target = preview_root / 'notes-site'
    if not target.exists():
        target.symlink_to(ROOT / 'site', target_is_directory=True)
    url = 'http://127.0.0.1:8765/notes-site/'
    try:
        with urlopen(url + 'publication.json', timeout=2) as response:
            json.loads(response.read())
    except Exception:
        log = (RUNTIME / 'preview.log').open('a')
        process = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '--bind', '127.0.0.1', '--directory', str(preview_root)],
                                   cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, env=ENV)
        log.close()
        (RUNTIME / 'preview.pid').write_text(str(process.pid))
        for _ in range(20):
            if process.poll() is not None:
                raise ExportError('无法启动预览；请检查 8765 端口及 .runtime/preview.log')
            try:
                with urlopen(url + 'publication.json', timeout=1):
                    break
            except Exception:
                time.sleep(.25)
        else:
            raise ExportError('预览启动超时')
    status('预览已就绪', url=url)
    webbrowser.open(url)


def gh_json(*arguments):
    return json.loads(run('gh', *arguments, capture=True))


def await_deployment(commit):
    repo = config()['site']['repository']
    status('已推送，正在等待 GitHub Pages 部署', commit=commit)
    deadline = time.monotonic() + 900
    last_phase = None
    while time.monotonic() < deadline:
        data = gh_json('api', f'repos/{repo}/actions/workflows/pages.yml/runs?head_sha={commit}&per_page=5')
        runs = data.get('workflow_runs', [])
        if runs:
            latest = runs[0]
            phase = latest['status']
            if phase != last_phase:
                status('GitHub Actions：' + phase, workflow_url=latest['html_url'], run_id=latest['id'])
                last_phase = phase
            if phase == 'completed':
                if latest['conclusion'] != 'success':
                    raise ExportError('部署失败：' + latest['html_url'])
                status('已上线', commit=commit, url=config()['site']['url'], workflow_url=latest['html_url'])
                return
        time.sleep(8)
    raise ExportError('等待部署超时，请在仓库 Actions 查看该提交的结果；无需再次修改笔记')


def publication_commit_message():
    """Describe the public notes in the staged snapshot relative to HEAD."""
    manifest_path = 'docs/publication.json'
    previous = {}
    if run('git', 'ls-tree', '--name-only', 'HEAD', '--', manifest_path,
           capture=True, cwd=ROOT):
        manifest = json.loads(run('git', 'show', 'HEAD:' + manifest_path,
                                  capture=True, cwd=ROOT))
        previous = {note['path']: note for note in manifest['notes']}
    manifest = json.loads(run('git', 'show', ':' + manifest_path,
                              capture=True, cwd=ROOT))
    current = {note['path']: note for note in manifest['notes']}
    changed = set(run('git', 'diff', '--cached', '--name-only', '--no-renames',
                      '-z', '--', 'docs', capture=True, cwd=ROOT).split('\0'))
    added = current.keys() - previous.keys()
    removed = previous.keys() - current.keys()
    updated = {path for path in current.keys() & previous.keys()
               if 'docs/' + path in changed}
    groups = [('add', added, current), ('update', updated, current),
              ('remove', removed, previous)]
    if sum(len(paths) for _, paths, _ in groups) == 1:
        for verb, paths, notes in groups:
            if paths:
                path = next(iter(paths))
                title = ' '.join(str(notes[path].get('title') or '').split()) or Path(path).stem
                prefix = 'feat' if verb == 'add' else 'docs'
                return f'{prefix}: {verb} 「{title}」'
    summary = ', '.join(f'{verb} {len(paths)} note' + ('s' if len(paths) != 1 else '')
                        for verb, paths, _ in groups if paths)
    return 'docs: ' + (summary or 'update public snapshot')


def publish():
    settings = config()['site']
    local = tomllib.loads((ROOT / 'local.toml').read_text())
    proxy = local.get('proxy')
    if proxy:
        for key in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
            ENV[key] = proxy
    branch = run('git', 'branch', '--show-current', capture=True)
    origin = run('git', 'remote', 'get-url', 'origin', capture=True)
    expected = settings['repository']
    if branch != settings['branch'] or origin.removesuffix('.git') not in {'https://github.com/' + expected, 'git@github.com:' + expected, 'ssh://git@ssh.github.com:443/' + expected}:
        raise ExportError('当前分支或 origin 与发布配置不一致，停止推送')
    # 只允许自动提交公开快照。其他源码变更交给明确的开发提交。
    changes = run('git', 'status', '--porcelain=v1', '-z', capture=True)
    for record in changes.split('\0'):
        if not record:
            continue
        path = record[3:] if len(record) >= 3 else record
        if not path.startswith('docs/'):
            raise ExportError('网站源码有未提交修改，请先处理后再发布：' + path)
    prepare(write_export=True)
    run('git', 'add', '-A', '--', 'docs')
    diff = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT)
    if diff.returncode == 1:
        run('git', 'commit', '-m', publication_commit_message())
    elif diff.returncode != 0:
        raise ExportError('无法检查待提交内容')
    else:
        print('公开内容没有变化，将检查当前提交的部署状态。', flush=True)
    status('正在推送到 GitHub')
    output = run('git', 'push', 'origin', settings['branch'], capture=True, timeout=180)
    if output:
        print(output, flush=True)
    commit = run('git', 'rev-parse', 'HEAD', capture=True)
    await_deployment(commit)


def main():
    parser = argparse.ArgumentParser(description='sychostar 笔记网站发布工具')
    parser.add_argument('command', choices=['check', 'preview', 'publish', 'build', 'validate'])
    parser.add_argument('--theme', choices=['pure', 'chirpy'], help='临时选择主题，不修改笔记或默认设置')
    parser.add_argument('--from-obsidian', action='store_true')
    args = parser.parse_args()
    if args.theme and args.command not in {'check', 'build', 'preview'}:
        parser.error('--theme 仅适用于 check、build 和 preview；上线主题由 publish.toml 决定')
    if args.command == 'validate':
        print(f'构建结果校验通过：{validate(ROOT / "site")} 个页面。')
        return
    RUNTIME.mkdir(exist_ok=True)
    with (RUNTIME / 'publish.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ExportError('已有检查、预览或发布任务正在运行，请等待它完成')
        status('开始：' + args.command, command=args.command, origin='obsidian' if args.from_obsidian else 'terminal', error=None)
        if args.command == 'check':
            prepare(theme=args.theme)
            status('检查通过')
        elif args.command == 'build':
            build(theme=args.theme)
            status('构建通过')
        elif args.command == 'preview':
            preview(theme=args.theme)
        else:
            publish()


if __name__ == '__main__':
    try:
        main()
    except (ExportError, OSError, subprocess.SubprocessError, ValueError) as exc:
        status('未完成', error=str(exc))
        print(str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
