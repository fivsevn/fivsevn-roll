"""Append exact Git-upload snapshots to the existing Bygone collection."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile

from bygone_webp import convert
from content import ROOT, PUBLICATION_ZONE, read_post
from import_stills import OID, SHA256, git, path_in, resolve_commit
from media_naming import media_filename
from site_post_metadata import dump_frontmatter, validate_metadata

INBOX = 'stills/bygone/trigger_img'
PACKAGE = 'stills/bygone'
STATE = '.publishing/bygone.json'
IGNORED = {'README.md', '.gitkeep', '.keep', '.DS_Store'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_state(root):
    path = path_in(root, STATE)
    data = json.loads(path.read_text()) if path.exists() else {'version': 1, 'items': {}, 'events': {}}
    if (not isinstance(data, dict) or data.get('version') != 1
            or not isinstance(data.get('items'), dict) or not isinstance(data.get('events'), dict)):
        raise ValueError('Invalid Bygone publishing state')
    def saved(item):
        if not isinstance(item, dict) or not SHA256.fullmatch(item.get('sha256', '')):
            raise ValueError('Invalid Bygone saved image')
        name = item.get('file', '')
        if not isinstance(name, str) or not name.startswith('assets/') or PurePosixPath(name).suffix != '.webp':
            raise ValueError('Invalid Bygone WebP path')
        path_in(root, PACKAGE + '/' + name)
    for key, item in data['items'].items():
        if not SHA256.fullmatch(key):
            raise ValueError('Invalid Bygone source digest')
        saved(item)
    for key, event in data['events'].items():
        if not isinstance(key, str) or not isinstance(event, dict) or not OID.fullmatch(event.get('after', '')):
            raise ValueError('Invalid Bygone event')
        if not isinstance(event.get('images'), list) or not event['images']:
            raise ValueError('Invalid Bygone event images')
        for image in event['images']:
            saved(image)
            if (not OID.fullmatch(image.get('blob_sha', ''))
                    or not SHA256.fullmatch(image.get('source_sha256', ''))
                    or not image.get('upload_path', '').startswith(INBOX + '/')):
                raise ValueError('Invalid Bygone upload provenance')
            path_in(root, image['upload_path'])
    return data


def tree_images(root, commit):
    entries = {}
    for record in git(root, 'ls-tree', '-r', '-z', commit, '--', INBOX + '/').split(b'\0'):
        if not record:
            continue
        header, raw = record.split(b'\t', 1)
        mode, kind, blob = header.decode('ascii').split()
        name = raw.decode('utf-8')
        path_in(root, name)
        if PurePosixPath(name).name not in IGNORED:
            entries[name] = {'upload_path': name, 'blob_sha': blob, 'mode': mode, 'kind': kind}
    return entries


def push_images(root, before, after):
    current = tree_images(root, after)
    if set(before) == {'0'} and len(before) in {40, 64}:
        return list(current.values())
    resolve_commit(root, before)
    git(root, 'merge-base', '--is-ancestor', before, after)
    changed = git(root, 'diff', '--name-only', '-z', '--no-renames', '--diff-filter=AMT', before, after,
                  '--', INBOX + '/').split(b'\0')
    return [current[value.decode('utf-8')] for value in changed if value and value.decode('utf-8') in current]


def install(root, updates, originals):
    """Install a prepared batch together, restoring files if any replacement fails."""
    with tempfile.TemporaryDirectory(prefix='.bygone-import-', dir=root) as folder:
        folder = Path(folder)
        prepared = {}
        for number, (relative, data) in enumerate(updates.items()):
            prepared[relative] = folder / str(number)
            prepared[relative].write_bytes(data)
        for relative, previous in originals.items():
            path = path_in(root, relative)
            actual = path.read_bytes() if path.exists() else None
            if actual != previous:
                raise ValueError('Bygone source changed while preparing the batch; retry')
        installed = []
        try:
            for relative, temporary in prepared.items():
                destination = path_in(root, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temporary, destination)
                installed.append(relative)
        except BaseException:
            for relative in reversed(installed):
                path = path_in(root, relative)
                if originals[relative] is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(originals[relative])
            raise


def ingest(root=ROOT, *, before=None, after=None, manual=False, stage=False):
    root = Path(root).resolve()
    head = git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    after = resolve_commit(root, after or head) if manual or after else None
    if after is None:
        raise ValueError('Bygone push publication requires exact before and after commit SHAs')
    git(root, 'merge-base', '--is-ancestor', after, head)
    state = read_state(root)
    if manual:
        processed = {(image['upload_path'], image['blob_sha']) for event in state['events'].values() for image in event['images']}
        uploads = [image for image in tree_images(root, after).values()
                   if (image['upload_path'], image['blob_sha']) not in processed]
        signature = digest(json.dumps([(i['upload_path'], i['blob_sha']) for i in sorted(uploads, key=lambda i: i['upload_path'])]).encode())
        event_key = 'manual:' + after + ':' + signature
    else:
        if not isinstance(before, str) or not OID.fullmatch(before):
            raise ValueError('Bygone push publication requires exact before and after commit SHAs')
        event_key = 'push:' + after
        if event_key in state['events']:
            return None
        uploads = push_images(root, before, after)
    if not uploads or event_key in state['events']:
        return None
    stamp = datetime.fromisoformat(git(root, 'show', '-s', '--format=%cI', after).decode().strip()).astimezone(PUBLICATION_ZONE)
    source_paths = [PACKAGE + '/index.md', 'site-data/bygone.json', 'site-data/originals.json', STATE]
    originals = {name: path_in(root, name).read_bytes() if path_in(root, name).exists() else None for name in source_paths}
    meta, body = read_post(path_in(root, PACKAGE + '/index.md'))
    if meta.get('id') != 'bygone' or meta.get('extra', {}).get('mode') != 'collection':
        raise ValueError('Bygone uploads require the existing collection package')
    config = json.loads(originals['site-data/bygone.json'])
    archive = json.loads(originals['site-data/originals.json'])
    updated = copy.deepcopy(state)
    selected = {image['file'] for image in meta['extra']['images']}
    for item in updated['items'].values():
        saved = path_in(root, PACKAGE + '/' + item['file'])
        if item['file'] not in selected or not saved.is_file() or digest(saved.read_bytes()) != item['sha256']:
            raise ValueError('Bygone publishing state refers to a changed or missing saved image')
    prefix = media_filename('stills', 'bygone', meta['extra']['published_at'], 1, '.webp').rsplit('-', 1)[0] + '-'
    number = 0
    for name in selected | {p.relative_to(path_in(root, PACKAGE)).as_posix() for p in path_in(root, PACKAGE + '/assets').iterdir()}:
        match = re.fullmatch(r'assets/' + re.escape(prefix) + r'(\d+)\.[^.]+', name)
        if match:
            number = max(number, int(match[1]))
    updates = {}
    added_images, added_cards, event_images = [], [], []
    for upload in sorted(uploads, key=lambda image: image['upload_path']):
        if upload['mode'] not in {'100644', '100755'} or upload['kind'] != 'blob':
            raise ValueError('Bygone uploads must be regular image files')
        data = git(root, 'cat-file', 'blob', upload['blob_sha'])
        encoded, _ = convert(data, upload['upload_path'])
        source_hash = digest(data)
        item = updated['items'].get(source_hash)
        if item is None:
            output_hash = digest(encoded)
            item = updated['items'].get(output_hash)
            if item is None:
                number += 1
                relative = 'assets/' + media_filename('stills', 'bygone', meta['extra']['published_at'], number, '.webp')
                destination = PACKAGE + '/' + relative
                if path_in(root, destination).exists():
                    raise ValueError('Bygone image number collides with an existing file')
                updates[destination] = encoded
                originals[destination] = None
                item = {'file': relative, 'sha256': output_hash}
                title = PurePosixPath(upload['upload_path']).stem
                added_images.append({'file': relative, 'alt': title})
                added_cards.append({'file': relative, 'title': title, 'published_at': stamp.isoformat(timespec='seconds'),
                                    'display_date': stamp.isoformat(timespec='seconds'), 'comment_count': '0'})
                archive.append({'path': destination, 'bytes': len(encoded), 'sha256': output_hash, 'role': 'post'})
            updated['items'][output_hash] = dict(item)
        updated['items'][source_hash] = dict(item)
        event_images.append({**{key: upload[key] for key in ('upload_path', 'blob_sha')},
                             'source_sha256': source_hash, **item})
    if added_images:
        meta['extra']['images'] = added_images + meta['extra']['images']
        meta['updated'] = meta['metadata_updated'] = stamp.date().isoformat()
        config['cards'] = added_cards + config['cards']
        validate_metadata(meta, site='stills', schema_dir=root/'schemas')
        updates[PACKAGE + '/index.md'] = (dump_frontmatter(meta) + body).encode()
        updates['site-data/bygone.json'] = (json.dumps(config, ensure_ascii=False, indent=2) + '\n').encode()
        updates['site-data/originals.json'] = (json.dumps(archive, ensure_ascii=False, indent=2) + '\n').encode()
    updated['events'][event_key] = {'before': before, 'after': after, 'images': event_images}
    updates[STATE] = (json.dumps(updated, ensure_ascii=False, indent=2) + '\n').encode()
    if git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip() != head:
        raise ValueError('Git history changed while preparing Bygone uploads; retry')
    install(root, updates, originals)
    if stage:
        git(root, 'add', '--', *updates)
    print(f'Published {len(added_images)} new Bygone photos; {len(event_images)} upload copies recorded.')
    return updated['events'][event_key]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event-path', type=Path)
    parser.add_argument('--manual', action='store_true')
    parser.add_argument('--stage', action='store_true')
    args = parser.parse_args()
    if args.manual:
        event = ingest(manual=True, stage=args.stage)
    else:
        if not args.event_path:
            parser.error('--event-path or --manual is required')
        payload = json.loads(args.event_path.read_text())
        event = ingest(before=payload['before'], after=payload['after'], stage=args.stage)
    if event is None:
        print('No new Bygone upload batch; the saved collection is unchanged.')


if __name__ == '__main__':
    main()
