"""Adapt the same public snapshot to Astro Pure; preserve the Chirpy adapter for rollback."""
from __future__ import annotations

import json
import html
import posixpath
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup
import markdown

from scripts.exporter import frontmatter, page_url
from scripts.steam import MARKER as STEAM_MARKER, render_card as steam_card
from scripts.jekyll import (breadcrumbs, card_directory, card_headings, custom_callout_styles,
                            folder_navigation, folder_tree, note_title_html, post_date, render, section_list)


def slug(value: str) -> str:
    return re.sub(r'[^\w-]+', '-', value.lower()).strip('-')


def stage(docs: Path, work: Path, template: Path, settings: dict, labels: dict) -> Path:
    """Write data and assets in an isolated build directory; the Vault is never read."""
    public = work / 'public'
    public.mkdir(parents=True)
    manifest = json.loads((docs / 'publication.json').read_text())
    notes = {note['path']: note for note in manifest['notes']}
    baseurl = settings.get('baseurl', '')
    sections = {'courses/index.md': 'Course', 'reading/index.md': 'Reading', 'knowledge/index.md': 'Tech'}
    tabs = {path: (None, {'title': title}) for path, title in sections.items()}
    # Derive display titles from the public paths, including older snapshots.
    # Keep the original title for body rendering and directory index pages.
    for source, note in notes.items():
        if posixpath.basename(source) != 'index.md':
            title = posixpath.basename(source).removesuffix('.md')
            notes[source] = {**note, 'title': title,
                             'subtitle': note['title'] if note['title'] != title else None}
    navigation = folder_navigation({path: note for path, note in notes.items() if path not in sections})
    available = {path.relative_to(docs).as_posix() for path in docs.rglob('*.md')}
    pages = []

    for path in sorted(docs.rglob('*.md')):
        source = path.relative_to(docs).as_posix()
        if source == 'index.md' or source.startswith('assets/'):
            continue
        metadata, body = frontmatter(path.read_text())
        heading = BeautifulSoup(markdown.markdown(body), 'html.parser').find('h1')
        original_title = sections.get(source) or metadata.get('title') or (heading.get_text() if heading else posixpath.basename(source).removesuffix('.md'))
        title = notes.get(source, {}).get('title', original_title) if source not in sections else sections[source]
        subtitle = notes.get(source, {}).get('subtitle')
        content = render(body, source, baseurl, original_title, theme='pure')
        folder = posixpath.dirname(source)
        if source in sections:
            introduction = content if source in notes else ''
            tree = section_list if source.startswith('knowledge/') else folder_tree
            content = introduction + tree(notes, folder, baseurl, labels, available)
        elif source.endswith('/index.md') and source not in notes:
            tree = section_list if source.startswith('knowledge/') else folder_tree
            anchor = BeautifulSoup(content, 'html.parser').find('span', id=True, recursive=False)
            content = (str(anchor) if anchor else '') + tree(notes, folder, baseurl, labels, available)
        elif source in notes and source.startswith('courses/') and source.endswith('/index.md'):
            content += ('<section class="course-folder-index"><h2 id="course-notes">课程笔记</h2>'
                        + folder_tree(notes, folder, baseurl, labels, available) + '</section>')
        soup = BeautifulSoup(content, 'html.parser')
        for stylesheet in soup.select('link[rel="stylesheet"]'):
            stylesheet.decompose()
        content = str(soup)
        headings = [{'depth': int(h.name[1]), 'slug': h['id'], 'text': h.get_text()}
                    for h in soup.select('h2[id],h3[id],h4[id],h5[id],h6[id]')]
        record = notes.get(source, {})
        tags = metadata.get('tags', [])
        if isinstance(tags, str):
            tags = tags.split()
        pages.append({
            'route': unquote(page_url(source)).strip('/'),
            'url': baseurl + '/' + page_url(source), 'title': title, 'subtitle': subtitle, 'html': content,
            'description': metadata.get('description'), 'headings': headings,
            'breadcrumbs': breadcrumbs(source, notes, tabs, labels),
            'directory': card_directory(source, labels),
            'cardHeadings': card_headings(body, original_title),
            'publishedAt': post_date(metadata.get('date') or record['published_at']) if record else None,
            'updatedAt': post_date(record['updated_at']) if record.get('updated_at') else None,
            'tags': tags,
            'tagLinks': [{'title': tag, 'url': '/tags/' + slug(tag) + '/'} for tag in tags],
            'category': labels.get(folder, {'courses': 'Course', 'reading': 'Reading', 'knowledge': 'Tech'}.get(source.split('/')[0])),
            'isNote': source in notes and source not in sections,
            **navigation.get(source, {})
        })

    articles = [page for page in pages if page['isNote']]
    for kind, key in [('tags', 'tags'), ('categories', 'category')]:
        groups = {}
        for page in articles:
            values = page[key] if key == 'tags' else [page[key]]
            for value in values:
                groups.setdefault(value, []).append(page)
        for title, grouped in groups.items():
            route = kind + '/' + slug(title)
            body = '<ul class="archive-list">' + ''.join(
                '<li><a href="' + html.escape(page['url'], quote=True) + '">' + note_title_html(page['title'], page.get('subtitle')) + '</a></li>'
                for page in sorted(grouped, key=lambda page: page['publishedAt'], reverse=True)) + '</ul>'
            pages.append({'route': route, 'url': baseurl + '/' + route + '/', 'title': title,
                          'html': body, 'headings': [], 'breadcrumbs': [{'title': kind.title(), 'url': '/' + kind + '/'}], 'isNote': False})
        body = '<ul class="archive-list">' + ''.join(
            '<li><a href="' + baseurl + '/' + kind + '/' + slug(title) + '/">' + html.escape(title)
            + '</a> <span>' + str(len(grouped)) + '</span></li>' for title, grouped in sorted(groups.items())) + '</ul>'
        pages.append({'route': kind, 'url': baseurl + '/' + kind + '/', 'title': kind.title(),
                      'html': body, 'headings': [], 'breadcrumbs': [], 'isNote': False})

    _, about = frontmatter((template / '_tabs/about.md').read_text())
    about = about.replace(STEAM_MARKER, steam_card(template))
    about_html = BeautifulSoup(render(about, 'about/index.md', baseurl, 'About', theme='pure'), 'html.parser')
    # The shared About source also has wrappers required by the old Chirpy layout.
    for wrapper in about_html.select('article, div.content'):
        wrapper.unwrap()
    for heading in about_html.select('h1'):
        heading.decompose()
    pages.append({'route': 'about', 'url': baseurl + '/about/', 'title': 'About',
                  'html': str(about_html), 'headings': [], 'breadcrumbs': [], 'isNote': False})

    data = work / 'content.json'
    data.write_text(json.dumps({'pages': pages}, ensure_ascii=False, default=str))
    shutil.copy2(docs / 'publication.json', public / 'publication.json')
    for directory in ('images', 'lib/fonts', 'lib/fontawesome-free', 'vendor/mathjax'):
        original = template / 'assets' / directory
        if original.exists():
            shutil.copytree(original, public / 'assets' / directory)
    if (docs / 'assets').exists():
        shutil.copytree(docs / 'assets', public / 'assets', dirs_exist_ok=True)
    (public / 'assets/css').mkdir(parents=True, exist_ok=True)
    for name in ('tabsdown.css', 'obsidian-callouts.css'):
        css = (template / 'assets/css' / name).read_text()
        if name == 'obsidian-callouts.css':
            css += custom_callout_styles(manifest.get('callouts', {}))
            css = css.replace(':root[data-bs-theme="light"]', ':root:not(.dark)')
            css = css.replace(':root[data-bs-theme="dark"]', ':root.dark')
        (public / 'assets/css' / name).write_text(css)
    (public / 'assets/js').mkdir(parents=True, exist_ok=True)
    for name in ('tabsdown.js', 'steam.js'):
        shutil.copy2(template / 'assets/js' / name, public / 'assets/js' / name)
    return data
