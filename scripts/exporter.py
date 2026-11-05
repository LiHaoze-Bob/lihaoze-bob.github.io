"""从明确指定的 Obsidian 目录导出公开笔记；不会写回源文件。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
import hashlib
import html
import json
import os
import posixpath
import re
import unicodedata
import yaml
from markdown_it import MarkdownIt

from scripts.tabsdown import TabsdownError, parse as parse_tabsdown, serialize as serialize_tabsdown, transform_blocks


class ExportError(Exception):
    pass


@dataclass
class Note:
    source: Path
    destination: str
    metadata: dict
    published: bool
    title: str
    order: float = 1000


def frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r'\A\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)', text, re.S)
    if not match:
        return {}, text
    try:
        metadata = yaml.safe_load(match[1]) or {}
    except yaml.YAMLError as exc:
        raise ExportError('YAML 属性格式错误') from exc
    if not isinstance(metadata, dict):
        raise ExportError('笔记属性必须为键值结构')
    return metadata, text[match.end():]


def slug(text: str) -> str:
    text = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unicodedata.normalize('NFKC', html.unescape(text)).lower()
    return re.sub(r'[\s-]+', '-', re.sub(r'[^\w\s-]', '', text)).strip('-') or 'section'


def page_url(destination: str) -> str:
    """Match the generator's directory URLs, including published index notes."""
    if destination == 'index.md':
        return './'
    path = destination[:-8] if destination.endswith('/index.md') else destination.removesuffix('.md') + '/'
    return quote(path, safe='/.-_~')

class Protected:
    def __init__(self, text: str):
        self.prefix = 'SITELITERAL' + hashlib.sha256(text.encode()).hexdigest()[:10]
        self.values: dict[str, str] = {}

    def put(self, value: str) -> str:
        key = self.prefix + str(len(self.values)) + 'END'
        self.values[key] = value
        return key

    def restore(self, text: str) -> str:
        for key, value in reversed(list(self.values.items())):
            text = text.replace(key, value)
        return text

    def protect(self, text: str) -> str:
        lines = text.splitlines(keepends=True)
        protected_lines = set()
        for token in MarkdownIt().parse(text):
            if token.type == 'fence' and token.info.strip().split(' ')[0] in {'dataview', 'dataviewjs', 'query', 'embed'}:
                raise ExportError(f'不支持动态内容：{token.info}')
            if token.type in {'fence', 'code_block'} and token.map:
                protected_lines.update(range(*token.map))
        for i in protected_lines:
            # 保留引用前缀，让提示块转换可以正常去掉 >；代码内容原样恢复。
            match = re.match(r'^((?:[ \t]*>[ \t]?)*)', lines[i])
            prefix = match[0]
            value = lines[i][len(prefix):].removesuffix('\n')
            lines[i] = prefix + self.put(value) + ('\n' if lines[i].endswith('\n') else '')
        text = ''.join(lines)
        text = re.sub(r'(`+)(?!`)([^\n]*?)(?<!`)\1(?!`)', lambda m: self.put(m[0]), text)
        def protect_math(match):
            rows = match[0].split('\n')
            result = [self.put(rows[0])]
            for row in rows[1:]:
                prefix = re.match(r'^((?:[ \t]*>[ \t]?)*)', row)[0]
                result.append(prefix + self.put(row[len(prefix):]))
            prefix = match.string[:match.start()].rsplit('\n', 1)[-1]
            prefix = prefix if re.fullmatch(r'[ \t>]*', prefix) else ''
            # Python Markdown 的块公式需要段落边界；Obsidian 通常不要求。
            return '\n' + prefix + '\n' + prefix + '\n'.join(result) + '\n' + prefix + '\n' + prefix
        text = re.sub(r'\$\$.*?\$\$', protect_math, text, flags=re.S)
        def protect_inline_math(match):
            # 单美元公式允许在 Obsidian 中换行；网站导出合并行内空白。
            value = re.sub(r'\n[ \t]*(?:>[ \t]*)*', ' ', match[0])
            return self.put(value)
        text = re.sub(r'(?<![\\$])\$(?!\$)(?:\\.|(?!\n\s*\n)[^$])+?\$(?!\$)', protect_inline_math, text)
        text = re.sub(r'%%.*?%%', '', text, flags=re.S)
        return text


def convert_callouts(text: str) -> str:
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        match = re.match(r'^([ \t]*)>\s*\[!\s*([\w-]+)\s*\]([+-])?\s*(.*)$', lines[i])
        if not match:
            result.append(lines[i]); i += 1; continue
        indent, kind, fold, title = match.groups()
        output_indent = indent if len(indent.expandtabs(4)) >= 4 else ''
        # Obsidian supports custom callout identifiers. Keep the authored type so
        # aliases and Callout Manager definitions retain their own title/style.
        kind = kind.lower()
        marker = {'-': '???', '+': '???+'}.get(fold, '!!!')
        header = output_indent + marker + ' ' + kind
        if title:
            header += ' ' + json.dumps(title, ensure_ascii=False)
        result.extend(['', header])
        i += 1
        body = []
        while i < len(lines):
            quote_line = re.match(r'^' + re.escape(indent) + r'>[ \t]?(.*)$', lines[i])
            if quote_line:
                body.append(quote_line[1]); i += 1
            elif (not lines[i].strip() and i + 1 < len(lines)
                  and re.match(r'^' + re.escape(indent) + r'>', lines[i + 1])
                  and not re.match(r'^' + re.escape(indent) + r'>[ \t]*\[![\w-]+\]', lines[i + 1])):
                body.append(''); i += 1
            else:
                break
        nested = convert_callouts('\n'.join(body))
        result.extend(output_indent + '    ' + line if line else '' for line in nested.split('\n'))
        result.append('')
    return '\n'.join(result)


class Exporter:
    def __init__(self, vault: Path, config: dict, template: Path):
        self.vault = vault.resolve()
        self.config = config
        self.template = template
        self.notes: list[Note] = []
        self.warnings: list[str] = []
        self.assets: dict[str, bytes] = {}
        self.callouts = self.custom_callouts()
        self.roots: list[tuple[Path, str]] = []
        for item in config['sources']:
            source = Path(item['path'])
            destination = item['destination']
            if source.is_absolute() or '..' in source.parts or destination.startswith('/') or '..' in Path(destination).parts:
                raise ExportError('目录配置必须是安全的相对路径')
            path = self.vault / source
            if path.is_symlink() or not path.resolve().is_relative_to(self.vault):
                raise ExportError('源目录不能使用指向外部的符号链接')
            self.roots.append((path.resolve(), destination))

    def custom_callouts(self) -> dict:
        """Read presentation-only custom callouts from Obsidian Callout Manager."""
        path = self.vault / '.obsidian/plugins/callout-manager/data.json'
        if not path.is_file():
            return {}
        try:
            callouts = json.loads(path.read_text()).get('callouts', {})
            custom = callouts.get('custom', [])
            settings = callouts.get('settings', {})
        except (OSError, json.JSONDecodeError, AttributeError):
            return {}
        result = {}
        for value in custom:
            kind = str(value).lower()
            if not re.fullmatch(r'[\w-]+', kind):
                continue
            definition = {}
            rules = settings.get(value, settings.get(kind, []))
            if not isinstance(rules, list):
                rules = []
            for rule in rules:
                if not isinstance(rule, dict) or not isinstance(rule.get('changes'), dict):
                    continue
                changes = rule['changes']
                scheme = rule.get('condition', {}).get('colorScheme') if isinstance(rule.get('condition', {}), dict) else None
                if isinstance(changes.get('icon'), str):
                    definition['icon'] = changes['icon']
                if isinstance(changes.get('color'), str) and scheme in {None, 'light', 'dark'}:
                    if scheme is None:
                        definition['light_color'] = changes['color']
                        definition['dark_color'] = changes['color']
                    else:
                        definition[scheme + '_color'] = changes['color']
            result[kind] = definition
        return result

    def discover(self) -> None:
        destinations = set()
        source_roots = {root for root, _ in self.roots}
        for root, destination in self.roots:
            if not root.is_dir():
                raise ExportError(f'配置的源目录不存在：{root.name}')
            for current, directories, filenames in os.walk(root, followlinks=False):
                # Nested configured sources own their subtree, preserving their URLs
                # regardless of whether the parent or child appears first in config.
                directories[:] = sorted(
                    d for d in directories
                    if not d.startswith('.') and d != 'node_modules'
                    and not (Path(current) / d).is_symlink()
                    and (Path(current) / d).resolve() not in source_roots
                )
                for filename in sorted(filenames):
                    path = Path(current) / filename
                    if filename.startswith('.') or path.suffix.lower() != '.md' or path.is_symlink():
                        continue
                    # 未公开笔记仅读取属性区，以建立链接索引。
                    with path.open(encoding='utf-8-sig') as handle:
                        first = handle.readline()
                        header = first
                        if first.strip() == '---':
                            for _ in range(2048):
                                line = handle.readline()
                                header += line
                                if not line or line.strip() == '---':
                                    break
                    try:
                        metadata, _ = frontmatter(header)
                    except ExportError:
                        if re.search(r'^publish\s*:', header, re.M):
                            raise ExportError(f'{path.name}：YAML 属性格式错误')
                        metadata = {}
                    published = metadata.get('publish') is True
                    if 'publish' in metadata and not isinstance(metadata['publish'], bool):
                        raise ExportError(f'{path.name}：publish 只能是 true 或 false')
                    title = str(metadata.get('title') or path.stem)
                    if published:
                        _, body = frontmatter(path.read_text())
                        if not body.strip():
                            raise ExportError(f'{path.name} 已标记公开，但没有正文')
                        heading = re.search(r'^#\s+(.+)$', body, re.M)
                        if not metadata.get('title') and heading:
                            title = heading[1].strip()
                    order = metadata.get('nav_order', 1000)
                    if published and (not isinstance(order, (int, float)) or isinstance(order, bool)):
                        raise ExportError(f'{path.name}：nav_order 必须是数字')
                    target = destination + '/' + path.relative_to(root).as_posix()
                    if published and target in destinations:
                        raise ExportError(f'重复输出路径：{target}')
                    if published:
                        destinations.add(target)
                    self.notes.append(Note(path.resolve(), target, metadata, published, title, order if isinstance(order, (int, float)) else 1000))

    def resolve_note(self, target: str, current: Note) -> Note | None:
        target = unquote(target).replace('\\', '/')
        if not target:
            return current
        stem_target = target.removesuffix('.md')
        # 完整路径/相对路径优先，无路径双链只在同级优先后尝试唯一名称。
        candidates_paths = [(current.source.parent / (stem_target + '.md')).resolve(), (self.vault / (stem_target + '.md')).resolve()]
        for candidate in candidates_paths:
            matches = [n for n in self.notes if n.source == candidate]
            if matches:
                return matches[0]
        matches = []
        if '/' not in stem_target:
            for note in self.notes:
                aliases = note.metadata.get('aliases') or []
                if isinstance(aliases, str):
                    aliases = [aliases]
                if note.source.stem == stem_target or stem_target in aliases:
                    matches.append(note)
        else:
            matches = [n for n in self.notes if n.source.relative_to(self.vault).as_posix().removesuffix('.md').endswith('/' + stem_target)]
        if len(matches) > 1:
            raise ExportError(f'{current.title}：链接 {target!r} 存在多个匹配，请使用完整路径')
        return matches[0] if matches else None

    def relative(self, destination: str, note: Note) -> str:
        return quote(posixpath.relpath(destination, posixpath.dirname(note.destination)), safe='/.-_~')

    def image(self, target: str, note: Note) -> str:
        target = unquote(target)
        candidate = (note.source.parent / target).resolve()
        roots = [root for root, _ in self.roots]
        if not candidate.is_file():
            candidates = []
            # 短文件名仅在配置过的源目录内查找，不能取第一个碰巧同名的文件。
            if '/' not in target:
                for root in roots:
                    for p in root.rglob(target):
                        if p.is_file() and not p.is_symlink() and not any(part.startswith('.') for part in p.relative_to(root).parts):
                            candidates.append(p.resolve())
            candidates = list(dict.fromkeys(candidates))
            if len(candidates) > 1:
                raise ExportError(f'{note.title}：同名图片 {target!r} 有多个匹配')
            if not candidates:
                raise ExportError(f'{note.title}：找不到图片 {target!r}')
            candidate = candidates[0]
        if not any(candidate.is_relative_to(root) for root in roots):
            raise ExportError(f'{note.title}：图片超出配置目录：{target!r}')
        if any(part.startswith('.') for part in candidate.relative_to(self.vault).parts):
            raise ExportError('不能发布隐藏目录中的图片')
        if candidate.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.avif'}:
            raise ExportError(f'{note.title}：第一版不支持此附件：{target!r}')
        data = candidate.read_bytes()
        name = 'assets/notes/' + hashlib.sha256(data).hexdigest()[:20] + candidate.suffix.lower()
        self.assets[name] = data
        return self.relative(name, note)

    def local_link(self, target: str, label: str, is_image: bool, note: Note) -> str:
        parts = urlsplit(target)
        if parts.scheme in {'http', 'https', 'mailto', 'tel'} or target.startswith('//'):
            return ('!' if is_image else '') + '[' + label + '](' + target + ')'
        if parts.scheme or target.startswith('/') or parts.query:
            raise ExportError(f'{note.title}：不支持本地资源地址 {target!r}')
        if is_image:
            if parts.fragment:
                raise ExportError(f'{note.title}：图片不支持嵌入片段')
            return '![' + label + '](' + self.image(parts.path, note) + ')'
        linked = self.resolve_note(parts.path, note)
        if linked is None:
            raise ExportError(f'{note.title}：找不到链接目标 {target!r}')
        if not linked.published:
            self.warnings.append(f'{note.title}：未公开的链接已转为文字：{label}')
            return label
        anchor = ''
        if parts.fragment:
            if unquote(parts.fragment).startswith('^'):
                raise ExportError(f'{note.title}：暂不支持块引用，请改为标题链接')
            anchor = '#' + quote(slug(unquote(parts.fragment)), safe='-')
        return '[' + label + '](' + (self.relative(linked.destination, note) if parts.path else '') + anchor + ')'

    def _convert_fragment(self, note: Note, body: str, seen: dict[str, int]) -> str:
        protected = Protected(body)

        def tabsdown(block):
            try:
                tabs = parse_tabsdown(block.source)
            except TabsdownError as exc:
                line = block.start_line + exc.line
                raise ExportError(f'{note.title}：Tabsdown 第 {line} 行：{exc}') from exc
            for tab in tabs.tabs:
                tab.body = self._convert_fragment(note, tab.body, seen).strip()
            serialized = serialize_tabsdown(tabs)
            # 一行一个占位符，保留引用前缀，避免后续提示块转换破坏围栏。
            return '\n'.join(block.prefix + protected.put(line)
                             for line in serialized.splitlines())

        try:
            text = transform_blocks(body, tabsdown)
        except TabsdownError as exc:
            raise ExportError(f'{note.title}：Tabsdown 第 {exc.line} 行：{exc}') from exc
        text = protected.protect(text)
        def wiki(match):
            embedded, content = match.groups()
            target, _, alias = content.partition('|')
            label = alias or target.split('#')[0] or note.title
            if embedded:
                extension = Path(target.split('#')[0]).suffix.lower()
                if extension not in {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.avif'}:
                    raise ExportError(f'{note.title}：暂不支持笔记或附件嵌入：{target}')
                dimensions = re.fullmatch(r'(\d+)(?:x(\d+))?', alias)
                rendered = self.local_link(target, '' if dimensions else (alias or Path(target).stem), True, note)
                if dimensions:
                    rendered += '{ width="' + dimensions[1] + '"' + (' height="' + dimensions[2] + '"' if dimensions[2] else '') + ' }'
            else:
                rendered = self.local_link(target, label, False, note)
            return protected.put(rendered)
        text = re.sub(r'(!?)\[\[([^\]\n]+)\]\]', wiki, text)
        # 带括号的文件名、<含空格路径>、可选 title，均在这里解析。
        pattern = re.compile(r'(!?)\[([^\]\n]*)\]\(')
        cursor = 0
        rendered = []
        while match := pattern.search(text, cursor):
            rendered.append(text[cursor:match.start()])
            i, depth, escaped = match.end(), 1, False
            while i < len(text) and depth:
                ch = text[i]
                if escaped:
                    escaped = False
                elif ch == '\\':
                    escaped = True
                elif ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                i += 1
            if depth:
                raise ExportError(f'{note.title}：Markdown 链接括号未闭合')
            value = text[match.end():i-1].strip()
            title_match = re.search(r'''\s+(["'])(.*?)\1$''', value)
            title = title_match[2] if title_match else None
            if title_match:
                value = value[:title_match.start()].strip()
            value = value.removeprefix('<').removesuffix('>')
            value = re.sub(r'\\([() ])', r'\1', value)
            result = self.local_link(value, match[2], bool(match[1]), note)
            if title is not None and result.endswith(')'):
                result = result[:-1] + ' ' + json.dumps(title, ensure_ascii=False) + ')'
            rendered.append(protected.put(result))
            cursor = i
        text = ''.join(rendered) + text[cursor:]
        # 引用式链接在使用处转换；未公开目标只保留文字，未使用的定义不复制附件。
        reference_env = {}
        MarkdownIt().parse(text, reference_env)
        # MarkdownIt's core parser sees footnotes as reference definitions;
        # leave them for the Markdown footnotes extension at render time.
        references = {key: value for key, value in reference_env.get('references', {}).items()
                      if not key.startswith('^')}
        rows = text.splitlines(keepends=True)
        for definition in references.values():
            for index in range(*definition['map']):
                rows[index] = '\n'
        text = ''.join(rows)
        def reference(match):
            embedded, label, identifier = match.groups()
            key = re.sub(r'\s+', ' ', identifier or label).strip().upper()
            definition = references.get(key)
            if definition is None:
                return match[0]
            result = self.local_link(definition['href'], label, bool(embedded), note)
            if definition.get('title') and result.endswith(')'):
                result = result[:-1] + ' ' + json.dumps(definition['title'], ensure_ascii=False) + ')'
            return protected.put(result)
        text = re.sub(r'(!?)\[([^\]\n]+)\](?:\[([^\]\n]*)\])?', reference, text)
        text = convert_callouts(text)
        # 显式锚点使中文标题的链接不依赖生成器的默认 slug 算法。
        def heading(match):
            prefix, title = match.groups()
            existing = re.search(r'\{#([\w-]+)\}\s*$', title)
            if existing:
                return match[0]
            plain = protected.restore(title)
            ident = slug(re.sub(r'\s+#+\s*$', '', plain))
            count = seen.get(ident, 0)
            seen[ident] = count + 1
            if count:
                ident += '-' + str(count)
            return prefix + title + ' {#' + ident + '}'
        text = re.sub(r'^(#{1,6}\s+)(.+)$', heading, text, flags=re.M)
        text = re.sub(r'^[ \t]+$', '', text, flags=re.M)
        return protected.restore(text)

    def convert(self, note: Note) -> str:
        _, body = frontmatter(note.source.read_text())
        text = self._convert_fragment(note, body, {})
        metadata = {k: note.metadata[k] for k in ['description', 'tags', 'source', 'source_author', 'date'] if k in note.metadata}
        metadata['title'] = note.title
        return '---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).rstrip() + '\n---\n' + text.strip() + '\n'

    def export(self, destination: Path, publication_dates: dict | None = None) -> dict:
        self.discover()
        published = sorted((n for n in self.notes if n.published), key=lambda n: (n.order, natural_key(n.destination)))
        destination.mkdir(parents=True, exist_ok=True)
        content_hashes = {}
        for note in published:
            output = destination / note.destination
            output.parent.mkdir(parents=True, exist_ok=True)
            content = self.convert(note)
            output.write_text(content)
            content_hashes[note.destination] = hashlib.sha256(content.encode()).hexdigest()
        for path, data in self.assets.items():
            output = destination / path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        labels = self.config.get('labels', {})
        configured_destinations = [item['destination'].strip('/') for item in self.config['sources']]
        def directory_nav(folder: str):
            children = [n for n in published if posixpath.dirname(n.destination) == folder]
            below = [n for n in published if n.destination.startswith(folder + '/')]
            discovered = {n.destination[len(folder)+1:].split('/')[0] for n in below
                          if '/' in n.destination[len(folder)+1:]}
            configured = [posixpath.basename(path) for path in configured_destinations
                          if posixpath.dirname(path) == folder]
            # Configured source groups stay visible even before their first note is
            # published. Keep their declared order, then append nested note folders.
            directories = list(dict.fromkeys(configured))
            directories += sorted(discovered.difference(directories), key=natural_key)
            title = labels.get(folder, {'courses': '课程笔记', 'knowledge': '知识积累', 'reading': '阅读记录'}.get(folder, folder.split('/')[-1]))
            index = folder + '/index.md'
            if any(n.destination == index for n in published):
                # 公开的 index.md 本身担任目录首页，不覆盖原笔记。
                items = [index]
            else:
                entries = ['# ' + title, '']
                for directory in directories:
                    path = folder + '/' + directory
                    entries.append('- [' + labels.get(path, directory) + '](' + quote(directory, safe='') + '/index.md)')
                entries += ['- [' + n.title + '](' + quote(posixpath.basename(n.destination), safe='') + ')' for n in children]
                if not below and not directories:
                    entries.append('暂无公开笔记。')
                output = destination / index
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text('\n'.join(entries) + '\n')
                items = [index]
            for directory in directories:
                child_folder = folder + '/' + directory
                items.append({labels.get(child_folder, directory): directory_nav(child_folder)})
            items += [{n.title: n.destination} for n in children if n.destination != index]
            return items
        sections = [('courses', '课程笔记'), ('reading', '阅读记录'), ('knowledge', '技术积累')]
        for folder, _ in sections:
            directory_nav(folder)
        (destination / 'index.md').write_text('# ' + self.config['site']['name'] + '\n')
        # 首次发布时间不变；只在已发布笔记的公开内容发生变化时刷新更新时间。
        history = publication_dates or {}
        now = datetime.now().astimezone().isoformat(timespec='seconds')
        records = []
        for note in published:
            previous = history.get(note.destination, {})
            # Keep accepting the old path -> date mapping used by callers/tests.
            if isinstance(previous, str):
                previous = {'published_at': previous}
            content_hash = content_hashes[note.destination]
            record = {
                'path': note.destination,
                'title': note.title,
                'published_at': previous.get('published_at', now),
                'content_hash': content_hash,
            }
            updated_at = previous.get('updated_at')
            if previous.get('content_hash') and previous['content_hash'] != content_hash:
                updated_at = now
            if updated_at:
                record['updated_at'] = updated_at
            records.append(record)
        manifest = {'notes': records,
                    'images': sorted(self.assets),
                    'callouts': self.callouts}
        (destination / 'publication.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        return manifest


def natural_key(value: str):
    return [(1, int(part)) if part.isdigit() else (0, part.casefold()) for part in re.split(r'(\d+)', value)]
