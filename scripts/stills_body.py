"""Parse authored album order without changing the shared text-only renderer."""
from html import escape, unescape
from pathlib import PurePosixPath
import re
from urllib.parse import quote, unquote, urlparse

from bs4 import BeautifulSoup
import markdown
from markdown.extensions.fenced_code import FencedBlockPreprocessor

from stills_document import LAYOUT_MARKER as BODY_MARKER


_MARKER_LINE = re.compile(r' {0,3}' + re.escape(BODY_MARKER) + r'[ \t]*(?:\r?\n)?\Z')


def _marker_ranges(body):
    fences = [(match.start(), match.end()) for match in FencedBlockPreprocessor.FENCED_BLOCK_RE.finditer(body)]
    offset = 0
    markers = []
    for line in body.splitlines(keepends=True):
        if _MARKER_LINE.fullmatch(line) and not any(start <= offset < end for start, end in fences):
            markers.append((offset, offset + len(line.rstrip('\r\n'))))
        offset += len(line)
    return markers


def is_body_layout(body, meta=None):
    extra = (meta or {}).get('extra', {})
    return extra.get('stills_layout') == 'body-v1' or bool(_marker_ranges(body))


def _image_path(value):
    parsed = urlparse(value)
    path = unquote(parsed.path)
    pure = PurePosixPath(path)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or not path.startswith('assets/') or '\\' in path or '\x00' in path
            or '..' in pure.parts or pure.as_posix() != path):
        raise ValueError('Stills body images must reference a local assets/ file: ' + value)
    return path


def _parse(body):
    source = body
    rendered_source = body
    for start, end in reversed(_marker_ranges(body)):
        source = source[:start] + ' ' * (end - start) + source[end:]
        rendered_source = rendered_source[:start] + rendered_source[end:]
    offset = 0
    if not source.strip():
        return [], []
    parser = markdown.Markdown(extensions=['tables', 'fenced_code', 'sane_lists'])
    fragment = BeautifulSoup(parser.convert(escape(rendered_source.strip('\r\n'), quote=False)), 'html.parser')
    raw_parser = markdown.Markdown(extensions=['tables', 'fenced_code', 'sane_lists'])
    raw_parser.convert(rendered_source)
    blocks, actual = [], []
    for node in list(fragment.children):
        if not getattr(node, 'name', None):
            continue
        images = node.find_all('img')
        if images:
            if (node.name != 'p' or any(image.parent is not node for image in images)
                    or any(getattr(child, 'name', None) != 'img' and str(child).strip() for child in node.children)):
                raise ValueError('Put Stills body images on separate lines, apart from text and links')
            references = [{'file': image.get('src', ''), 'alt': image.get('alt', '')} for image in images]
            actual.extend(references)
            if blocks and blocks[-1]['kind'] == 'photos':
                blocks[-1]['images'].extend(references)
            else:
                blocks.append({'kind': 'photos', 'images': references})
        else:
            for link in node.select('a[href]'):
                if urlparse(link['href']).scheme not in {'', 'https', 'http', 'mailto'}:
                    del link['href']
            if blocks and blocks[-1]['kind'] == 'text':
                blocks[-1]['html'] += '\n' + str(node)
            else:
                blocks.append({'kind': 'text', 'html': str(node)})

    # The Markdown parser decides which nodes are images. Source positions are
    # collected only for standalone image lines, outside actual fenced code.
    fences = [(match.start(), match.end()) for match in parser.preprocessors['fenced_code_block'].FENCED_BLOCK_RE.finditer(source)]
    positions = []
    line_start = 0
    for raw in source.splitlines(keepends=True):
        line = raw.rstrip('\r\n')
        if not any(start <= line_start < end for start, end in fences) and re.match(r' {0,3}!\[', line):
            cursor = len(line) - len(line.lstrip(' '))
            pending = []
            while cursor < len(line):
                result = None
                for name in ('image_link', 'image_reference', 'short_image_ref'):
                    processor = raw_parser.inlinePatterns[name]
                    match = processor.getCompiledRegExp().match(line, cursor)
                    if match:
                        element, start, end = processor.handleMatch(match, line)
                        if element is not None:
                            _, alt_end, _ = processor.getText(line, match.end())
                            prefix = line[start:alt_end]
                            path = _image_path(unescape(element.get('src', '')))
                            # Native image parsing preserves authored alt entities and
                            # escaped punctuation; text blocks keep the old escaping.
                            image = BeautifulSoup(markdown.markdown(prefix + '(' + quote(path, safe='/.-_~') + ')'), 'html.parser').img
                            result = {'start': offset + line_start + start, 'end': offset + line_start + end,
                                      'prefix': prefix, 'title': element.get('title'),
                                      'file': path, 'alt': image.get('alt', '')}
                            break
                if result is None:
                    break
                pending.append(result)
                cursor = end
                while cursor < len(line) and line[cursor].isspace():
                    cursor += 1
            if cursor == len(line):
                positions.extend(pending)
        line_start += len(raw)
    if len(positions) != len(actual):
        raise ValueError('Use standalone Markdown image lines: ![description](assets/file)')
    for image, position in zip(actual, positions):
        image.update(file=position['file'], alt=position['alt'])
    return blocks, [{**image, **position} for image, position in zip(actual, positions)]


def body_images(body):
    """Return actual body image references and their exact source ranges."""
    return _parse(body)[1]


def rewrite_image_paths(body, mapping):
    """Rename only image references, retaining authored alt syntax and other text."""
    for image in reversed(body_images(body)):
        target = mapping.get(image['file'])
        if target is None or target == image['file']:
            continue
        title = image['title']
        suffix = '' if title is None else ' "' + unescape(title).replace('\\', '\\\\').replace('"', '\\"') + '"'
        replacement = image['prefix'] + '(' + quote(target, safe='/.-_~') + suffix + ')'
        body = body[:image['start']] + replacement + body[image['end']:]
    return body


def parse_layout(body, resources):
    """Resolve body order against the full inventory; unreferenced resources stay saved."""
    blocks, _ = _parse(body)
    inventory = {item['file']: item for item in resources}
    selected = set()
    for block in blocks:
        if block['kind'] != 'photos':
            continue
        resolved = []
        for image in block['images']:
            if image['file'] in selected:
                raise ValueError('Duplicate Stills body image reference: ' + image['file'])
            selected.add(image['file'])
            if image['file'] not in inventory:
                raise ValueError('Stills body image is absent from the resource inventory: ' + image['file'])
            resolved.append({**inventory[image['file']], 'alt': image['alt']})
        block['images'] = resolved
    return blocks


def display_images(blocks):
    return [image for block in blocks if block['kind'] == 'photos' for image in block['images']]
