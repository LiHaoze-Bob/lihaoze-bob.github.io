import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup
import yaml

from scripts.astro import stage
from scripts.exporter import Exporter
from scripts.site import build_snapshot
from scripts.jekyll import render

ROOT = Path(__file__).resolve().parents[1]


def test_pure_code_displays_language_without_including_label_in_copied_code():
    for language, source in [
        ('python', 'print("hello")\n'),
        ('json', '{"ok": true}\n'),
        ('http', 'GET /weather\n'),
        ('unknown-example', '<literal>\n'),
    ]:
        soup = BeautifulSoup(render(f'```{language}\n{source}```', 'example.md', '',
                                    theme='pure'), 'html.parser')
        label = soup.select_one('.note-code .code-header .code-language')
        assert label is not None
        assert label.get_text() == language
        assert soup.select_one('.note-code code').get_text() == source
        assert soup.select_one('.code-header button[aria-label="Copy code"]')


def test_pure_code_preserves_informal_json_http_and_literal_html_without_error_tokens():
    samples = [
        ('json', 'weather_tool = {"name": "get_weather"}\n'),
        ('json', 'response = client.chat.completions.create(model=model)\n'),
        ('http', 'GET /weather?city=Pittsburgh&units=F\nX-API-Key: 调用者的密钥\n'),
        ('unknown-example', '<img src="secret"> & {{ literal }}\n'),
    ]
    for language, source in samples:
        soup = BeautifulSoup(render(f'```{language}\n{source}```', 'example.md', '',
                                    theme='pure'), 'html.parser')
        block = soup.select_one('.note-code')
        assert block['data-language'] == language
        assert block.code.get_text() == source
        assert not block.select('.err, img')


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
    assert pages['courses']['title'] == 'Courses'
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
    assert search_metadata['data-directory'] == 'Courses / 测试'
    assert search_metadata['data-section'] == 'Courses'
    assert search_metadata['data-pagefind-filter'] == 'section[data-section]'
    assert [a.get_text(strip=True) for a in soup.select('#headerExpandContent a')] == ['Notes', 'Projects', 'About']
    assert soup.select_one('toc-heading a')['href'] == '#中文章节'
    assert 'Posted Sep 14, 2026' in soup.select_one('.post-meta').get_text(' ', strip=True)
    assert 'Updated Sep 16, 2026' in soup.select_one('.post-meta').get_text(' ', strip=True)
    assert soup.select_one('script[src$="tex-mml-chtml.js"]')
    assert soup.select_one('#breadcrumb a[href="/courses/"]')
    assert soup.select_one('.post-navigation a[aria-label="Newer"]')['href'].endswith('/Lecture10/')
    assert not soup.select_one('.post-navigation a[aria-label="Older"]')
    assert (site / 'pagefind/pagefind.js').is_file()
    search_index = json.loads((site / 'pagefind/pagefind-entry.json').read_text())
    assert set(search_index['languages']) == {'zh'}  # Chinese segmentation, independent of English UI.
    assert (site / 'tags/ai-agent/index.html').is_file()
    assert (site / 'feed.xml').is_file()
    assert (site / 'assets/lib/fontawesome-free/webfonts/fa-solid-900.woff2').is_file()
    course = BeautifulSoup((site / 'courses/index.html').read_text(), 'html.parser')
    assert course.select_one('#sidebar .section-tags h2').get_text(strip=True) == 'Tags'
    assert course.select_one('#sidebar .section-tags li a')['href'] == '/tags/ai-agent/'
    for section, tag in [('courses', 'AI/Agent'), ('reading', '阅读'), ('knowledge', '工具')]:
        listing = BeautifulSoup((site / section / 'index.html').read_text(), 'html.parser')
        assert [a.get_text(strip=True) for a in listing.select('#sidebar .section-tags li a')] == [tag]
        assert listing.select_one('#sidebar .all-tags')['href'] == '/tags/'
    assert not soup.select_one('.section-tags')  # Article pages keep their table of contents.
    tags = BeautifulSoup((site / 'tags/index.html').read_text(), 'html.parser')
    chips = tags.select('.tag-cloud .tag-chip')
    assert len(chips) == 3
    assert chips[0]['href'] == '/tags/ai-agent/'
    assert [chip.select_one('.tag-count').get_text() for chip in chips] == ['2', '1', '1']
    assert not tags.select_one('#sidebar')

    home = BeautifulSoup((site / 'index.html').read_text(), 'html.parser')
    assert home.html['lang'] == 'en'
    assert home.select_one('h1').get_text(strip=True) == 'Haoze Li'
    assert home.title.get_text() == 'sychostar'
    assert home.select_one('meta[property="og:title"]')['content'] == 'sychostar'
    assert home.select_one('.site-brand').get_text(strip=True) == 'sychostar'
    assert home.select_one('.site-brand')['aria-label'] == 'sychostar — Home'
    assert home.select_one('h1 + .home-handle').get_text(strip=True) == '@sychostar'
    assert not home.select_one('.home-handle a')
    intro = home.select('.home .personal-prose > p')
    assert len(intro) == 5
    assert intro[1].select_one('a')['href'] == '/about/'
    assert 'a CS undergrad at Zhejiang University & an AI enthusiast.' in intro[0].get_text()
    assert home.select_one('a[href="https://space.bilibili.com/2118021600"]')
    assert home.select_one('a[href="https://www.zhihu.com/people/sychostar"]')
    assert not home.select_one('#post-list')
    assert home.select_one('a[href="mailto:haozeli2025@gmail.com"]')
    projects = BeautifulSoup((site / 'projects/index.html').read_text(), 'html.parser')
    assert projects.select_one('#lingxiglove') and projects.select_one('#zju-sports-hub')
    assert projects.html['lang'] == 'en'
    about = BeautifulSoup((site / 'about/index.html').read_text(), 'html.parser')
    assert about.html['lang'] == 'en'
    assert not about.select_one('.about-greeting')
    assert about.select_one('.about-music') and about.select_one('.about-activity')
    assert about.select_one('.github-greeting img')['alt'] == 'Hi, I’m sychostar'
    assert len(about.select('.github-note-links li')) == 4
    assert len(about.select('.github-stats img')) == 2
    assert len(about.select('.github-contributions img')) == 2
    assert len(about.select('.about-activity')) == 1
    assert 'Asia/Shanghai' in about.select_one('[data-github-weekly]').get_text()
    assert about.select_one('[data-github-snapshot]')
    assert about.select_one('#education')
    notes = BeautifulSoup((site / 'notes/index.html').read_text(), 'html.parser')
    assert len(notes.select('.note-preview')) == 4
    assert notes.html['lang'] == 'en'
    assert not notes.select_one('.section-heading > span')
    assert soup.select_one('#content')['lang'] == 'zh-CN'
    assert notes.title.get_text() == 'Notes • sychostar'
    assert notes.select_one('.site-brand')['aria-label'] == 'sychostar — Home'
    search = BeautifulSoup((site / 'search/index.html').read_text(), 'html.parser')
    assert search.html['lang'] == 'en'
    assert search.select_one('#search-input')['placeholder'] == 'Search notes…'
    assert search.select_one('h1').get_text() == 'Search'
    assert search.select_one('.search-clear')['aria-label'] == 'Clear search'
    assert search.select_one('.search-clear').get_text() == '×'
    assert not search.select_one('.search-eyebrow, .search-intro p, .search-filters button span')
    assert not search.select_one('.search-recent')
    assert search.select_one('.search-more').get_text() == 'Load more'
    assert about.select_one('.about-steam')['data-ui-lang'] == 'en'
    assert 'Snapshot at publication' in about.select_one('.about-steam').get_text()
    assert '2 notes' in course.select_one('.course-tree').get_text()
    assert not (site / 'page2').exists()
    assert next(a for a in soup.select('a') if a.get_text(strip=True) == 'Back')['href'] == '/notes/'


def test_pure_taxonomy_preserves_raw_paths_and_legacy_category_routes(tmp_path):
    docs = snapshot(tmp_path)
    data = stage(docs, tmp_path / 'stage', ROOT / 'site-template', {'baseurl': ''}, {})
    pages = {p['route']: p for p in json.loads(data.read_text())['pages']}
    assert pages['knowledge']['title'] == 'Blog'
    assert pages['courses']['title'] == 'Courses'
    assert pages['knowledge/示例']['directory'] == ['Tech']
    assert 'categories/tech' in pages and 'categories/course' in pages
    assert pages['categories/tech']['title'] == 'Blog'
    assert pages['categories/course']['title'] == 'Courses'
    about = BeautifulSoup(pages['about']['html'], 'html.parser')
    assert not about.select_one('.about-intro')
    assert not about.select_one('.about-activity')
    assert about.select_one('.about-music')
    assert 'about-intro' in (ROOT / 'site-template/_tabs/about.md').read_text()


def test_notes_hub_and_flat_sections_keep_deep_links_and_all_eleven_notes(tmp_path):
    docs = snapshot(tmp_path)
    manifest_path = docs / 'publication.json'
    manifest = json.loads(manifest_path.read_text())
    for index in range(7):
        path = f'knowledge/tech/AI/Example{index}.md'
        target = docs / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'---\ntitle: Example{index}\n---\nA practical example.')
        manifest['notes'].append({'path': path, 'title': f'Example{index}', 'published_at': '2026-12-31T16:30:00Z'})
    (docs / 'knowledge/tech/index.md').write_text('# 技术积累\n')
    (docs / 'knowledge/tech/AI/index.md').write_text('# AI\n')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))
    before = {p: p.read_bytes() for p in docs.rglob('*') if p.is_file()}
    work = tmp_path / 'build'
    build_snapshot(docs, work, theme='pure')
    site = work / 'site'
    hub = BeautifulSoup((site / 'notes/index.html').read_text(), 'html.parser')
    second = BeautifulSoup((site / 'page2/index.html').read_text(), 'html.parser')
    first_urls = [link['href'] for link in hub.select('.note-preview h3 a')]
    second_urls = [link['href'] for link in second.select('.note-preview h3 a')]
    assert len(first_urls) == 10 and len(second_urls) == 1
    assert len(set(first_urls + second_urls)) == 11
    assert second.select_one('.pagination a')['href'] == '/notes/'
    assert second.html['lang'] == 'en'
    assert [h.get_text(strip=True) for h in hub.select('.note-year > h2')] == ['2027', '2026']
    articles = BeautifulSoup((site / 'knowledge/index.html').read_text(), 'html.parser')
    assert len(articles.select('.note-preview')) == 8
    assert not articles.select_one('.course-tree')
    assert 'prose' not in articles.select_one('#content')['class'], 'article typography hides heading links in listings'
    reading = BeautifulSoup((site / 'reading/index.html').read_text(), 'html.parser')
    assert len(reading.select('.note-preview')) == 1
    assert not reading.select_one('.course-tree')
    assert 'prose' not in reading.select_one('#content')['class']
    article = BeautifulSoup((site / 'knowledge/tech/AI/Example0/index.html').read_text(), 'html.parser')
    metadata = article.select_one('[data-pagefind-meta="directory[data-directory]"]')
    assert metadata['data-section'] == 'Blog'
    assert metadata['data-directory'] == 'Blog / AI'
    assert article.select_one('#breadcrumb a[href="/knowledge/tech/AI/"]')
    assert not article.select_one('#breadcrumb a[href="/knowledge/tech/"]')
    assert (site / 'knowledge/tech/index.html').is_file()
    assert (site / 'categories/tech/index.html').is_file()
    assert before == {p: p.read_bytes() for p in docs.rglob('*') if p.is_file()}


def test_pure_feed_contains_full_readable_articles_and_absolute_resources(tmp_path):
    docs = snapshot(tmp_path)
    article = docs / 'courses/测试/Lecture2 中文.md'
    with article.open('a') as output:
        output.write(r'''

![示意图](/assets/images/avatar.png)

??? note "折叠补充"
    折叠内容也要完整显示。

$$
\frac{1}{2} + x^2
$$

文章最后一段。<a href="#中文章节">回到章节</a>
''')
    work = tmp_path / 'build'
    build_snapshot(docs, work, theme='pure')
    channel = ET.parse(work / 'site/feed.xml').getroot().find('channel')
    items = channel.findall('item')
    assert len(items) == 4  # Only published notes, no private notes or generated indexes.
    item = next(item for item in items if item.findtext('title') == 'Lecture2 中文')
    body = item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded')
    assert body, 'RSS must include the full article, not only its heading summary'
    soup = BeautifulSoup(body, 'html.parser')
    assert '文章最后一段。' in soup.get_text()
    assert '面板一。' in soup.get_text() and '面板二。' in soup.get_text()
    assert '折叠内容也要完整显示。' in soup.get_text()
    assert not soup.select('details, summary')
    callout = next(block for block in soup.select('blockquote') if '折叠补充' in block.get_text())
    assert callout.strong.get_text(strip=True) == '折叠补充'
    assert '折叠内容也要完整显示。' in callout.get_text()
    assert soup.select_one('blockquote strong').get_text(strip=True) == '自定义标题'
    assert not soup.select('.arithmatex, svg, math')
    formulas = soup.select('img[src*="/assets/rss-math/"]')
    assert len(formulas) == 3  # Inline, Tabsdown panel, and display math.
    assert {'x^2', 'y=2', '\\frac{1}{2} + x^2'} == {image['alt'].strip() for image in formulas}
    for image in formulas:
        asset = work / 'site' / image['src'].split('github.io/')[1]
        assert asset.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
        assert int(image['width']) > 0 and int(image['height']) > 0
    assert soup.select_one('code').get_text().strip() == '<img src="private"> & {{ site.title }} {% include missing.html %}'
    assert not soup.select('button, script, style')
    assert soup.select_one('img[alt="示意图"]')['src'] == 'https://lihaoze-bob.github.io/assets/images/avatar.png'
    links = [unquote(link['href']) for link in soup.select('a[href]')]
    assert 'https://lihaoze-bob.github.io/courses/测试/Lecture10/#章节' in links
    assert unquote(item.findtext('link')) + '#中文章节' in links
    assert item.findtext('description') == '中文章节'
    assert item.findtext('pubDate') == 'Mon, 14 Sep 2026 04:30:00 GMT'
    assert item.findtext('guid') == item.findtext('link')
    assert 'PRIVATE_SENTINEL' not in body


def test_english_directory_counts_preserve_content_and_legacy_output():
    from scripts.jekyll import folder_tree, section_list
    notes = {'courses/中文课程/子目录/笔记.md': {'title': '中文标题'}}
    english = BeautifulSoup(folder_tree(notes, 'courses', '', {}, lang='en'), 'html.parser')
    assert english.select_one('.small').get_text() == '1 folder · 1 note'
    assert '中文标题' in english.get_text()
    assert '个子目录' in folder_tree(notes, 'courses', '', {})
    for renderer in (folder_tree, section_list):
        assert 'No notes yet.' in renderer({}, 'reading', '', {}, lang='en')
        assert '暂无公开笔记。' in renderer({}, 'reading', '', {})
