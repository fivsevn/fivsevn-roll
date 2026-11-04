"""Clear Bygone inputs only after their converted WebP has been verified live."""
from pathlib import Path
import stat

from content import ROOT, public, read_post, safe_asset
from import_bygone import INBOX, PACKAGE, digest, read_state
from import_stills import OID, git, path_in
from stills_inbox import ancestor, head_blob, index_blob, verified_receipt


def cleanup(root=ROOT):
    root = Path(root).resolve()
    receipt = verified_receipt(root)
    state = read_state(root)
    head = git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    post, _ = read_post(path_in(root, PACKAGE + '/index.md'))
    if not public(post):
        return []
    selected = {image['file'] for image in post['extra']['images']}
    pending = {}
    for event in state['events'].values():
        if not ancestor(root, event['after'], head):
            continue
        for image in event['images']:
            relative = image['upload_path']
            upload = path_in(root, relative)
            if not upload.is_file() or not stat.S_ISREG(upload.stat().st_mode) or image['file'] not in selected:
                continue
            served = PACKAGE + '/' + image['file']
            if receipt['files'].get(served) != image['sha256']:
                continue
            if digest(safe_asset(path_in(root, PACKAGE), image['file']).read_bytes()) != image['sha256']:
                continue
            if (digest(upload.read_bytes()) != image['source_sha256']
                    or head_blob(root, head, relative) != image['blob_sha']
                    or index_blob(root, relative) != image['blob_sha']):
                continue
            touched = git(root, 'log', '-1', '--format=%H', '--', ':(literal)' + relative).decode().strip()
            if not OID.fullmatch(touched) or not ancestor(root, touched, event['after']):
                continue
            pending[relative] = image['source_sha256']
    if git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip() != head:
        raise ValueError('Git history changed while planning Bygone cleanup')
    removed = []
    for relative, expected in sorted(pending.items()):
        upload = path_in(root, relative)
        if upload.is_file() and digest(upload.read_bytes()) == expected:
            upload.unlink()
            removed.append(relative)
    print(f'Removed {len(removed)} verified Bygone upload copies.')
    return removed


if __name__ == '__main__':
    cleanup()
