import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup
import pytest
import yaml

from scripts.exporter import Exporter, ExportError, convert_callouts, frontmatter
from scripts.jekyll import (card_headings, card_directory, custom_callout_styles,
                            folder_tree, render, section_list, stage, post_date)

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_publication_state_is_bootstrapped_from_snapshot_and_git(tmp_path, monkeypatch):
    import scripts.site as site

    note = tmp_path / 'docs/courses/示例.md'
    note.parent.mkdir(parents=True)
    note.write_text('公开快照')
    (tmp_path / 'docs/publication.json').write_text(json.dumps({
        'notes': [{'path': 'courses/示例.md', 'title': '示例'}]
    }))
    monkeypatch.setattr(site, 'ROOT', tmp_path)
    monkeypatch.setattr(site, 'run', lambda *args, **kwargs: (
        '2026-09-16T09:45:00+08:00\n2026-09-14T12:30:00+08:00'
    ))

    record = site.publication_records()['courses/示例.md']
    assert record['published_at'] == '2026-09-14T12:30:00+08:00'
    assert record['updated_at'] == '2026-09-16T09:45:00+08:00'
    assert record['content_hash'] == hashlib.sha256(note.read_bytes()).hexdigest()


def test_render_preserves_code_math_and_chinese_links():
    body = '''# 标题 {#标题}

[下一篇](%E4%B8%8B%E4%B8%80%E7%AF%87.md#小节)
![图片](../../assets/notes/image.png){ width="240" }

!!! warning "注意"
    中文$x^2$，**保留强调**。

???+ tip "展开"
    $$x=1$$

```python
print("{{ site.title }}")
```
'''
    output = render(body, 'courses/课程/示例.md', '/notes-site', '标题')
    soup = BeautifulSoup(output, 'html.parser')
    assert not soup.h1 and soup.find(id='标题')
    assert soup.a['href'] == '/notes-site/courses/%E8%AF%BE%E7%A8%8B/%E4%B8%8B%E4%B8%80%E7%AF%87/#小节'
    assert soup.img['src'] == '/assets/notes/image.png' and soup.img['width'] == '240'
    assert 'width="240" />' in output
    assert soup.select_one('div.obsidian-callout[data-callout="warning"] > .callout-title')
    assert soup.select_one('details.obsidian-callout[data-callout="tip"][open] > summary').get_text() == '展开'
    assert len(soup.select('.arithmatex')) == 2
    assert soup.select_one('.language-python .rouge-code').get_text().strip() == 'print("{{ site.title }}")'
    assert soup.select_one('.language-python .nb').get_text() == 'print'


def test_a_different_body_heading_is_not_deleted():
    output = render('# 正文小节', 'reading/一.md', '', '文章标题')
    assert '<h1' in output and '正文小节' in output


def test_render_strikethrough_without_changing_code_or_escaped_tildes():
    body = '~~划分策略~~，前~~字~~后，`~~代码~~`，\\~~原样\\~~'
    soup = BeautifulSoup(render(body, 'courses/示例.md', ''), 'html.parser')
    assert [item.get_text() for item in soup.find_all('del')] == ['划分策略', '字']
    assert soup.code.get_text() == '~~代码~~'
    assert '~~原样~~' in soup.get_text()


@pytest.mark.parametrize('theme', ['pure', 'chirpy'])
def test_render_obsidian_highlights_preserving_formatting_and_literal_examples(theme):
    body = r'''==中文高亮==，前==重点==后，==**强调**与$x^2$==。

`==行内代码==`，\==原样\==，未闭合==文字。

```text
==代码块==
```

!!! note "提示"
    ==提示高亮==

```tabsdown
tab: 一
==面板高亮==
tab: 二
普通正文。
```
'''
    soup = BeautifulSoup(render(body, 'courses/示例.md', '', theme=theme), 'html.parser')
    marks = soup.find_all('mark')
    assert [item.get_text() for item in marks] == [
        '中文高亮', '重点', '强调与\\(x^2\\)', '提示高亮', '面板高亮']
    assert marks[2].strong.get_text() == '强调'
    assert marks[2].select_one('.arithmatex').get_text() == '\\(x^2\\)'
    assert soup.select_one('p code').get_text() == '==行内代码=='
    code_block = soup.select_one('.note-code pre code, .rouge-code pre')
    assert code_block.get_text().strip() == '==代码块=='
    assert '==原样==' in soup.get_text()
    assert '未闭合==文字' in soup.get_text()


def test_obsidian_single_newlines_render_inside_text_blocks_only():
    body = '''第一行
第二行

- 列表一
- 列表二

!!! note "提示"
    提示第一行
    提示第二行

```text
代码第一行
代码第二行
```'''
    soup = BeautifulSoup(render(body, 'courses/示例.md', ''), 'html.parser')
    paragraph = soup.find('p')
    assert list(paragraph.stripped_strings) == ['第一行', '第二行']
    assert len(paragraph.find_all('br')) == 1
    assert [item.get_text() for item in soup.select('ul > li')] == ['列表一', '列表二']
    prompt = soup.select_one('.obsidian-callout p:not(.callout-title)')
    assert list(prompt.stripped_strings) == ['提示第一行', '提示第二行']
    assert len(prompt.find_all('br')) == 1
    assert soup.select_one('.rouge-code').get_text() == '代码第一行\n代码第二行\n'
    assert not soup.select_one('.rouge-code br')


def test_render_tabsdown_is_accessible_nested_and_has_no_js_fallback():
    body = '''~~~~~tabsdown
config: position=left, layout=multi, density=compact, personality=underline, palette=secondary, alignment=equal-width

tab: **概念**
## 小节
正文

tab: 例子 <script>
~~~~tabsdown
tab: 内一
内容一
tab: 内二
内容二
~~~~
~~~~~'''
    output = render(body, 'courses/标签页.md', '/notes-site')
    soup = BeautifulSoup(output, 'html.parser')
    outer = soup.select_one('.tabsdown-site--left.tabsdown-site--multi.tabsdown-site--compact.tabsdown-site--underline.tabsdown-site--secondary.tabsdown-site--equal-width')
    assert outer
    assert len(outer.select(':scope > .tabsdown-site__tablist > .tabsdown-site__tab')) == 2
    assert len(outer.select(':scope > .tabsdown-site__panels > .tabsdown-site__panel')) == 2
    assert outer.select_one('.tabsdown-site__tab strong').get_text() == '概念'
    assert not soup.script and '&lt;script&gt;' in output
    assert [item.get_text(strip=True) for item in outer.select('.tabsdown-site__fallback-label')] == [
        '概念', '例子 <script>', '内一', '内二']
    assert soup.select_one('.tabsdown-site__panel h2').get_text() == '小节'
    assert len(soup.select('.tabsdown-site')) == 2


def test_invalid_tabsdown_blocks_rendering():
    with pytest.raises(ExportError, match='Tabsdown.*至少需要两个'):
        render('```tabsdown\ntab: 一\n正文\n```', 'courses/错误.md', '')


def test_tabsdown_stays_inside_an_admonition_after_export_indentation():
    body = '''!!! tip "提示"
    正文

    ```tabsdown
    tab: A
    一
    tab: B
    二
    ```'''
    soup = BeautifulSoup(render(body, 'courses/嵌套.md', ''), 'html.parser')
    callout = soup.select_one('div.obsidian-callout')
    assert callout.select_one('.tabsdown-site')


def test_card_headings_extract_clean_main_sections_only():
    body = '''# 树

!!! note
    ## 提示块内的示例

```markdown
## 代码中的标题
```

### **基础**概念 {#基础概念}
#### 深层小节
### [树的表示](#基础概念)
### `Expression Trees` & 遍历
### 基础概念
### $x^2$
$$
x^*
=
f(x)
$$
### 应用
### 更多内容
'''
    assert card_headings(body, '树') == [
        '基础概念', '树的表示', 'Expression Trees & 遍历', '应用']
    assert card_headings('# 树\n\n只有正文', '树') == []
    assert card_headings('## 概念\n\n ```c\n#include <stdio.h>\n#define SIZE 5\n ```\n\n## 实现', '树') == ['概念', '实现']


def test_card_directory_keeps_all_levels_and_configured_labels():
    assert card_directory('courses/FDS-ZJU/notes/树.md', {}) == ['Course', 'FDS-ZJU', 'notes']
    assert card_directory('knowledge/tech/主题/index.md', {'knowledge/tech': '技术积累'}) == [
        'Tech', '技术积累', '主题']


def test_custom_callout_keeps_its_obsidian_identifier_and_title():
    output = render('!!! intro\n    导言', 'reading/一.md', '', '文章标题')
    soup = BeautifulSoup(output, 'html.parser')
    callout = soup.select_one('div.obsidian-callout[data-callout="intro"]')
    assert callout and callout.select_one('.callout-title').get_text() == 'Intro'


def test_adjacent_obsidian_callouts_render_as_separate_blocks():
    source = '> [!question]\n> 一个问题\n\n> [!quote]\n> 一段引用'
    soup = BeautifulSoup(render(convert_callouts(source), 'courses/例.md', ''), 'html.parser')
    callouts = soup.select('.obsidian-callout')
    assert [item['data-callout'] for item in callouts] == ['question', 'quote']
    assert [item.select_one('.callout-title').get_text() for item in callouts] == ['Question', 'Quote']
    assert '一段引用' not in callouts[0].get_text()
    assert '一段引用' in callouts[1].get_text()


def test_callout_manager_colors_and_icons_become_safe_css():
    css = custom_callout_styles({
        'intro': {'icon': 'lucide-anchor', 'dark_color': '83, 223, 221'},
        'bad"]': {'light_color': '999, 0, 0'},
    })
    assert 'data-callout="intro"' in css and '--callout-rgb: 83 223 221' in css
    assert '--callout-icon: url("../lib/lucide/anchor.svg")' in css
    assert 'bad' not in css


def test_callout_title_and_nested_content_keep_separate_rendering_regions():
    source = '''> [!note] **重点**
> 第一段。
>
> > [!tip]- 内层提示
> > 内层正文。
>
> 最后一段。'''
    soup = BeautifulSoup(render(convert_callouts(source), 'courses/例.md', ''), 'html.parser')
    outer = soup.select_one('div.obsidian-callout')
    title = outer.select_one(':scope > .callout-title')
    assert title.select_one('.callout-title-inner strong').get_text() == '重点'
    assert title.select_one('.callout-icon')['aria-hidden'] == 'true'
    content = outer.select_one(':scope > .callout-content')
    assert [p.get_text() for p in content.find_all('p', recursive=False)] == ['第一段。', '最后一段。']
    inner = content.select_one('details.obsidian-callout')
    assert not inner.has_attr('open')
    assert inner.select_one(':scope > summary .callout-fold')['aria-hidden'] == 'true'
    assert inner.select_one(':scope > .callout-content').get_text(strip=True) == '内层正文。'


def test_code_html_stays_literal():
    output = render('```html\n<img src="secret"> & {{ site.title }}\n```', 'courses/例.md', '')
    soup = BeautifulSoup(output, 'html.parser')
    assert not soup.img
    assert soup.select_one('.rouge-code').get_text().strip() == '<img src="secret"> & {{ site.title }}'


def test_staging_uses_only_public_notes_and_keeps_paths_and_dates(tmp_path):
    vault = tmp_path / 'vault'
    (vault / '课程').mkdir(parents=True)
    (vault / '课程/文 档.md').write_text('---\npublish: true\ntags: [CNN]\n---\n# 公开\n正文\n`{{ site.title }}`\n[[秘密|普通文字]]')
    (vault / '课程/秘密.md').write_text('---\npublish: false\n---\nPRIVATE_SENTINEL')
    (vault / '课程/index.md').write_text('---\npublish: true\n---\n# 课程索引\n自己整理的索引。')
    cfg = {'site': {'name': 'test'}, 'sources': [{'path': '课程', 'destination': 'courses'}]}
    docs = tmp_path / 'docs'
    manifest = Exporter(vault, cfg, ROOT / 'site-template').export(docs, {
        'courses/文 档.md': {
            'published_at': '2026-09-14T12:30:00+08:00',
            'updated_at': '2026-09-16T09:45:00+08:00',
        }
    })
    assert manifest['notes'][1]['published_at'] == '2026-09-14T12:30:00+08:00'
    output = tmp_path / 'jekyll'
    settings = yaml.safe_load((ROOT / '_config.yml').read_text())
    stage(docs, output, ROOT / 'site-template', settings, {})
    posts = list((output / '_posts').glob('*.html'))
    assert len(posts) == 1  # A published section index becomes the tab itself.
    metadata, body = frontmatter(posts[0].read_text())
    assert metadata['permalink'] == '/courses/文 档/'
    assert metadata['date'] == '2026-09-14T12:30:00+08:00'
    assert metadata['last_modified_at'] == '2026-09-16T09:45:00+08:00'
    assert metadata['tags'] == ['CNN'] and metadata['render_with_liquid'] is False
    assert 'description' not in metadata
    assert '{{ site.title }}' in body
    assert '自己整理的索引' in (output / '_tabs/course.html').read_text()
    assert 'PRIVATE_SENTINEL' not in ''.join(p.read_text() for p in output.rglob('*.html'))
    assert sorted(frontmatter(p.read_text())[0]['order'] for p in (output / '_tabs').iterdir()) == [1, 2, 3, 4]


def test_invalid_date_blocks_build():
    with pytest.raises(ExportError, match='ISO 日期'):
        post_date('yesterday')


def test_built_breadcrumbs_link_every_public_parent(tmp_path):
    from scripts.exporter import page_url
    from scripts.site import build_snapshot

    vault = tmp_path / 'vault'
    files = {
        '课程/课程2/index.md': '---\npublish: true\ntitle: "<课程> & {{ literal }}"\n---\n课程介绍',
        '课程/课程2/实验 一/示例.md': '---\npublish: true\n---\n正文',
        '课程/课程2/秘密/未公开.md': '---\npublish: false\n---\nPRIVATE_SENTINEL',
        '阅读/书/第一章.md': '---\npublish: true\n---\n正文',
        '技术/工具.md': '---\npublish: true\n---\n正文',
    }
    for name, body in files.items():
        source = vault / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(body)
    cfg = {'site': {'name': 'test'}, 'labels': {'knowledge/tech': '技术积累'}, 'sources': [
        {'path': '课程', 'destination': 'courses'},
        {'path': '阅读', 'destination': 'reading'},
        {'path': '技术', 'destination': 'knowledge/tech'},
    ]}
    docs = tmp_path / 'docs'
    Exporter(vault, cfg, ROOT / 'site-template').export(docs)
    build_snapshot(docs, tmp_path / 'build', theme='chirpy')
    site = tmp_path / 'build/site'
    cases = [
        ('courses/课程2/实验 一/示例', ['Home', 'Course', '<课程> & {{ literal }}', '实验 一', '示例'],
         ['index.md', 'courses/index.md', 'courses/课程2/index.md', 'courses/课程2/实验 一/index.md']),
        ('courses/课程2/实验 一', ['Home', 'Course', '<课程> & {{ literal }}', '实验 一'],
         ['index.md', 'courses/index.md', 'courses/课程2/index.md']),
        ('courses/课程2', ['Home', 'Course', '<课程> & {{ literal }}'],
         ['index.md', 'courses/index.md']),
        ('courses', ['Home', 'Course'], ['index.md']),
        ('reading/书/第一章', ['Home', 'Reading', '书', '第一章'],
         ['index.md', 'reading/index.md', 'reading/书/index.md']),
        ('knowledge/tech/工具', ['Home', 'Tech', '技术积累', '工具'],
         ['index.md', 'knowledge/index.md', 'knowledge/tech/index.md']),
    ]
    for path, titles, parents in cases:
        soup = BeautifulSoup((site / path / 'index.html').read_text(), 'html.parser')
        crumb = soup.select_one('#breadcrumb')
        assert 'note-breadcrumbs' in crumb.get('class', [])
        assert soup.select_one('link[href$="/breadcrumbs.css"]')
        assert [span.get_text(strip=True) for span in crumb.select('span')] == titles
        expected = ['/' if p == 'index.md' else '/' + page_url(p) for p in parents]
        assert [a['href'] for a in crumb.select('a')] == expected
        assert crumb.select_one('[aria-current="page"]').get_text() == titles[-1]
        assert '秘密' not in str(crumb)
    for path, titles in [('index.html', ['Home']), ('about/index.html', ['Home', 'About'])]:
        soup = BeautifulSoup((site / path).read_text(), 'html.parser')
        assert [s.get_text(strip=True) for s in soup.select('#breadcrumb span')] == titles


def test_course_tree_keeps_hierarchy_order_and_public_links(tmp_path):
    vault = tmp_path / 'vault'
    files = {
        '课程/课程10/第一篇.md': '---\npublish: true\n---\n第一篇',
        '课程/课程2/index.md': '---\npublish: true\n---\n# 课程介绍',
        '课程/课程2/Lecture10.md': '---\npublish: true\n---\n第十讲',
        '课程/课程2/Lecture2.md': '---\npublish: true\n---\n第二讲',
        '课程/课程2/置顶.md': '---\npublish: true\nnav_order: 1\n---\n置顶',
        '课程/课程2/实验/示例.md': '---\npublish: true\ntitle: "<示例> & {{ literal }}"\n---\n正文',
        '课程/课程2/秘密/未公开.md': '---\npublish: false\n---\nPRIVATE_SENTINEL',
        '课程/导读.md': '---\npublish: true\n---\n导读',
        '阅读/书.md': '---\npublish: true\n---\n阅读',
    }
    for name, body in files.items():
        source = vault / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(body)
    labels = {'courses/课程2': '课程 & 二'}
    cfg = {'site': {'name': 'test'}, 'labels': labels, 'sources': [
        {'path': '课程', 'destination': 'courses'},
        {'path': '阅读', 'destination': 'reading'},
    ]}
    docs = tmp_path / 'docs'
    manifest = Exporter(vault, cfg, ROOT / 'site-template').export(docs)
    output = tmp_path / 'jekyll'
    stage(docs, output, ROOT / 'site-template', {'baseurl': '/notes-site'}, labels)
    _, body = frontmatter((output / '_tabs/course.html').read_text())
    soup = BeautifulSoup(body, 'html.parser')
    cards = soup.select('.course-tree > .categories')
    assert [card.select_one('a').get_text() for card in cards] == ['课程 & 二', '课程10', '导读']
    first = cards[0]
    assert first.select_one('summary .small').get_text() == '1 个子目录，5 篇笔记'
    assert [a.get_text() for a in first.select('details > ul > .course-note > a')] == [
        '<示例> & {{ literal }}', '置顶', 'Lecture2', 'Lecture10']
    assert first.select_one('.course-branch details summary a').get_text() == '实验'
    assert not soup.find('示例') and 'PRIVATE_SENTINEL' not in body and '秘密' not in body
    index_post = next(
        post for post in (output / '_posts').glob('*.html')
        if frontmatter(post.read_text())[0]['permalink'] == '/courses/课程2/'
    )
    index_body = frontmatter(index_post.read_text())[1]
    index = BeautifulSoup(index_body, 'html.parser').select_one('.course-folder-index')
    assert index and index.h2.get_text() == '课程笔记'
    assert [a.get_text() for a in index.select('.course-note a')] == [
        '<示例> & {{ literal }}', '置顶', 'Lecture2', 'Lecture10']
    assert not index.find(string='PRIVATE_SENTINEL')
    from scripts.exporter import page_url
    links = [a['href'] for a in soup.select('.course-tree a')]
    for note in manifest['notes']:
        url = '/notes-site/' + page_url(note['path'])
        assert links.count(url) == (1 if note['path'].startswith('courses/') else 0)


def test_empty_course_tree_has_no_disclosure(tmp_path):
    from scripts.jekyll import course_tree
    soup = BeautifulSoup(course_tree({}, '', {}), 'html.parser')
    assert '暂无公开笔记' in soup.get_text()
    assert not soup.find('details') and not soup.find('a')


def test_tech_is_flat_but_reading_keeps_deep_directories(tmp_path):
    notes = {
        'knowledge/tech/直接.md': {'title': '直接技术笔记'},
        'knowledge/tech/子目录/深入.md': {'title': '深入技术笔记'},
        'reading/reading/书/第一章.md': {'title': '第一章'},
        'reading/paper/论文.md': {'title': '论文笔记'},
    }
    labels = {
        'knowledge/tech': '技术积累', 'knowledge/tools': 'Tools',
        'reading/reading': 'Reading', 'reading/paper': 'Paper',
    }

    tech = BeautifulSoup(section_list(notes, 'knowledge', '/notes-site', labels), 'html.parser')
    assert [card.select_one('summary a').get_text() for card in tech.select('.section-list > .categories')] == [
        '技术积累', 'Tools']
    assert [row.a.get_text() for row in tech.select('.course-note')] == [
        '直接技术笔记', '深入技术笔记']
    assert len(tech.select('.course-note > .fa-file-lines')) == 2
    assert not tech.select('.course-branch, .course-subfolder')
    assert '暂无公开笔记' in tech.select('.categories')[1].get_text()

    reading = BeautifulSoup(folder_tree(notes, 'reading', '/notes-site', labels), 'html.parser')
    assert [card.select_one('.card-header a').get_text() for card in reading.select('.course-tree > .categories')] == [
        'Reading', 'Paper']
    assert [row.a.get_text() for row in reading.select('.course-note')] == ['第一章', '论文笔记']
    assert reading.select_one('.course-branch .course-subfolder a').get_text() == '书'
    assert len(reading.select('.course-note > .fa-file-lines')) == 2


def test_official_jekyll_build_keeps_literal_code_and_navigation(tmp_path):
    from scripts.site import build_snapshot
    vault = tmp_path / 'vault'
    (vault / '课程/FDS-ZJU/notes').mkdir(parents=True)
    (vault / '课程/无章节.md').write_text('---\npublish: true\n---\n不应出现在卡片的正文')
    (vault / '课程/FDS-ZJU/notes/示例.md').write_text('''---
publish: true
tags: [test]
---
# 示例

正文[^1]。中文$x^2$。~~划分策略~~。

## **基础**概念 {#基础概念}

## `A` & B

```html
<img src="literal"> & {{ site.title }} {% include missing.html %}
```

[^1]: 脚注正文。
''')
    cfg = {'site': {'name': 'test'}, 'sources': [{'path': '课程', 'destination': 'courses'}]}
    docs = tmp_path / 'docs'
    Exporter(vault, cfg, ROOT / 'site-template').export(docs, {
        'courses/FDS-ZJU/notes/示例.md': {
            'published_at': '2026-09-14T12:30:00+08:00',
            'updated_at': '2026-09-16T09:45:00+08:00',
        }
    })
    pages = build_snapshot(docs, tmp_path / 'build', theme='chirpy')
    assert pages >= 10
    site = tmp_path / 'build/site'
    soup = BeautifulSoup((site / 'courses/FDS-ZJU/notes/示例/index.html').read_text(), 'html.parser')
    assert [link.get_text(strip=True) for link in soup.select('#sidebar a.nav-link')] == ['HOME', 'COURSE', 'READING', 'TECH', 'ABOUT']
    assert soup.select_one('.rouge-code').get_text().strip() == '<img src="literal"> & {{ site.title }} {% include missing.html %}'
    assert soup.find('del').get_text() == '划分策略'
    assert soup.select_one('.code-header button') and soup.find(id='fn:1')
    assert not soup.select_one('img[src="literal"]')
    assert not soup.select_one('.post-desc')
    post_meta = soup.select_one('main .post-meta').get_text(' ', strip=True)
    assert 'Posted Sep 14, 2026' in post_meta
    assert 'Updated Sep 16, 2026' in post_meta
    home = BeautifulSoup((site / 'index.html').read_text(), 'html.parser')
    cards = {card.h1.get_text(strip=True): card for card in home.select('#post-list .card')}
    assert cards['示例'].select_one('.card-text').get_text(strip=True) == '基础概念 · A & B'
    assert cards['示例'].select_one('.card-directory').get_text(strip=True) == 'Course / FDS-ZJU / notes'
    assert not cards['无章节'].select_one('.card-text')
    assert '不应出现在卡片的正文' not in home.select_one('#post-list').get_text()
    assert home.select_one('link[href$="/note-cards.css"]')


def test_built_post_navigation_uses_only_same_folder_in_filename_order(tmp_path):
    from scripts.exporter import page_url
    from scripts.site import build_snapshot

    vault = tmp_path / 'vault'
    files = {
        '课程/index.md': {'publish': True},
        '课程/课程2/Lecture10.md': {'publish': True, 'date': '2020-01-01', 'nav_order': 1},
        '课程/课程2/Lecture2 中文.md': {
            'publish': True, 'date': '2020-01-02', 'title': '<第二讲> & {{ literal }}'},
        '课程/课程2/Lecture1.md': {'publish': True, 'date': '2020-01-03', 'title': 'Z first'},
        '课程/课程2/Lecture3.md': {'publish': False},
        '课程/课程2/实验/Lecture3.md': {'publish': True},
        '课程/课程20/Lecture3.md': {'publish': True},
    }
    for name, metadata in files.items():
        source = vault / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True) + '---\n正文。')
    cfg = {'site': {'name': 'test'}, 'sources': [{'path': '课程', 'destination': 'courses'}]}
    docs = tmp_path / 'docs'
    Exporter(vault, cfg, ROOT / 'site-template').export(docs)
    build_snapshot(docs, tmp_path / 'build', theme='chirpy')
    site = tmp_path / 'build/site'

    def navigation(path):
        soup = BeautifulSoup((site / path / 'index.html').read_text(), 'html.parser')
        buttons = soup.select('.post-navigation > *')
        assert [button['aria-label'] for button in buttons] == ['Older', 'Newer']
        for button in buttons:
            if not button.get('href'):
                assert 'disabled' in button['class'] and button.get_text(strip=True) == '-'
        return buttons

    siblings = ['Lecture1', 'Lecture2 中文', 'Lecture10']
    titles = ['Z first', '<第二讲> & {{ literal }}', 'Lecture10']
    for i, name in enumerate(siblings):
        buttons = navigation('courses/课程2/' + name)
        for button, offset in zip(buttons, [-1, 1]):
            j = i + offset
            if 0 <= j < len(siblings):
                assert button['href'] == '/' + page_url('courses/课程2/' + siblings[j] + '.md')
                assert button.get_text(strip=True) == titles[j]
            else:
                assert not button.get('href')
    for path in ['courses/课程2/实验/Lecture3', 'courses/课程20/Lecture3']:
        assert all(not button.get('href') for button in navigation(path))
