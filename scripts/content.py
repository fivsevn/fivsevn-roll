"""Offline content contract shared by the builder, sync, and validation."""
from pathlib import Path, PurePosixPath
from datetime import datetime
from zoneinfo import ZoneInfo
import json, re, yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = {'published', 'publish', 'active'}
VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
PUBLICATION_ZONE = ZoneInfo('Asia/Shanghai')


def read_post(path):
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise ValueError(f'{path}: missing frontmatter')
    header, body = text[4:].split('\n---\n', 1)
    data = yaml.safe_load(header)
    if not isinstance(data, dict):
        raise ValueError(f'{path}: metadata must be a mapping')
    return data, body


def public(post):
    return post.get('status') in PUBLISHED and post.get('visibility') == 'public'


def motion_path(root, slug, published_at):
    """Archive chronologically in Shanghai time without changing the public ID."""
    if not slug or slug in {'.', '..'} or '/' in slug or '\\' in slug:
        raise ValueError('Invalid Motion package ID')
    stamp = datetime.fromisoformat(published_at)
    if stamp.tzinfo is None:
        raise ValueError('Publication time needs timezone')
    local = stamp.astimezone(PUBLICATION_ZONE)
    folder = local.strftime('%Y-%m-%d-%H%M%S') + '-' + slug
    return root / 'motion' / local.strftime('%Y') / local.strftime('%m') / folder / 'index.md'


def stills_path(root, slug, published_at):
    """Group archive folders by publication month, keeping portfolio IDs intact."""
    if not slug or slug in {'.', '..'} or '/' in slug or '\\' in slug:
        raise ValueError('Invalid Stills package ID')
    stamp = datetime.fromisoformat(published_at)
    if stamp.tzinfo is None:
        raise ValueError('Publication time needs timezone')
    local = stamp.astimezone(PUBLICATION_ZONE)
    return root / 'stills' / local.strftime('%Y') / local.strftime('%m') / slug / 'index.md'


def safe_asset(package, relative):
    p = PurePosixPath(relative)
    if not relative.startswith('assets/') or p.is_absolute() or '..' in p.parts or '\\' in relative:
        raise ValueError(f'Unsafe asset path: {relative}')
    target = package / relative
    if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to((package / 'assets').resolve()):
        raise ValueError(f'Missing or unsafe asset: {target}')
    if any(part.is_symlink() for part in [package, *[parent for parent in target.parents if parent.is_relative_to(package)] ]):
        raise ValueError(f'Symlink not permitted: {target}')
    return target


def load_posts(root=ROOT, include_hidden=False):
    validator = Draft202012Validator(json.loads((root/'schemas/content-metadata.schema.json').read_text()), format_checker=FormatChecker())
    result = {'stills': [], 'motion': []}
    seen_videos = set()
    for kind in result:
        seen_ids=set()
        paths=(root/kind).rglob('index.md')
        for path in sorted(paths):
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(root/kind)):
                raise ValueError(f'Symlink not permitted: {path}')
            data, body = read_post(path)
            validator.validate(data)
            if data['module'] != kind or (kind == 'stills' and data['id'] != path.parent.name):
                raise ValueError(f'{path}: identity or module does not match path')
            if data['id'] in seen_ids:
                raise ValueError(f'{path}: duplicate package ID: {data["id"]}')
            seen_ids.add(data['id'])
            extra = data.get('extra', {})
            if extra.get('profile') != 'roll-post-v1':
                raise ValueError(f'{path}: expected roll-post-v1')
            stamp = datetime.fromisoformat(extra['published_at'])
            if stamp.tzinfo is None:
                raise ValueError(f'{path}: publication time requires timezone')
            if kind == 'stills' and body.strip():
                raise ValueError(f'{path}: Stills uses ordered extra.images; body rendering is not supported')
            if kind == 'stills':
                expected_path = stills_path(root, data['id'], extra['published_at'])
                if path != expected_path:
                    raise ValueError(f'{path}: Stills path must match publication year/month: {expected_path}')
                images = extra.get('images')
                if not isinstance(images, list) or not images:
                    raise ValueError(f'{path}: a group must have ordered images')
                if len({i['file'] for i in images}) != len(images):
                    raise ValueError(f'{path}: duplicate images')
                for item in images:
                    safe_asset(path.parent, item['file'])
            else:
                expected_path = motion_path(root, data['id'], extra['published_at'])
                if path != expected_path:
                    raise ValueError(f'{path}: Motion path must match publication year/month/timestamp: {expected_path}')
                ids = extra.get('video_ids', [])
                if not ids or any(not VIDEO_ID.fullmatch(v) for v in ids):
                    raise ValueError(f'{path}: invalid YouTube video IDs')
                # Historical duplicate embeds are retained. Sync never recreates any existing ID.
                seen_videos.update(ids)
            data = dict(data, _path=path, _body=body)
            if include_hidden or public(data):
                result[kind].append(data)
    history = json.loads((root/'site-data/history.json').read_text())
    for kind, posts in result.items():
        order = {slug:i for i,slug in enumerate(history[kind])}
        posts.sort(key=lambda p: (-datetime.fromisoformat(p['extra']['published_at']).timestamp(), order.get(p['id'], -1), p['id']))
    return result


def write_post(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = '---\n'+yaml.safe_dump(data, allow_unicode=True, sort_keys=False)+'---\n'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)
