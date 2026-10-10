import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup
import yaml

from scripts.astro import stage
from scripts.exporter import Exporter
from scripts.site import build_snapshot

ROOT = Path(__file__).resolve().parents[1]


def snapshot(tmp_path):
    vault = tmp_path / 'vault'
    folder = vault / '课程/测试'
    folder.mkdir(parents=True)
    (folder / 'Lecture2 中文.md').write_text('''---
publish: true
tags: [AI/Agent]
---
# 示例

第一行
第二行。~~中文删除线~~。$x^2$。

## 中文章节

> [!intro] 自定义标题
> 导言正文。

> [!quote]
> 相邻引用。

```tabsdown
tab: 概念
面板一。[[Lecture10]]
tab: 例子
面板二。$y=2$
```

```html
<img src="private"> & {{ site.title }} {% include missing.html %}
```

[[Lecture10#章节]]
''')
    (folder / 'Lecture10.md').write_text('---\npublish: true\ntags: [AI/Agent]\n---\n# 第十讲\n\n## 章节\n正文。')
    (folder / '秘密.md').write_text('---\npublish: false\n---\nPRIVATE_SENTINEL')
    cfg = {'site': {'name': 'test'}, 'sources': [{'path': '课程', 'destination': 'courses'}]}
    for section, tag in [('reading', '阅读'), ('knowledge', '工具')]:
        section_folder = vault / section
        section_folder.mkdir()
        (section_folder / '示例.md').write_text(f'---\npublish: true\ntags: [{tag}]\n---\n# {section}\n')
        cfg['sources'].append({'path': section, 'destination': section})
    docs = tmp_path / 'docs'
    Exporter(vault, cfg, ROOT / 'site-template').export(docs, {
        'courses/测试/Lecture2 中文.md': {'published_at': '2026-09-14T12:30:00+08:00',
                                     'updated_at': '2026-09-16T09:45:00+08:00'}
    })
    return docs


def test_pure_adapter_preserves_public_contract_and_snapshot(tmp_path):
    docs = snapshot(tmp_path)
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in docs.rglob('*') if p.is_file()}
    data = stage(docs, tmp_path / 'stage', ROOT / 'site-template', {'baseurl': '/notes-site'}, {})
    pages = json.loads(data.read_text())['pages']
    page = next(p for p in pages if p['route'] == 'courses/测试/Lecture2 中文')
    soup = BeautifulSoup(page['html'], 'html.parser')
    assert page['url'] == '/notes-site/courses/%E6%B5%8B%E8%AF%95/Lecture2%20%E4%B8%AD%E6%96%87/'
    assert page['publishedAt'] == '2026-09-14T12:30:00+08:00'
    assert page['updatedAt'] == '2026-09-16T09:45:00+08:00'
    assert page['folder_next']['title'] == 'Lecture10'
    assert page['folder_next']['subtitle'] == '第十讲'
    assert page['folder_previous'] is None
    assert soup.select_one('p br')
    assert soup.select_one('del').get_text() == '中文删除线'
    assert soup.select_one('.arithmatex')
    assert soup.select_one('.obsidian-callout[data-callout="intro"] .callout-title').get_text() == '自定义标题'
    assert soup.select_one('.obsidian-callout[data-callout="quote"]')
    assert soup.select_one('.tabsdown-site__panel a')['href'].startswith('/notes-site/courses/')
    assert soup.select_one('.note-code code').get_text().strip() == '<img src="private"> & {{ site.title }} {% include missing.html %}'
    assert not soup.select_one('img[src="private"]')
    assert 'PRIVATE_SENTINEL' not in data.read_text() and '秘密' not in data.read_text()
    assert 'tags/ai-agent' in {p['route'] for p in pages}
    assert hashes == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in docs.rglob('*') if p.is_file()}


def test_filename_titles_work_with_existing_snapshot_and_keep_body_anchors(tmp_path):
    docs = snapshot(tmp_path)
    before = {p: p.read_bytes() for p in docs.rglob('*') if p.is_file()}
    data = stage(docs, tmp_path / 'stage', ROOT / 'site-template', {'baseurl': '/notes-site'}, {})
    pages = {p['route']: p for p in json.loads(data.read_text())['pages']}
    page = pages['courses/测试/Lecture2 中文']
    assert page['title'] == 'Lecture2 中文'
    assert page['subtitle'] == '示例'
    soup = BeautifulSoup(page['html'], 'html.parser')
    assert not soup.select('h1')
    assert soup.select_one('#示例')
    assert page['cardHeadings'] == ['中文章节']
    assert pages['courses']['title'] == 'Course'
    assert not pages['courses'].get('subtitle')
    listing = BeautifulSoup(pages['courses']['html'], 'html.parser')
    link = listing.select_one('a[href$="/Lecture10/"]')
    assert link.select_one('.note-title-primary').get_text() == 'Lecture10'
    assert link.select_one('.note-title-secondary').get_text() == '第十讲'
    nested = BeautifulSoup(pages['courses/测试']['html'], 'html.parser')
    # Generated Chinese index headings used Markdown's existing ASCII slug.
    assert nested.select_one('#_1')
    assert nested.select_one('a[href$="/Lecture10/"] .note-title-primary').get_text() == 'Lecture10'
    assert nested.select_one('a[href$="/Lecture10/"] .note-title-secondary').get_text() == '第十讲'
    assert before == {p: p.read_bytes() for p in docs.rglob('*') if p.is_file()}


def test_duplicate_titles_and_directory_indexes_have_no_subtitle(tmp_path):
    docs = snapshot(tmp_path)
    folder = docs / 'courses/测试'
    (folder / 'Same.md').write_text('---\ntitle: Same\n---\n# Same\n正文。')
    (folder / 'index.md').write_text('---\ntitle: 课程概览\n---\n# 课程概览\n目录介绍。')
    manifest = json.loads((docs / 'publication.json').read_text())
    manifest['notes'] += [
        {'path': 'courses/测试/Same.md', 'title': 'Same', 'published_at': '2026-09-14'},
        {'path': 'courses/测试/index.md', 'title': '课程概览', 'published_at': '2026-09-14'},
    ]
    (docs / 'publication.json').write_text(json.dumps(manifest, ensure_ascii=False))
    data = stage(docs, tmp_path / 'stage', ROOT / 'site-template', {'baseurl': '/notes-site'}, {})
    pages = {p['route']: p for p in json.loads(data.read_text())['pages']}
    assert pages['courses/测试/Same']['title'] == 'Same'
    assert not pages['courses/测试/Same'].get('subtitle')
    assert pages['courses/测试']['title'] == '课程概览'
    assert not pages['courses/测试'].get('subtitle')


def test_pure_production_build_has_search_navigation_dates_and_assets(tmp_path):
    docs = snapshot(tmp_path)
    work = tmp_path / 'build'
    assert build_snapshot(docs, work, theme='pure') >= 8
    site = work / 'site'
    soup = BeautifulSoup((site / 'courses/测试/Lecture2 中文/index.html').read_text(), 'html.parser')
    assert soup.select_one('#content-header h1').get_text(strip=True) == 'Lecture2 中文'
    assert soup.select_one('.note-subtitle').get_text(strip=True) == '示例'
    assert soup.select_one('#breadcrumb [aria-current] .note-title-primary').get_text() == 'Lecture2 中文'
    assert soup.select_one('#breadcrumb [aria-current] .note-title-secondary').get_text() == '示例'
    neighbor = soup.select_one('.post-navigation a[aria-label="Newer"]')
    assert neighbor.select_one('.note-title-primary').get_text() == 'Lecture10'
    assert neighbor.select_one('.note-title-secondary').get_text() == '第十讲'
    assert soup.select_one('.note-heading').get_text(' ', strip=True) == 'Lecture2 中文 示例'
    assert soup.select_one('.note-heading').get('data-search-title') == 'Lecture2 中文 · 示例'
    assert soup.select_one('[data-pagefind-filter="kind:note"]')
    search_metadata = soup.select_one('[data-pagefind-meta="directory[data-directory]"]')
    assert search_metadata['data-directory'] == 'Course / 测试'
    assert search_metadata['data-section'] == 'Course'
    assert search_metadata['data-pagefind-filter'] == 'section[data-section]'
    assert [a.get_text(strip=True) for a in soup.select('#headerExpandContent > div > a')] == ['Course', 'Reading', 'Tech', 'About']
    assert soup.select_one('toc-heading a')['href'] == '#中文章节'
    assert 'Posted Sep 14, 2026' in soup.select_one('.post-meta').get_text(' ', strip=True)
    assert 'Updated Sep 16, 2026' in soup.select_one('.post-meta').get_text(' ', strip=True)
    assert soup.select_one('script[src$="tex-mml-chtml.js"]')
    assert soup.select_one('#breadcrumb a[href="/notes-site/courses/"]')
    assert soup.select_one('.post-navigation a[aria-label="Newer"]')['href'].endswith('/Lecture10/')
    assert not soup.select_one('.post-navigation a[aria-label="Older"]')
    assert (site / 'pagefind/pagefind.js').is_file()
    assert (site / 'tags/ai-agent/index.html').is_file()
    assert (site / 'feed.xml').is_file()
    assert (site / 'assets/lib/fontawesome-free/webfonts/fa-solid-900.woff2').is_file()
    course = BeautifulSoup((site / 'courses/index.html').read_text(), 'html.parser')
    assert course.select_one('#sidebar .section-tags h2').get_text(strip=True) == 'Tags'
    assert course.select_one('#sidebar .section-tags li a')['href'] == '/notes-site/tags/ai-agent/'
    for section, tag in [('courses', 'AI/Agent'), ('reading', '阅读'), ('knowledge', '工具')]:
        listing = BeautifulSoup((site / section / 'index.html').read_text(), 'html.parser')
        assert [a.get_text(strip=True) for a in listing.select('#sidebar .section-tags li a')] == [tag]
        assert listing.select_one('#sidebar .all-tags')['href'] == '/notes-site/tags/'
    assert not soup.select_one('.section-tags')  # Article pages keep their table of contents.
    tags = BeautifulSoup((site / 'tags/index.html').read_text(), 'html.parser')
    chips = tags.select('.tag-cloud .tag-chip')
    assert len(chips) == 3
    assert chips[0]['href'] == '/notes-site/tags/ai-agent/'
    assert [chip.select_one('.tag-count').get_text() for chip in chips] == ['2', '1', '1']
    assert not tags.select_one('#sidebar')
