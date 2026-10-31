"""Validate archive integrity, image ordering and the public artifact boundary."""
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse,unquote
import argparse,hashlib,json
from content import ROOT,load_posts,public


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root=ROOT,base_path=''):
    posts=load_posts(root,True);out=root/'_site';errors=[]
    manifest=json.loads((root/'migration/assets.json').read_text())
    for row in manifest['files']:
        path=root/row['destination']
        if not path.is_file() or sha(path)!=row['sha256']:errors.append(f"Archive checksum: {row['destination']}")
    hidden=[kind+'/'+p['id']+'/' for kind,items in posts.items() for p in items if not public(p)]
    files=[p for p in out.rglob('*') if p.is_file()]
    for p in files:
        rel=p.relative_to(out).as_posix()
        if any(x in Path(rel).parts for x in ('drafts','migration','scripts','templates','schemas','.git','tests')) or any(rel.startswith(x) for x in hidden):errors.append(f'Nonpublic file: {rel}')
        if p.suffix not in {'.html','.css','.js','.json','.xml','.txt'}:continue
        text=p.read_text()
        if any(x in text for x in ('/drafts/','footer.rs','cdn.jsdelivr.net/gh/fivsevn/fivsevn-assets')):errors.append(f'Forbidden public reference: {rel}')
        if p.suffix!='.html':continue
        s=BeautifulSoup(text,'html.parser')
        for e in s.select('[href],[src]'):
            for a in ('href','src'):
                v=e.get(a,'');u=urlparse(v)
                if not v or v.startswith('#') or u.scheme or u.netloc:continue
                path=unquote(u.path)
                if base_path:
                    if not path.startswith(base_path+'/'):errors.append(f'Base-path mismatch: {rel}: {v}');continue
                    path=path[len(base_path):]
                target=out/path.lstrip('/') if path.startswith('/') else p.parent/path
                if not target.exists():errors.append(f'Broken link: {rel}: {v}')
        if rel.startswith('stills/') and rel.endswith('/index.html') and rel!='stills/index.html':
            n=s.select_one('#rights-notice');expected=json.loads((root/'migration/rights-notice.json').read_text())['paragraphs']
            if not n or [x.get_text() for x in n.select('p')]!=expected:errors.append(f'Rights Notice changed: {rel}')
    for p in posts['stills']:
        if not public(p):continue
        page=BeautifulSoup((out/'stills'/p['id']/'index.html').read_text(),'html.parser')
        images=page.select('.roll-photos img');expected=p['extra']['images']
        if len(images)!=len(expected):errors.append(f"Image count: {p['id']}")
        for image,item in zip(images,expected):
            name=Path(unquote(urlparse(image['src']).path)).name;original=Path(item['file']).name
            if name not in {original,str(Path(original).with_suffix('.display.webp'))}:errors.append(f"Image ordering: {p['id']}: {name}")
        if p['extra'].get('mode')=='collection' and page.select('.roll-photos a'):errors.append('Bygone images must not link to individual posts')
    draft_hashes={r['sha256'] for r in manifest['files'] if r['status']=='needs-review' and Path(r['source_path']).suffix.lower() in {'.jpg','.jpeg','.png','.webp'}}
    for p in files:
        if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'} and sha(p) in draft_hashes:errors.append(f'Draft bytes leaked: {p}')
    if errors:raise ValueError('\n'.join(errors))
    print(f'PASS: {len(manifest["files"])} archived files; {len(files)} public files; links, order, notice, and draft exclusion')
    return True

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-path',default='');check(base_path=p.parse_args().base_path)
