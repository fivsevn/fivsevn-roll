"""One-time migration/recovery; never part of ordinary publication.
Download only reviewed, pinned originals. Do not overwrite or publish anything.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path,PurePosixPath
from urllib.parse import quote
import argparse,hashlib,json,requests
from content import ROOT


def restore(root=ROOT,source_root=None):
    manifest=json.loads((root/'migration/assets.json').read_text());shared=json.loads((root/'migration/shared-media.json').read_text())
    entries=[dict(r,url='https://raw.githubusercontent.com/'+manifest['source_repository']+'/'+r['source_commit']+'/'+quote(r['source_path'],safe='/')) for r in manifest['files']]+shared
    def one(row):
        relative=PurePosixPath(row['destination'])
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in {'drafts','stills','site-assets'}:raise ValueError('Unsafe destination')
        dest=root/relative
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest()!=row['sha256']:raise ValueError(f'Existing file differs: {dest}')
            return False
        if source_root and 'source_path' in row:data=(source_root/row['source_path']).read_bytes()
        else:
            response=requests.get(row['url'],timeout=90);response.raise_for_status();data=response.content
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError(f'Source mismatch: {relative}')
        dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_name(dest.name+'.download');temp.write_bytes(data);temp.replace(dest);return True
    with ThreadPoolExecutor(max_workers=8) as pool:count=sum(pool.map(one,entries))
    print(f'Restored {count} verified assets; {len(entries)} total checked')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path);restore(source_root=p.parse_args().source_root)
