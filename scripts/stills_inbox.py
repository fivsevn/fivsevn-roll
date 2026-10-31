"""Remove only uploaded copies whose original bytes have been verified online."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess

from content import ROOT, public, read_post, safe_asset
from import_stills import OID, SHA256, git, path_in, read_state, validate_image


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verified_receipt(root):
    receipt_path = path_in(root, '_site/build-receipt.json')
    proof_path = path_in(root, '_site/.verified-live.json')
    if not receipt_path.is_file() or not proof_path.is_file():
        raise ValueError('Inbox cleanup requires successful live verification of this build')
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    proof = json.loads(proof_path.read_bytes())
    files = receipt.get('files') if isinstance(receipt, dict) else None
    if not isinstance(files, dict):
        raise ValueError('Invalid public build receipt')
    fingerprint = digest(json.dumps(files, sort_keys=True).encode())
    if (receipt.get('fingerprint') != fingerprint or not isinstance(proof, dict)
            or proof.get('version') != 1 or proof.get('fingerprint') != fingerprint
            or proof.get('receipt_sha256') != digest(receipt_bytes)):
        raise ValueError('Inbox cleanup proof does not match this build receipt')
    return receipt


def ancestor(root, older, newer):
    result = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', older, newer], capture_output=True)
    if result.returncode not in (0, 1):
        raise ValueError('Cannot establish inbox upload history')
    return result.returncode == 0


def head_blob(root, head, relative):
    # Compare the exact returned name: filename punctuation must not broaden deletion scope.
    for entry in git(root, 'ls-tree', '-z', head, '--', relative).split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, blob = metadata.decode('ascii').split()
        if name.decode('utf-8') == relative and mode in {'100644', '100755'} and kind == 'blob':
            return blob
    return None


def index_blob(root, relative):
    entries = [entry for entry in git(root, 'ls-files', '--stage', '-z', '--', ':(literal)' + relative).split(b'\0') if entry]
    if len(entries) != 1:
        return None
    metadata, name = entries[0].split(b'\t', 1)
    mode, blob, stage = metadata.decode('ascii').split()
    return blob if name.decode('utf-8') == relative and mode in {'100644', '100755'} and stage == '0' else None


def cleanup(root=ROOT):
    root = Path(root).resolve()
    receipt = verified_receipt(root)
    state = read_state(root)
    head = git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    pending = {}
    for event in state['events'].values():
        if not ancestor(root, event['after'], head):
            continue
        package = path_in(root, event['package'])
        index = path_in(root, event['package'] + '/index.md')
        if not index.is_file():
            continue
        post, _ = read_post(index)
        if not public(post) or post.get('module') != 'stills' or post.get('id') != event['id']:
            continue
        if not SHA256.fullmatch(receipt['files'].get('stills/' + event['id'] + '/index.html', '')):
            continue
        selected = {item.get('file') for item in post.get('extra', {}).get('images', []) if isinstance(item, dict)}
        for image in event['images']:
            relative = image['upload_path']
            upload = path_in(root, relative)
            if not upload.is_file() or not stat.S_ISREG(upload.stat().st_mode) or image['file'] not in selected:
                continue
            served = 'stills/' + event['id'] + '/' + image['file']
            if receipt['files'].get(served) != image['sha256']:
                continue
            original = safe_asset(package, image['file'])
            if digest(original.read_bytes()) != image['sha256']:
                continue
            uploaded_bytes = upload.read_bytes()
            if (digest(uploaded_bytes) != image['sha256'] or head_blob(root, head, relative) != image['blob_sha']
                    or index_blob(root, relative) != image['blob_sha']):
                continue
            last_touch = git(root, 'log', '-1', '--format=%H', '--', ':(literal)' + relative).decode().strip()
            if not OID.fullmatch(last_touch) or not ancestor(root, last_touch, event['after']):
                continue
            validate_image(uploaded_bytes, relative)
            pending[relative] = image['sha256']
    if git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip() != head:
        raise ValueError('Repository changed while planning inbox cleanup; retry after verification')
    removed = []
    for relative, expected in sorted(pending.items()):
        target = path_in(root, relative)
        if target.is_file() and stat.S_ISREG(target.stat().st_mode) and digest(target.read_bytes()) == expected:
            target.unlink()
            removed.append(relative)
    print(f'Removed {len(removed)} verified Stills upload copies; published originals remain in their packages.')
    return removed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    cleanup(parser.parse_args().root)
