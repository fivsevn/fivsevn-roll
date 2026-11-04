#!/usr/bin/env python3
"""Prepare ordinary Stills albums without changing their original image bytes.

``extra.images`` is the complete, persistent resource inventory.  The marked
Markdown body controls which resources are shown and their display order.
Previously inventoried images are never automatically added back to the body.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image, UnidentifiedImageError

from content import ROOT, safe_asset, stills_path
from media_naming import EXTENSIONS, media_filename, media_prefix
from site_post_metadata import read_frontmatter, validate_metadata
from stills_body import body_images, is_body_layout, rewrite_image_paths
from stills_document import LAYOUT_MARKER, compose_document, image_reference


FORMATS = {
    '.jpg': {'JPEG'}, '.jpeg': {'JPEG'}, '.png': {'PNG'},
    '.webp': {'WEBP'}, '.gif': {'GIF'},
}


@dataclass
class PackagePlan:
    source: Path
    before: bytes
    after: bytes
    renames: list[tuple[Path, Path]]
    added: list[str]
    migrated: bool


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def validate_image(path):
    """Decode every frame for validation only; never save/reencode an image."""
    try:
        with Image.open(path) as image:
            if image.format not in FORMATS[path.suffix.lower()]:
                raise ValueError('Image extension does not match its data: ' + str(path))
            for frame in range(getattr(image, 'n_frames', 1)):
                image.seek(frame)
                image.load()
    except (OSError, UnidentifiedImageError, EOFError, Image.DecompressionBombError) as error:
        raise ValueError('Invalid or unsupported Stills original: ' + str(path)) from error


def _regular_tree(package):
    assets = package / 'assets'
    if not assets.is_dir() or assets.is_symlink():
        raise ValueError('Stills assets must be a real directory: ' + str(assets))
    files = []
    casefolded = set()
    for path in sorted(assets.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink not permitted in Stills assets: ' + str(path))
        if not path.is_dir() and not path.is_file():
            raise ValueError('Stills assets must contain regular files: ' + str(path))
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        if path.suffix.lower() not in FORMATS:
            raise ValueError('Ordinary Stills supports JPG, PNG, WebP, and GIF originals: ' + str(path))
        relative = path.relative_to(package).as_posix()
        if any(ord(char) < 32 or ord(char) == 127 for char in relative):
            raise ValueError('Control characters are not permitted in image paths')
        if relative.casefold() in casefolded:
            raise ValueError('Case-insensitive Stills filename collision: ' + relative)
        casefolded.add(relative.casefold())
        safe_asset(package, relative)
        validate_image(path)
        files.append(path)
    return files


def _append_images(body, images):
    if not images:
        return body
    separator = '\n\n' if body.rstrip() else ''
    return body.rstrip() + separator + '\n\n'.join(image_reference(item) for item in images) + '\n'


def plan_package(root, source):
    before = source.read_bytes()
    meta, body = read_frontmatter(source)
    if not meta:
        raise ValueError('Missing Stills frontmatter: ' + str(source))
    if meta.get('id') == 'bygone' or meta.get('extra', {}).get('mode') == 'collection':
        return None
    validate_metadata(meta, site='stills', schema_dir=root / 'schemas')
    if source != stills_path(root, meta['id'], meta['extra']['published_at']):
        raise ValueError('Stills package identity or publication path mismatch: ' + str(source))
    package = source.parent
    extra = meta['extra']
    known = extra.get('images')
    if not isinstance(known, list) or not known:
        raise ValueError('A Stills album requires its original image inventory')
    if any(not isinstance(item, dict) or not isinstance(item.get('file'), str) for item in known):
        raise ValueError('Invalid Stills image inventory: ' + str(source))
    inventory = {item['file']: deepcopy(item) for item in known}
    if len(inventory) != len(known):
        raise ValueError('Duplicate Stills inventory image: ' + str(source))
    files = _regular_tree(package)
    prefix = media_prefix('stills', meta['id'], extra['published_at'])
    pattern = re.compile(re.escape(prefix) + r'-([0-9]{3,})\.(jpg|png|webp|gif|heic|heif|avif|tif|tiff|bmp)')
    used = set()
    normalized = {}
    for path in files:
        match = pattern.fullmatch(path.name)
        if match and int(match[1]) > 0:
            number = int(match[1])
            if number in used:
                raise ValueError('Duplicate Stills image number: ' + str(path))
            used.add(number)
            normalized[path.relative_to(package).as_posix()] = path
    for relative, item in inventory.items():
        original = safe_asset(package, relative)
        if relative not in normalized:
            raise ValueError('Refusing to rename an already inventoried original: ' + relative)
        if 'sha256' in item and item['sha256'] != digest(original):
            raise ValueError('Original image checksum changed: ' + relative)

    next_number = max(used, default=0) + 1
    renames = []
    mapping = {}
    added = []
    for path in files:
        relative = path.relative_to(package).as_posix()
        if relative in inventory:
            continue
        destination = path
        if relative not in normalized:
            destination = package / 'assets' / media_filename('stills', meta['id'], extra['published_at'], next_number, path.suffix)
            next_number += 1
            if destination.exists() or destination.is_symlink():
                raise ValueError('Refusing to overwrite a Stills asset: ' + str(destination))
            renames.append((path, destination))
        saved = destination.relative_to(package).as_posix()
        if saved.casefold() in {name.casefold() for name in inventory}:
            raise ValueError('Stills resource filename collision: ' + saved)
        mapping[relative] = saved
        item = {'file': saved, 'alt': path.name, 'sha256': digest(path)}
        inventory[saved] = item
        added.append(saved)

    body = rewrite_image_paths(body, mapping)
    migrated = not is_body_layout(body, meta)
    references = body_images(body)
    referenced = [item['file'] for item in references]
    if len(set(referenced)) != len(referenced):
        raise ValueError('Duplicate Stills body image: ' + str(source))
    unknown = set(referenced) - set(inventory)
    if unknown:
        raise ValueError('Unknown Stills body image: ' + ', '.join(sorted(unknown)))
    if migrated:
        if not references:
            original_body = body
            body = _append_images(LAYOUT_MARKER, list(inventory.values()))
            if original_body.strip():
                body = body.rstrip() + '\n\n' + original_body.lstrip('\n')
        else:
            body = LAYOUT_MARKER + '\n\n' + body.lstrip('\n')
            body = _append_images(body, [inventory[name] for name in added if name not in referenced])
    else:
        body = _append_images(body, [inventory[name] for name in added if name not in referenced])
    extra['images'] = list(inventory.values())
    extra['stills_layout'] = 'body-v1'
    validate_metadata(meta, site='stills', schema_dir=root / 'schemas')
    # This also rejects unsupported body syntax before any filesystem mutation.
    final_references = body_images(body)
    if len({item['file'] for item in final_references}) != len(final_references):
        raise ValueError('Duplicate Stills body image: ' + str(source))
    after = compose_document(meta, body).encode('utf-8')
    return PackagePlan(source, before, after, renames, added, migrated)


def _git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace').strip())
    return result.stdout


def prepare(root=ROOT, *, stage=False):
    """Validate all albums, then apply one rollback-safe set of preparations."""
    root = Path(root).resolve()
    stills = root / 'stills'
    if stills.is_symlink():
        raise ValueError('Symlink not permitted: ' + str(stills))
    plans = []
    seen = set()
    for source in sorted(stills.rglob('index.md')):
        if source.is_relative_to(stills / 'bygone'):
            continue
        if source.is_symlink() or any(parent.is_symlink() for parent in source.parents if parent.is_relative_to(stills)):
            raise ValueError('Symlink not permitted: ' + str(source))
        plan = plan_package(root, source)
        if plan is not None:
            name = source.parent.name
            if name in seen:
                raise ValueError('Duplicate Stills package ID: ' + name)
            seen.add(name)
            plans.append(plan)
    changes = [plan for plan in plans if plan.before != plan.after or plan.renames]
    paths = set()
    for plan in changes:
        paths.add(plan.source.relative_to(root).as_posix())
        paths.update((plan.source.parent / name).relative_to(root).as_posix() for name in plan.added)
        for source, destination in plan.renames:
            paths.add(destination.relative_to(root).as_posix())
            if stage and _git(root, 'ls-files', '--', ':(literal)' + source.relative_to(root).as_posix()).strip():
                paths.add(source.relative_to(root).as_posix())
    index = None
    old_index = None
    if stage and changes:
        index = Path(os.fsdecode(_git(root, 'rev-parse', '--git-path', 'index').strip()))
        if not index.is_absolute():
            index = root / index
        old_index = index.read_bytes() if index.exists() else None
    moved, written = [], []
    try:
        with tempfile.TemporaryDirectory(prefix='.roll-stills-prepare-', dir=root) as temporary:
            for number, plan in enumerate(changes):
                # Fail closed if an editor or another process changed a planned input.
                if plan.source.read_bytes() != plan.before:
                    raise ValueError('Stills document changed during preparation: ' + str(plan.source))
                for source, destination in plan.renames:
                    if destination.exists() or destination.is_symlink():
                        raise ValueError('Stills target appeared during preparation: ' + str(destination))
                    source.rename(destination)
                    moved.append((source, destination))
                pending = Path(temporary) / str(number)
                pending.write_bytes(plan.after)
                shutil.copymode(plan.source, pending)
                os.replace(pending, plan.source)
                written.append(plan)
            if stage and paths:
                _git(root, 'add', '-A', '--', *(':(literal)' + path for path in sorted(paths)))
    except BaseException:
        for plan in reversed(written):
            plan.source.write_bytes(plan.before)
        for source, destination in reversed(moved):
            destination.rename(source)
        if index is not None:
            if old_index is None:
                index.unlink(missing_ok=True)
            else:
                index.write_bytes(old_index)
        raise
    return {
        'albums': len(plans), 'changed': len(changes),
        'migrated': sum(plan.migrated for plan in plans),
        'added': sum(len(plan.added) for plan in plans),
        'renamed': [{'from': source.relative_to(root).as_posix(), 'to': destination.relative_to(root).as_posix()}
                    for plan in plans for source, destination in plan.renames],
        'paths': sorted(paths),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--stage', action='store_true', help='Stage exactly the files changed by this preparation')
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, stage=args.stage), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
