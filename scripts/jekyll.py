"""Stage public Obsidian exports for the official Chirpy theme."""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import html
import json
from pathlib import Path
import posixpath
import re
import shutil
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from bs4.formatter import HTMLFormatter
from bs4.dammit import EntitySubstitution
import markdown
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.util import ClassNotFound
import yaml

from scripts.exporter import ExportError, frontmatter, natural_key, page_url
from scripts.tabsdown import TabsdownError, parse as parse_tabsdown, site_markup, transform_blocks
from scripts.steam import MARKER as STEAM_MARKER, render_card as steam_card


def write_page(path: Path, metadata: dict, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
                    + '---\n' + content + '\n')


def render(body: str, source: str, baseurl: str, title: str | None = None,
           theme: str = 'chirpy') -> str:
    """Render common Obsidian syntax with the selected theme's code/image markup."""
    counter = 0

    def expand_tabsdown(text: str) -> str:
        def expand(block):
            nonlocal counter
            counter += 1
            try:
                tabs = parse_tabsdown(block.source)
            except TabsdownError as exc:
                line = block.start_line + exc.line
                raise ExportError(f'{source}：Tabsdown 第 {line} 行：{exc}') from exc
            markup = site_markup(tabs, expand_tabsdown, f'{source}:{counter}')
            return '\n'.join(block.prefix + line if line else block.prefix.rstrip()
                             for line in markup.splitlines())
        try:
            return transform_blocks(text, expand)
        except TabsdownError as exc:
            raise ExportError(f'{source}：Tabsdown 第 {exc.line} 行：{exc}') from exc

    body = expand_tabsdown(body)
    result = markdown.markdown(body, extensions=[
        'admonition', 'attr_list', 'tables', 'footnotes', 'md_in_html', 'nl2br',
        'pymdownx.details', 'pymdownx.highlight', 'pymdownx.superfences', 'pymdownx.arithmatex',
        'pymdownx.tasklist', 'pymdownx.tilde', 'pymdownx.mark', 'toc',
    ], extension_configs={
        'pymdownx.arithmatex': {'generic': True, 'smart_dollar': False},
        'pymdownx.highlight': {'use_pygments': False},
        'pymdownx.tilde': {'subscript': False, 'smart_delete': False},
        'pymdownx.mark': {'smart_mark': False},
    })
    soup = BeautifulSoup(result, 'html.parser')
    # The native layout supplies the title. Preserve the original H1 anchor.
    heading = soup.find('h1', recursive=False)
    if heading and (title is None or heading.get_text() == title):
        anchor = soup.new_tag('span', id=heading.get('id', 'page-title'))
        heading.replace_with(anchor)
    for prompt in soup.select('div.admonition, details[class]'):
        kind = next((c for c in prompt.get('class', []) if c != 'admonition'), 'note').lower()
        prompt['data-callout'] = kind
        if prompt.name == 'div':
            prompt['class'] = ['obsidian-callout']
            title = prompt.find(class_='admonition-title', recursive=False)
            if title:
                title['class'] = ['callout-title']
        else:
            prompt['class'] = ['obsidian-callout']
            title = prompt.find('summary', recursive=False)
            if title:
                title['class'] = ['callout-title']
        if title:
            if title.name == 'p':
                title.name = 'div'
            label = soup.new_tag('span', attrs={'class': 'callout-title-inner'})
            for child in list(title.contents):
                label.append(child.extract())
            icon = soup.new_tag('span', attrs={'class': 'callout-icon', 'aria-hidden': 'true'})
            title.append(icon)
            title.append(label)
            if prompt.name == 'details':
                title.append(soup.new_tag('span', attrs={'class': 'callout-fold', 'aria-hidden': 'true'}))
        content = soup.new_tag('div', attrs={'class': 'callout-content'})
        for child in list(prompt.contents):
            if child is not title:
                content.append(child.extract())
        prompt.append(content)
    for code in soup.select('pre > code'):
        language = next((c.removeprefix('language-') for c in code.get('class', [])
                         if c.startswith('language-')), 'plaintext')
        try:
            lexer = get_lexer_by_name(language)
        except ClassNotFound:
            lexer = TextLexer()
        text = code.get_text()
        colored = highlight(text, lexer, HtmlFormatter(nowrap=True))
        lines = '\n'.join(str(i) for i in range(1, len(text.splitlines()) + 1))
        # Same structure as Kramdown/Rouge, so Chirpy adds its own code toolbar.
        block = (f'<div class="language-{html.escape(language, quote=True)} highlighter-rouge">'
                 '<div class="highlight"><pre class="highlight"><code>'
                 '<table class="rouge-table"><tbody><tr><td class="rouge-gutter gl">'
                 f'<pre class="lineno">{lines}</pre></td><td class="rouge-code">'
                 f'<pre>{colored}</pre></td></tr></tbody></table></code></pre></div></div>')
        if theme == 'pure':
            # Pygments adds a final newline; keep that contract with Prism too.
            literal = html.escape(text if text.endswith('\n') else text + '\n')
            block = (f'<div class="note-code" data-language="{html.escape(language, quote=True)}">'
                     '<div class="code-header">'
                     '<button type="button" aria-label="复制代码">Copy</button></div>'
                     f'<pre class="highlight"><code>{literal}</code></pre></div>')
        code.parent.replace_with(BeautifulSoup(block, 'html.parser'))
    for code in soup.select('code'):
        if not code.find_parent(class_='highlight'):
            code['class'] = [*code.get('class', []), 'highlighter-rouge']
    for element in soup.select('a[href], img[src]'):
        attribute = 'src' if element.name == 'img' else 'href'
        target = element[attribute]
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        path = unquote(parsed.path)
        if path.startswith('/'):
            path = path.removeprefix(baseurl + '/').lstrip('/')
        else:
            path = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
        if path.startswith('../'):
            raise ExportError('链接超出公开目录：' + target)
        url = page_url(path) if path.endswith('.md') else quote(path, safe='/.-_~')
        # Chirpy's native image renderer adds baseurl itself.
        prefix = '' if element.name == 'img' and theme == 'chirpy' else baseurl
        element[attribute] = urlunsplit(('', '', prefix + '/' + url, parsed.query, parsed.fragment))
        if theme == 'pure' and element.name == 'img':
            element['class'] = [*element.get('class', []), 'zoomable']
    # Chirpy parses the Kramdown-style space before a void element's closing slash.
    return soup.decode(formatter=HTMLFormatter(entity_substitution=EntitySubstitution.substitute_xml,
                                               void_element_close_prefix=' /'))


CALLOUT_ICONS = {
    'lucide-anchor': 'anchor',
    'lucide-blend': 'blend',
    'lucide-book-open-check': 'book-open-check',
    'lucide-aperture': 'aperture',
    'lucide-book': 'book',
    'lucide-book-open': 'book-open',
    'lucide-apple': 'apple',
    'lucide-airplay': 'airplay',
}


def custom_callout_styles(callouts: dict) -> str:
    """Translate Callout Manager colors/icons into safe local CSS."""
    rules = []
    for kind, definition in sorted(callouts.items()):
        if not re.fullmatch(r'[\w-]+', kind) or not isinstance(definition, dict):
            continue
        selector = f'.obsidian-callout[data-callout="{kind}"]'
        for scheme in ('light', 'dark'):
            color = definition.get(scheme + '_color')
            if isinstance(color, str) and re.fullmatch(r'\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*', color):
                channels = [int(part.strip()) for part in color.split(',')]
                if any(channel > 255 for channel in channels):
                    continue
                values = ' '.join(map(str, channels))
                rules.append(
                    f':root[data-bs-theme="{scheme}"] {selector} '
                    f'{{ --callout-rgb: {values}; }}'
                )
        icon = CALLOUT_ICONS.get(definition.get('icon'))
        if icon:
            rules.append(f'{selector} {{ --callout-icon: url("../lib/lucide/{icon}.svg"); }}')
    return '\n'.join(rules) + ('\n' if rules else '')


def post_date(value) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        return datetime.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ExportError('笔记 date 必须为 ISO 日期或日期时间：' + str(value)) from exc


def note_title_html(title: str, subtitle: str | None = None) -> str:
    if not subtitle or subtitle == title:
        return html.escape(title)
    return ('<span class="note-title-pair"><span class="note-title-primary">'
            + html.escape(title) + '</span> <span class="note-title-secondary">'
            + html.escape(subtitle) + '</span></span>')


def folder_tree(notes: dict, section: str, baseurl: str, labels: dict,
                available_pages: set[str] | None = None) -> str:
    """Render a section's public folder hierarchy in manifest order."""
    section_prefix = section + '/'
    section_notes = {path: note for path, note in notes.items()
                     if path.startswith(section_prefix) and path != section_prefix + 'index.md'}

    def link(path: str, title: str) -> str:
        url = baseurl + '/' + page_url(path)
        subtitle = section_notes.get(path, {}).get('subtitle')
        return f'<a href="{html.escape(url, quote=True)}">{note_title_html(title, subtitle)}</a>'

    def children(folder: str, top: bool = False) -> str:
        prefix = folder + '/'
        below = {path: note for path, note in section_notes.items() if path.startswith(prefix)}
        discovered = {path[len(prefix):].split('/')[0] for path in below
                      if '/' in path[len(prefix):]}
        configured = [posixpath.basename(path) for path in labels
                      if posixpath.dirname(path) == folder
                      and (available_pages is None or path + '/index.md' in available_pages)]
        directories = list(dict.fromkeys(configured))
        directories += sorted(discovered.difference(directories), key=natural_key)
        folders = []
        for directory in directories:
            path = prefix + directory
            index = path + '/index.md'
            title = labels.get(path, section_notes.get(index, {}).get('title', directory))
            descendants = [name[len(path) + 1:] for name in below if name.startswith(path + '/')]
            subfolders = len({name.split('/')[0] for name in descendants if '/' in name})
            count = (f'{subfolders} 个子目录，' if subfolders else '') + f'{len(descendants)} 篇笔记'
            items = children(path)
            row = (
                '<span class="course-label">'
                '<i class="far fa-folder-open fa-fw course-folder-open" aria-hidden="true"></i>'
                '<i class="far fa-folder fa-fw course-folder-closed" aria-hidden="true"></i>'
                f'{link(index, title)}<span class="text-muted small">{count}</span></span>'
            )
            if items:
                header = 'card-header' if top else 'course-subfolder'
                branch = (
                    f'<details open><summary class="{header}">{row}'
                    '<span class="category-trigger" aria-hidden="true">'
                    '<i class="fas fa-fw fa-angle-down"></i></span></summary>'
                    f'<ul class="list-group">{items}</ul></details>'
                )
            else:
                # An index-only folder is a real public note, with no empty toggle.
                branch = f'<div class="course-index-only {"card-header" if top else "course-subfolder"}">{row}</div>'
            folders.append(f'<div class="card categories">{branch}</div>' if top else
                           f'<li class="list-group-item course-branch">{branch}</li>')
        leaves = [
            '<li class="list-group-item course-note">'
            '<i class="far fa-file-lines fa-fw" aria-hidden="true"></i>'
            f'{link(path, note["title"])}</li>'
            for path, note in below.items()
            if posixpath.dirname(path) == folder and path != prefix + 'index.md'
        ]
        if top and leaves:
            folders.append('<div class="card categories"><ul class="list-group">' + ''.join(leaves) + '</ul></div>')
            leaves = []
        return ''.join(folders + leaves)

    content = children(section, top=True) or '<p class="text-muted">暂无公开笔记。</p>'
    stylesheet = html.escape(baseurl + '/assets/css/course-tree.css', quote=True)
    return f'<link rel="stylesheet" href="{stylesheet}"><div class="course-tree">{content}</div>'


def course_tree(notes: dict, baseurl: str, labels: dict,
                available_pages: set[str] | None = None) -> str:
    """Render the Course tab using the shared hierarchical folder view."""
    return folder_tree(notes, 'courses', baseurl, labels, available_pages)


def section_list(notes: dict, section: str, baseurl: str, labels: dict,
                 available_pages: set[str] | None = None) -> str:
    """Render one group level, then flatten every public article below it."""
    prefix = section + '/'
    section_notes = {path: note for path, note in notes.items()
                     if path.startswith(prefix) and path != prefix + 'index.md'}

    def link(path: str, title: str) -> str:
        url = baseurl + '/' + page_url(path)
        subtitle = section_notes.get(path, {}).get('subtitle')
        return f'<a href="{html.escape(url, quote=True)}">{note_title_html(title, subtitle)}</a>'

    # Direct labels come from the configured source groups, so empty groups are
    # visible in the intended order. Any unlabelled group is appended naturally.
    groups = [path for path in labels
              if posixpath.dirname(path) == section
              and (available_pages is None or path + '/index.md' in available_pages)]
    discovered = {
        prefix + path[len(prefix):].split('/')[0]
        for path in section_notes
        if '/' in path[len(prefix):]
    }
    groups += sorted(discovered.difference(groups), key=natural_key)

    cards = []
    for group in groups:
        index = group + '/index.md'
        grouped = [(path, note) for path, note in section_notes.items()
                   if path.startswith(group + '/')]
        title = labels.get(group, section_notes.get(index, {}).get('title', posixpath.basename(group)))
        count = len(grouped)
        rows = [
            '<li class="list-group-item course-note">'
            '<i class="far fa-file-lines fa-fw" aria-hidden="true"></i>'
            f'{link(path, note["title"])}</li>'
            for path, note in grouped if path != index
        ]
        if not rows:
            rows = ['<li class="list-group-item text-muted section-empty">暂无公开笔记。</li>']
        row = (
            '<span class="course-label">'
            '<i class="far fa-folder-open fa-fw course-folder-open" aria-hidden="true"></i>'
            '<i class="far fa-folder fa-fw course-folder-closed" aria-hidden="true"></i>'
            f'{link(index, title)}<span class="text-muted small">{count} 篇笔记</span></span>'
        )
        branch = (
            f'<details open><summary class="card-header">{row}'
            '<span class="category-trigger" aria-hidden="true">'
            '<i class="fas fa-fw fa-angle-down"></i></span></summary>'
            f'<ul class="list-group">{"".join(rows)}</ul></details>'
        )
        cards.append(f'<div class="card categories">{branch}</div>')

    direct = [(path, note) for path, note in section_notes.items()
              if posixpath.dirname(path) == section]
    if direct:
        rows = ''.join(
            '<li class="list-group-item course-note">'
            '<i class="far fa-file-lines fa-fw" aria-hidden="true"></i>'
            f'{link(path, note["title"])}</li>'
            for path, note in direct
        )
        cards.append(f'<div class="card categories"><ul class="list-group">{rows}</ul></div>')

    content = ''.join(cards) or '<p class="text-muted">暂无公开笔记。</p>'
    stylesheet = html.escape(baseurl + '/assets/css/course-tree.css', quote=True)
    return (f'<link rel="stylesheet" href="{stylesheet}">'
            f'<div class="course-tree section-list">{content}</div>')


def card_headings(body: str, title: str, limit: int = 4) -> list[str]:
    """Use the main section headings, excluding examples inside callouts/code."""
    headings = []
    # Display equations can contain a line of '=' that resembles a Setext H1.
    without_math = re.sub(r'\$\$.*?\$\$|\\\[.*?\\\]', '\n\n', body, flags=re.S)
    tokens = MarkdownIt().parse(without_math)
    for i, token in enumerate(tokens):
        if token.type != 'heading_open' or token.level != 0:
            continue
        # Parse each heading on its own: malformed body HTML cannot swallow it,
        # and CommonMark fences prevent C preprocessor lines becoming headings.
        content = markdown.markdown('### ' + tokens[i + 1].content, extensions=[
            'attr_list', 'pymdownx.arithmatex'], extension_configs={
                'pymdownx.arithmatex': {'generic': True, 'smart_dollar': False}})
        heading = BeautifulSoup(content, 'html.parser')
        for formula in heading.select('.arithmatex'):
            formula.decompose()
        text = ' '.join(heading.get_text().split())
        if text and text != title:
            headings.append((int(token.tag[1]), text))
    if not headings:
        return []
    level = min(level for level, _ in headings)
    return list(dict.fromkeys(text for depth, text in headings if depth == level))[:limit]


def card_directory(source: str, labels: dict) -> list[str]:
    """Show every public folder from the section down to the note's parent."""
    parts = posixpath.dirname(source).split('/')
    sections = {'courses': 'Course', 'reading': 'Reading', 'knowledge': 'Tech'}
    return [labels.get('/'.join(parts[:i + 1]), sections.get(part, part) if i == 0 else part)
            for i, part in enumerate(parts)]


def folder_navigation(notes: dict) -> dict:
    """Link direct siblings by filename, independently of dates and nav_order."""
    folders = {}
    for path in notes:
        folders.setdefault(posixpath.dirname(path), []).append(path)
    navigation = {}
    for paths in folders.values():
        paths.sort(key=lambda path: (natural_key(posixpath.basename(path)), path))
        for i, path in enumerate(paths):
            neighbors = {}
            for direction, offset in [('previous', -1), ('next', 1)]:
                neighbor = paths[i + offset] if 0 <= i + offset < len(paths) else None
                neighbors['folder_' + direction] = (
                    {'url': '/' + page_url(neighbor), 'title': notes[neighbor]['title'],
                     **({'subtitle': notes[neighbor]['subtitle']} if notes[neighbor].get('subtitle') else {})}
                    if neighbor else None
                )
            navigation[path] = neighbors
    return navigation


def breadcrumbs(source: str, notes: dict, tabs: dict, labels: dict) -> list[dict]:
    """Follow exported folders, omitting an index page's self-link."""
    folders = source.split('/')[:-1]
    if source.endswith('/index.md'):
        folders = folders[:-1]
    trail = []
    for depth in range(1, len(folders) + 1):
        folder = '/'.join(folders[:depth])
        index = folder + '/index.md'
        if index in tabs:
            title = tabs[index][1]['title']
        else:
            title = labels.get(folder, notes.get(index, {}).get('title', folders[depth - 1]))
        trail.append({'title': title, 'url': '/' + page_url(index)})
    return trail


def stage(docs: Path, destination: Path, template: Path, settings: dict, labels: dict):
    """Build only from the exported snapshot; never needs the private Vault."""
    shutil.copytree(template, destination, dirs_exist_ok=True)
    about = destination / '_tabs/about.md'
    if about.exists():
        about.write_text(about.read_text().replace(STEAM_MARKER, steam_card(template)))
    if (docs / 'assets').exists():
        shutil.copytree(docs / 'assets', destination / 'assets', dirs_exist_ok=True)
    shutil.copy2(docs / 'publication.json', destination / 'publication.json')
    (destination / '_config.yml').write_text(yaml.safe_dump(settings, allow_unicode=True, sort_keys=False))
    manifest = json.loads((docs / 'publication.json').read_text())
    callout_css = destination / 'assets/css/obsidian-callouts.css'
    callout_css.write_text(callout_css.read_text() + '\n' + custom_callout_styles(manifest.get('callouts', {})))
    notes = {note['path']: note for note in manifest['notes']}
    available_pages = {path.relative_to(docs).as_posix() for path in docs.rglob('*.md')}
    tabs = {}
    for path in (destination / '_tabs').glob('*.html'):
        metadata, _ = frontmatter(path.read_text())
        source = metadata.pop('source_index')
        tabs[source] = (path, metadata)
    navigation = folder_navigation({path: note for path, note in notes.items()
                                    if path not in tabs and path != 'index.md'
                                    and not path.startswith('assets/')})
    for source in sorted(docs.rglob('*.md')):
        relative = source.relative_to(docs).as_posix()
        if relative == 'index.md' or relative.startswith('assets/'):
            continue
        metadata, body = frontmatter(source.read_text())
        content = render(body, relative, settings.get('baseurl', ''), metadata.get('title'))
        if relative in notes and relative.startswith('courses/') and relative.endswith('/index.md'):
            folder = posixpath.dirname(relative)
            contents = folder_tree(notes, folder, settings.get('baseurl', ''), labels, available_pages)
            content += '<section class="course-folder-index" aria-label="课程笔记"><h2>课程笔记</h2>' + contents + '</section>'
        metadata.update(render_with_liquid=False, permalink='/' + unquote(page_url(relative)))
        if relative in tabs:
            path, tab_metadata = tabs[relative]
            metadata.update(tab_metadata)
            navigation_mode = metadata.pop('navigation', None)
            if navigation_mode == 'course-tree':
                # Keep an authored section introduction, replace generated lists.
                introduction = content if relative in notes else ''
                content = introduction + course_tree(
                    notes, settings.get('baseurl', ''), labels, available_pages)
            elif navigation_mode == 'section-tree':
                introduction = content if relative in notes else ''
                section = relative.split('/')[0]
                content = introduction + folder_tree(
                    notes, section, settings.get('baseurl', ''), labels, available_pages)
            elif navigation_mode == 'section-list':
                introduction = content if relative in notes else ''
                section = relative.split('/')[0]
                content = introduction + section_list(
                    notes, section, settings.get('baseurl', ''), labels, available_pages)
        elif relative in notes:
            note = notes[relative]
            timestamp = post_date(metadata.get('date') or note['published_at'])
            identifier = hashlib.sha256(relative.encode()).hexdigest()[:12]
            path = destination / '_posts' / f'{timestamp[:10]}-{identifier}.html'
            folder = posixpath.dirname(relative)
            section = relative.split('/')[0]
            category = labels.get(folder, {'courses': 'Course', 'reading': 'Reading', 'knowledge': 'Tech'}.get(section, section))
            metadata.update(layout='post', date=timestamp, categories=[category], math=True)
            if note.get('updated_at'):
                metadata['last_modified_at'] = post_date(note['updated_at'])
            metadata.update(card_headings=card_headings(body, note['title']),
                            card_directory=card_directory(relative, labels))
            metadata.update(navigation[relative])
        else:
            path = destination / Path(relative).with_suffix('.html')
            heading = BeautifulSoup(markdown.markdown(body), 'html.parser').find('h1')
            metadata.update(layout='page', title=heading.get_text() if heading else source.parent.name)
        metadata['breadcrumbs'] = breadcrumbs(relative, notes, tabs, labels)
        write_page(path, metadata, content)
