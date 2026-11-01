"""Publish one explicitly uploaded Stills image batch per GitHub push.

Only stills/trigger_imgs is an inbox. Images are read from the push's exact Git
snapshot, so later uploads cannot change an older batch. The state and complete
packages are saved together; retrying an event never rewrites editorial changes.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import warnings

from PIL import Image
from media_naming import media_filename
from site_post_metadata import normalize_metadata, validate_metadata
from content import ROOT, PUBLICATION_ZONE, write_post

INBOX = 'stills/trigger_imgs'
STATE = '.publishing/stills.json'
OID = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
FORMATS = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP', '.gif': 'GIF'}
IGNORED = {'README.md', '.gitkeep', '.keep', '.DS_Store'}
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
    if result.returncode:
        raise ValueError('Git operation failed: ' + result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def path_in(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or '\x00' in relative:
        raise ValueError('Unsafe publication path')
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != relative:
        raise ValueError('Unsafe publication path: ' + relative)
    target = Path(root).joinpath(*path.parts)
    current = Path(root)
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Symlink publication path: ' + relative)
    if not target.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Publication path leaves repository')
    return target


def read_state(root):
    path = path_in(root, STATE)
    if not path.exists():
        return {'version': 1, 'events': {}}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('events'), dict):
        raise ValueError('Invalid Stills publishing state')
    for key, event in data['events'].items():
        if not isinstance(key, str) or not isinstance(event, dict) or not OID.fullmatch(event.get('after', '')):
            raise ValueError('Invalid Stills event')
        ident = event.get('id', '')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}-\d{6}-[0-9a-f]{12}', ident):
            raise ValueError('Invalid Stills event ID')
        package = event.get('package', '')
        if package != f'stills/{ident[:4]}/{ident[5:7]}/{ident}':
            raise ValueError('Invalid Stills package path')
        path_in(root, package)
        images = event.get('images')
        if not isinstance(images, list) or not images:
            raise ValueError('Invalid Stills event images')
        for image in images:
            if not isinstance(image, dict) or not OID.fullmatch(image.get('blob_sha', '')) or not SHA256.fullmatch(image.get('sha256', '')):
                raise ValueError('Invalid Stills image provenance')
            upload = image.get('upload_path', '')
            if not upload.startswith(INBOX + '/'):
                raise ValueError('Invalid Stills image inbox path')
            path_in(root, upload)
            saved = image.get('file', '')
            if not isinstance(saved, str) or not saved.startswith('assets/') or PurePosixPath(saved).suffix.lower() not in FORMATS:
                raise ValueError('Invalid Stills saved image path')
            path_in(root, package + '/' + saved)
    return data


def resolve_commit(root, value):
    if not isinstance(value, str) or not OID.fullmatch(value):
        raise ValueError('An exact Git commit SHA is required')
    resolved = git(root, 'rev-parse', '--verify', value + '^{commit}').decode().strip()
    if resolved != value:
        raise ValueError('Commit SHA did not resolve exactly')
    return value


def tree_images(root, commit):
    entries = {}
    raw = git(root, 'ls-tree', '-r', '-z', commit, '--', INBOX + '/')
    for record in raw.split(b'\0'):
        if not record:
            continue
        header, filename = record.split(b'\t', 1)
        mode, kind, blob = header.decode('ascii').split()
        name = filename.decode('utf-8')
        path_in(root, name)
        if not name.startswith(INBOX + '/') or PurePosixPath(name).name in IGNORED:
            continue
        entries[name] = {'upload_path': name, 'blob_sha': blob, 'mode': mode, 'kind': kind}
    return entries


def push_images(root, before, after):
    if set(before) == {'0'} and len(before) in {40, 64}:
        return list(tree_images(root, after).values())
    resolve_commit(root, before)
    git(root, 'merge-base', '--is-ancestor', before, after)
    names = git(root, 'diff', '--name-only', '-z', '--no-renames', '--diff-filter=AMT', before, after, '--', INBOX + '/').split(b'\0')
    current = tree_images(root, after)
    return [current[name.decode('utf-8')] for name in names if name and name.decode('utf-8') in current]


def validate_image(data, path):
    extension = PurePosixPath(path).suffix.lower()
    if extension not in FORMATS:
        raise ValueError('Unsupported Stills upload: ' + path + '; use JPG/JPEG, PNG, WebP or GIF')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as picture:
                if picture.format != FORMATS[extension]:
                    raise ValueError('Filename extension does not match image data')
                picture.verify()
            with Image.open(BytesIO(data)) as picture:
                for frame in range(getattr(picture, 'n_frames', 1)):
                    picture.seek(frame)
                    picture.load()
    except Exception as error:
        raise ValueError('Invalid Stills image: ' + path + ': ' + str(error)) from error


def ingest(root=ROOT, *, before=None, after=None, manual=False, stage=False):
    root = Path(root).resolve()
    head = git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    if not manual and after is None:
        raise ValueError('Push publication requires exact before and after commit SHAs')
    after = resolve_commit(root, after or head)
    git(root, 'merge-base', '--is-ancestor', after, head)
    state = read_state(root)
    if manual:
        current = tree_images(root, after)
        processed = {(image['upload_path'], image['blob_sha']) for event in state['events'].values() for image in event['images']}
        uploads = [image for image in current.values() if (image['upload_path'], image['blob_sha']) not in processed]
        signature = hashlib.sha256(json.dumps([(x['upload_path'], x['blob_sha']) for x in sorted(uploads, key=lambda x:x['upload_path'])], ensure_ascii=False).encode()).hexdigest()
        event_key = 'manual:' + after + ':' + signature
        before = None
    else:
        if not isinstance(before, str) or not OID.fullmatch(before):
            raise ValueError('Push publication requires exact before and after commit SHAs')
        event_key = 'push:' + after
        if event_key in state['events']:
            return None
        uploads = push_images(root, before, after)
    if not uploads or event_key in state['events']:
        return None
    uploads.sort(key=lambda image: image['upload_path'])
    stamp = datetime.fromisoformat(git(root, 'show', '-s', '--format=%cI', after).decode().strip()).astimezone(PUBLICATION_ZONE)
    ident = stamp.strftime('%Y-%m-%d-%H%M%S') + '-' + hashlib.sha256(event_key.encode()).hexdigest()[:12]
    package = f'stills/{stamp:%Y/%m}/{ident}'
    destination = path_in(root, package)
    if destination.exists():
        raise ValueError('Refusing to overwrite existing Stills package: ' + package)
    date = stamp.date().isoformat()
    meta = dict(id=ident, title=f'{stamp.day:02d} {MONTHS[stamp.month-1]}, {stamp.year} {stamp:%H:%M}',
                module='stills', submodule='roll', topic=None, type='log', status='published', canonical=True,
                summary=None, parents=[], related=[], tags=[], audience=['public'], languages=['zh','en','ja'],
                maturity='evolving', confidence=None, visibility='public', source_of_truth='site',
                filename_policy='entrypoint', created=date, updated=date, metadata_updated=date,
                extra={'profile':'site-post-v1', 'published_at':stamp.isoformat(timespec='seconds'),
                       'display_date':date, 'author':'guest_d', 'images':[], 'upload_event':event_key})
    event = {'id':ident, 'published_at':meta['extra']['published_at'], 'before':before, 'after':after,
             'package':package, 'images':[]}
    paths = []
    with tempfile.TemporaryDirectory(prefix='.roll-stills-', dir=root) as temporary:
        pending = Path(temporary) / ident
        pending.mkdir()
        for number, upload in enumerate(uploads, 1):
            name = upload['upload_path']
            if upload['mode'] not in {'100644', '100755'} or upload['kind'] != 'blob':
                raise ValueError('Stills upload must be a regular image, not a symlink or submodule: ' + name)
            data = git(root, 'cat-file', 'blob', upload['blob_sha'])
            validate_image(data, name)
            relative = 'assets/' + media_filename('stills', ident, stamp, number, PurePosixPath(name).suffix)
            target = path_in(pending, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            meta['extra']['images'].append({'file':relative, 'alt':PurePosixPath(name).name,
                                           'source_path':name, 'source_commit':after, 'sha256':digest})
            event['images'].append({'upload_path':name, 'blob_sha':upload['blob_sha'], 'sha256':digest, 'file':relative})
            paths.append(package + '/' + relative)
        meta = normalize_metadata(meta, site='stills')
        validate_metadata(meta, site='stills', schema_dir=root/'schemas')
        write_post(pending/'index.md', meta)
        paths.append(package + '/index.md')
        updated = copy.deepcopy(state)
        updated['events'][event_key] = event
        state_path = path_in(root, STATE)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        old_state = state_path.read_bytes() if state_path.exists() else None
        temporary_state = Path(temporary)/'state.json'
        temporary_state.write_text(json.dumps(updated, ensure_ascii=False, indent=2)+'\n')
        destination.parent.mkdir(parents=True, exist_ok=True)
        installed = False
        try:
            pending.rename(destination)
            installed = True
            os.replace(temporary_state, state_path)
        except BaseException:
            if installed:
                destination.rename(pending)
            if old_state is None:
                state_path.unlink(missing_ok=True)
            else:
                state_path.write_bytes(old_state)
            raise
    paths.append(STATE)
    if stage:
        git(root, 'add', '--', *paths)
    print(f'Published {len(uploads)} uploaded images as Stills group {ident}; original bytes and filenames retained.')
    return event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--before')
    parser.add_argument('--after')
    parser.add_argument('--event-path', type=Path, help='GitHub push event JSON; its full before/after range is one group')
    parser.add_argument('--manual', action='store_true', help='Explicitly publish all currently unprocessed inbox files as one group')
    parser.add_argument('--stage', action='store_true', help='Stage only the exact generated package and state for the workflow')
    args = parser.parse_args()
    before, after = args.before, args.after
    if args.event_path:
        if args.manual or before or after:
            parser.error('--event-path cannot be combined with --manual/--before/--after')
        event = json.loads(args.event_path.read_text())
        if event.get('ref') != 'refs/heads/main' or event.get('deleted') or event.get('forced'):
            raise ValueError('Stills automatic import only accepts a normal main-branch push')
        before, after = event.get('before'), event.get('after')
    if ingest(args.root, before=before, after=after, manual=args.manual, stage=args.stage) is None:
        print('No new Stills upload batch; saved groups are unchanged.')


if __name__ == '__main__':
    main()
