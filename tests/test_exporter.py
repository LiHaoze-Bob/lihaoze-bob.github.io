from pathlib import Path
import json
import pytest
from scripts.exporter import Exporter, ExportError


@pytest.fixture
def setup(tmp_path):
    vault=tmp_path/'vault'; source=vault/'课程'; source.mkdir(parents=True)
    template=tmp_path/'template'; template.mkdir(); (template/'base.yml').write_text('site_name: test\n')
    cfg={'site':{'name':'test','url':'https://example.com/notes-site/'},'sources':[{'path':'课程','destination':'courses'}]}
    def note(name,body,published=True,extra=''):
        p=source/name; p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('---\npublish: '+str(published).lower()+'\n'+extra+'---\n'+body)
        return p
    def export():
        destination=tmp_path/('output-'+str(len(list(tmp_path.glob('output-*')))))
        exporter=Exporter(vault,cfg,template)
        manifest=exporter.export(destination)
        return destination,manifest,exporter
    return source,note,export


def test_only_explicit_true_and_removal(setup):
    source,note,export=setup
    selected=note('公开.md','# 公开\n公开正文')
    note('私人.md','# 秘密\nPRIVATE_SENTINEL',False)
    (source/'旧标记.md').write_text('---\npublished: true\n---\nLEGACY_PRIVATE')
    output,manifest,_=export()
    assert len(manifest['notes'])==1
    assert 'PRIVATE_SENTINEL' not in ''.join(p.read_text() for p in output.rglob('*.md'))
    selected.write_text(selected.read_text().replace('publish: true','publish: false'))
    output,manifest,_=export()
    assert not manifest['notes']
    assert not (output/'courses/公开.md').exists()


def test_update_time_changes_only_when_public_content_changes(setup):
    source, note, export = setup
    selected = note('公开.md', '# 公开\n第一版')
    first_output, first, _ = export()
    first_record = first['notes'][0]
    assert 'updated_at' not in first_record

    unchanged_output = first_output.parent / 'unchanged'
    unchanged = Exporter(
        source.parent, {
            'site': {'name': 'test', 'url': 'https://example.com/notes-site/'},
            'sources': [{'path': '课程', 'destination': 'courses'}],
        }, first_output.parent / 'template'
    ).export(unchanged_output, {first_record['path']: first_record})
    assert 'updated_at' not in unchanged['notes'][0]

    selected.write_text(selected.read_text().replace('第一版', '第二版'))
    changed_output = first_output.parent / 'changed'
    changed = Exporter(
        source.parent, {
            'site': {'name': 'test', 'url': 'https://example.com/notes-site/'},
            'sources': [{'path': '课程', 'destination': 'courses'}],
        }, first_output.parent / 'template'
    ).export(changed_output, {first_record['path']: first_record})
    changed_record = changed['notes'][0]
    assert changed_record['published_at'] == first_record['published_at']
    assert changed_record['updated_at'] >= changed_record['published_at']
    assert changed_record['content_hash'] != first_record['content_hash']

    rebuilt_output = first_output.parent / 'rebuilt'
    rebuilt = Exporter(
        source.parent, {
            'site': {'name': 'test', 'url': 'https://example.com/notes-site/'},
            'sources': [{'path': '课程', 'destination': 'courses'}],
        }, first_output.parent / 'template'
    ).export(rebuilt_output, {changed_record['path']: changed_record})
    assert rebuilt['notes'][0]['updated_at'] == changed_record['updated_at']


def test_tech_and_reading_sources_are_grouped_under_their_tabs(tmp_path):
    vault = tmp_path / 'vault'
    files = {
        '技术积累/实践.md': '工程实践',
        'Tools/工具.md': '工具笔记',
        'Reading/书.md': '阅读笔记',
        'Paper/论文.md': '论文笔记',
    }
    for name, body in files.items():
        path = vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\npublish: true\n---\n' + body)
    cfg = {
        'site': {'name': 'test', 'url': 'https://example.com/notes-site/'},
        'sources': [
            {'path': '技术积累', 'destination': 'knowledge/tech'},
            {'path': 'Tools', 'destination': 'knowledge/tools'},
            {'path': 'Reading', 'destination': 'reading/reading'},
            {'path': 'Paper', 'destination': 'reading/paper'},
        ],
        'labels': {
            'knowledge': 'Tech',
            'knowledge/tech': '技术积累',
            'knowledge/tools': 'Tools',
            'reading': 'Reading',
            'reading/reading': 'Reading',
            'reading/paper': 'Paper',
        },
    }
    output = tmp_path / 'output'
    manifest = Exporter(vault, cfg, tmp_path / 'template').export(output)

    assert {note['path'] for note in manifest['notes']} == {
        'knowledge/tech/实践.md',
        'knowledge/tools/工具.md',
        'reading/reading/书.md',
        'reading/paper/论文.md',
    }
    assert (output / 'knowledge/index.md').read_text() == (
        '# Tech\n\n- [技术积累](tech/index.md)\n- [Tools](tools/index.md)\n'
    )
    assert (output / 'reading/index.md').read_text() == (
        '# Reading\n\n- [Reading](reading/index.md)\n- [Paper](paper/index.md)\n'
    )


def test_configured_empty_source_groups_keep_their_index_pages(tmp_path):
    vault = tmp_path / 'vault'
    for name in ['技术积累', 'Tools', 'Reading', 'Paper']:
        (vault / name).mkdir(parents=True)
    cfg = {
        'site': {'name': 'test', 'url': 'https://example.com/notes-site/'},
        'sources': [
            {'path': '技术积累', 'destination': 'knowledge/tech'},
            {'path': 'Tools', 'destination': 'knowledge/tools'},
            {'path': 'Reading', 'destination': 'reading/reading'},
            {'path': 'Paper', 'destination': 'reading/paper'},
        ],
        'labels': {
            'knowledge': 'Tech', 'knowledge/tech': '技术积累',
            'knowledge/tools': 'Tools', 'reading': 'Reading',
            'reading/reading': 'Reading', 'reading/paper': 'Paper',
        },
    }
    output = tmp_path / 'output'
    Exporter(vault, cfg, tmp_path / 'template').export(output)

    assert (output / 'knowledge/index.md').read_text() == (
        '# Tech\n\n- [技术积累](tech/index.md)\n- [Tools](tools/index.md)\n'
    )
    assert (output / 'reading/index.md').read_text() == (
        '# Reading\n\n- [Reading](reading/index.md)\n- [Paper](paper/index.md)\n'
    )
    for path in ['knowledge/tech', 'knowledge/tools', 'reading/reading', 'reading/paper']:
        assert '暂无公开笔记。' in (output / path / 'index.md').read_text()


def test_unicode_paths_images_and_same_names(setup):
    source,note,export=setup
    for folder,data in [('一',b'one'),('二',b'two')]:
        note(folder+'/文 档.md','# 标题\n![](图 片(1).png )')
        (source/folder/'图 片(1).png').write_bytes(data)
    output,manifest,_=export()
    assert len(manifest['images'])==2
    assert {p.read_bytes() for p in (output/'assets/notes').glob('*')}=={b'one',b'two'}


def test_wikilink_alias_heading_and_private_target(setup):
    _,note,export=setup
    note('公开.md','# 公开\n[[目标#中文标题|跳转]]\n[[私人|保留文字]]')
    note('目标.md','# 目标\n## 中文标题\n正文')
    note('私人.md','# 私人\nSECRET',False)
    output,_,exporter=export()
    page=(output/'courses/公开.md').read_text()
    assert '[跳转](%E7%9B%AE%E6%A0%87.md#%E4%B8%AD%E6%96%87%E6%A0%87%E9%A2%98)' in page
    assert '保留文字' in page and '[保留文字]' not in page
    assert '{#中文标题}' in (output/'courses/目标.md').read_text()
    assert len(exporter.warnings)==1


def test_protect_code_inline_math_and_nested_callout(setup):
    _,note,export=setup
    literal='```md\n[[不会转换]]\n![](missing.png)\n> [!tip] 原样\n```'
    note('示例.md','# 示例\n'+literal+'\n`[[不会转换]]`\n$$a_i = \\sum x_i$$\n> [!tip]+ 标题\n> 内容\n> > [!warning] 内层\n> > 文字\n> ```python\n> print("[[literal]]")\n> ```')
    output,_,_=export(); text=(output/'courses/示例.md').read_text()
    assert literal in text
    assert '`[[不会转换]]`' in text
    assert '$$a_i = \\sum x_i$$' in text
    assert '???+ tip "标题"' in text and '    !!! warning "内层"' in text
    assert '    print("[[literal]]")' in text


def test_tabsdown_converts_panel_content_and_keeps_nested_blocks(setup):
    source,note,export=setup
    (source/'图.png').write_bytes(b'image')
    note('目标.md', '# 目标\n## 小节\n正文')
    note('标签页.md', '''# 标签页

~~~~~tabsdown
config: position=top, layout=one, density=compact, personality=underline

tab: 概念
[[目标#小节|内部链接]]
![[图.png|240]]

tab: 例子
> [!tip] 提示
> 正文

~~~~tabsdown
tab: 内一
内容一
tab: 内二
内容二
~~~~
~~~~~
''')
    output,manifest,_=export()
    text=(output/'courses/标签页.md').read_text()
    assert text.count('tabsdown') == 2
    assert '[内部链接](%E7%9B%AE%E6%A0%87.md#%E5%B0%8F%E8%8A%82)' in text
    assert '![](../assets/notes/' in text and '{ width="240" }' in text
    assert '!!! tip "提示"' in text
    assert len(manifest['images']) == 1


def test_invalid_and_dynamic_tabsdown_content_blocks_export(setup):
    _,note,export=setup
    note('错误.md', '```tabsdown\ntab: 只有一个\n正文\n```')
    with pytest.raises(ExportError, match='Tabsdown.*至少需要两个'):
        export()
    note('错误.md', '````tabsdown\ntab: 一\n```dataview\nLIST\n```\ntab: 二\n正文\n````')
    with pytest.raises(ExportError, match='不支持动态内容'):
        export()


def test_custom_callout_types_and_manager_settings_are_preserved(setup):
    source,note,export=setup
    manager = source.parent / '.obsidian/plugins/callout-manager'
    manager.mkdir(parents=True)
    manager.joinpath('data.json').write_text(json.dumps({'callouts': {
        'custom': ['intro', 'theorem'],
        'settings': {
            'intro': [{'changes': {'icon': 'lucide-anchor'}},
                      {'condition': {'colorScheme': 'dark'}, 'changes': {'color': '83, 223, 221'}}],
        },
    }}))
    note('自定义.md', '# 自定义\n> [!intro]\n> 导言\n\n普通正文\n\n> [!word]\n> 单词')
    output,manifest,_=export()
    text=(output/'courses/自定义.md').read_text()
    assert '!!! intro' in text and '!!! word' in text
    assert '!!! note' not in text
    assert manifest['callouts']['intro'] == {'icon': 'lucide-anchor', 'dark_color': '83, 223, 221'}
    assert manifest['callouts']['theorem'] == {}


@pytest.mark.parametrize('body,error',[
    ('![](missing.png)','找不到图片'),
    ('[[不存在]]','找不到链接目标'),
    ('![[私人]]','暂不支持笔记'),
    ('```dataview\nLIST\n```','不支持动态内容'),
    ('[本机](file:///Users/user/private.md)','不支持本地资源'),
])
def test_errors_block_export(setup,body,error):
    _,note,export=setup; note('公开.md','# 公开\n'+body)
    with pytest.raises(ExportError,match=error): export()


def test_ambiguous_link_does_not_pick_first(setup):
    _,note,export=setup
    note('主.md','[[同名]]'); note('甲/同名.md','# A'); note('乙/同名.md','# B')
    with pytest.raises(ExportError,match='多个匹配'): export()


def test_outside_scope_and_symlink_attachment(setup,tmp_path):
    source,note,export=setup
    secret=tmp_path/'secret.png'; secret.write_bytes(b'SECRET')
    (source/'linked.png').symlink_to(secret)
    note('主.md','![](linked.png)')
    with pytest.raises(ExportError,match='超出配置目录'): export()


def test_image_embed_dimensions_and_markdown_reference(setup):
    source,note,export=setup
    note('主.md','![[a.png|240]]\n![说明][image]\n\n[image]: a.png')
    (source/'a.png').write_bytes(b'image')
    output,manifest,_=export()
    text=(output/'courses/主.md').read_text()
    assert '{ width="240" }' in text
    assert '![说明](../assets/notes/' in text
    assert len(manifest['images'])==1


def test_private_reference_links_and_unused_images(setup):
    _,note,export=setup
    note('公开.md','# 公开\n[保留文字][private]\n[私人][]\n[私人]\n`[保留文字][private]`\n\n[private]: 私人.md\n[私人]: 私人.md\n[unused]: missing.png')
    note('私人.md','SECRET',False)
    output,manifest,exporter=export()
    text=(output/'courses/公开.md').read_text()
    assert '保留文字\n私人\n私人' in text
    assert '`[保留文字][private]`' in text
    assert '私人.md' not in text and 'missing.png' not in text
    assert len(exporter.warnings)==3 and not manifest['images']


def test_bad_publish_and_empty_notes(setup):
    source,note,export=setup
    note('空.md','')
    with pytest.raises(ExportError,match='没有正文'): export()
    (source/'空.md').write_text('---\npublish: "true"\n---\n正文')
    with pytest.raises(ExportError,match='只能是'): export()


def test_multiline_inline_and_quoted_display_math_render(setup):
    import markdown
    _,note,export=setup
    note('公式.md','# 公式\n中文$x +\ny$中文\n\n> [!tip] 公式\n> $$\n> P=\\frac{K-1}{2}\n> $$\n> 结束')
    output,_,_=export()
    text=(output/'courses/公式.md').read_text()
    _,body=__import__('scripts.exporter',fromlist=['frontmatter']).frontmatter(text)
    html=markdown.markdown(body,extensions=['admonition','pymdownx.arithmatex'],extension_configs={'pymdownx.arithmatex':{'generic':True,'smart_dollar':False}})
    assert html.count('class="arithmatex"')==2
    assert '$$' not in html
    assert '\\frac{K-1}{2}' in html


def test_callout_with_leading_spaces_is_not_literal(setup):
    import markdown
    _,note,export=setup
    note('空格.md','# 空格\n > [! note]\n > 正文')
    output,_,_=export()
    text=(output/'courses/空格.md').read_text()
    rendered=markdown.markdown(text,extensions=['admonition'])
    assert 'class="admonition note"' in rendered
    assert '!!! note' not in rendered


@pytest.mark.parametrize('reverse_sources', [False, True])
def test_vault_mapping_preserves_nested_urls_without_duplicates_or_private_content(tmp_path, reverse_sources):
    import tomllib

    config = tomllib.loads((Path(__file__).resolve().parents[1] / 'publish.toml').read_text())
    if reverse_sources:
        config['sources'].reverse()
    vault = tmp_path / 'vault'
    for source in config['sources']:
        (vault / source['path']).mkdir(parents=True, exist_ok=True)
    public = {
        '30_Courses/CS/Lecture.md': '[[30_Courses/Archive/FDS/Graph]]',
        '30_Courses/Archive/FDS/Graph.md': 'Archived course note',
        '50_Blog/Archive/Notes/Practice.md': '[[Tool]]',
        '50_Blog/Archive/Tools/Tool.md': '[[Practice]]',
        '50_Blog/Archive/Thought.md': '[[Practice]] [[Tool]] [[Private]]',
        '50_Blog/Archive/Experiments/Result.md': 'Experiment result',
        '40_Reading/Books/Book.md': 'Book note',
        '40_Reading/Papers/Paper.md': 'Paper note',
        '40_Reading/Articles/Article.md': 'Article reflection',
        '40_Reading/News/News.md': 'EXCLUDED_NEWS_SENTINEL',
        '50_Blog/In Progress.md': 'ROOT_DRAFT_SENTINEL',
    }
    for name, body in public.items():
        path = vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\npublish: true\n---\n' + body)
    (vault / '50_Blog/Archive/Private.md').write_text('---\npublish: false\n---\nPRIVATE_SENTINEL')
    (vault / '50_Blog/Archive/Draft.md').write_text('UNMARKED_SENTINEL')
    output = tmp_path / 'output'
    exporter = Exporter(vault, config, tmp_path / 'template')
    manifest = exporter.export(output)

    paths = [note['path'] for note in manifest['notes']]
    assert len(paths) == 9
    assert set(paths) == {
        'courses/CS/Lecture.md', 'courses/FDS/Graph.md',
        'knowledge/tech/Practice.md', 'knowledge/tools/Tool.md',
        'knowledge/Thought.md', 'knowledge/Experiments/Result.md',
        'reading/reading/Book.md', 'reading/paper/Paper.md',
        'reading/articles/Article.md',
    }
    assert len(exporter.notes) == len({note.source for note in exporter.notes})
    assert '[30_Courses/Archive/FDS/Graph](../FDS/Graph.md)' in (output / 'courses/CS/Lecture.md').read_text()
    assert '[Tool](../tools/Tool.md)' in (output / 'knowledge/tech/Practice.md').read_text()
    thought = (output / 'knowledge/Thought.md').read_text()
    assert '[Practice](tech/Practice.md)' in thought
    assert '[Tool](tools/Tool.md)' in thought
    assert '[Private]' not in thought
    exported = ''.join(path.read_text() for path in output.rglob('*.md'))
    for sentinel in ['PRIVATE_SENTINEL', 'UNMARKED_SENTINEL', 'EXCLUDED_NEWS_SENTINEL', 'ROOT_DRAFT_SENTINEL']:
        assert sentinel not in exported
