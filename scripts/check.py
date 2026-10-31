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
        if rel.startswith(('stills/','motion/')):
            section=rel.split('/')[0]
            if not s.title or s.title.get_text()!=f'roll.fivsevn/{section}':errors.append(f'Page title: {rel}')
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
        expected=p['extra']['images']
        if p['extra'].get('mode')=='collection':
            config=json.loads((root/'site-data/bygone.json').read_text())
            page_size=config['page_size'];images=[]
            for number in range(1,max(1,(len(expected)+page_size-1)//page_size)+1):
                file=out/'stills'/p['id']/('index.html' if number==1 else f'page/{number}/index.html')
                collection_page=BeautifulSoup(file.read_text(),'html.parser')
                cards=collection_page.select('li.wp-block-post')
                if len(cards)!=len(expected[(number-1)*page_size:number*page_size]):errors.append(f'Bygone page size: {number}')
                if any(card.select('a') for card in cards):errors.append(f'Bygone card links: {number}')
                if collection_page.select('.wp-block-post-comments-count'):errors.append(f'Bygone comment count: {number}')
                images.extend(collection_page.select('li.wp-block-post figure img'))
        else:
            images=page.select('.roll-photos img')
            arrow=page.select_one('li.wp-block-post p.wp-block-paragraph')
            if not arrow or arrow.get_text()!='▽':errors.append(f"Expanded roll arrow: {p['id']}")
            back=page.find('a',string='viewfinder')
            if not back or back.get('href')!=base_path+'/stills/':errors.append(f"Back to Stills: {p['id']}")
        if len(images)!=len(expected):errors.append(f"Image count: {p['id']}")
        for image,item in zip(images,expected):
            name=Path(unquote(urlparse(image['src']).path)).name;original=Path(item['file']).name
            if name not in {original,str(Path(original).with_suffix('.display.webp'))}:errors.append(f"Image ordering: {p['id']}: {name}")
    for p in posts['motion']:
        if not public(p):continue
        page=BeautifulSoup((out/'motion'/p['id']/'index.html').read_text(),'html.parser')
        leave=page.find('a',string='LEAVE ROOM')
        if not leave or leave.get('href')!=base_path+'/motion/':errors.append(f"Leave Motion room: {p['id']}")
        if any(a.get_text() in {'HOME','◁ motion'} and not a.find_parent('li') for a in page.select('a')):errors.append(f"Extra Motion footer navigation: {p['id']}")
    draft_hashes={r['sha256'] for r in manifest['files'] if r['status']=='needs-review' and Path(r['source_path']).suffix.lower() in {'.jpg','.jpeg','.png','.webp'}}
    for p in files:
        if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'} and sha(p) in draft_hashes:errors.append(f'Draft bytes leaked: {p}')
    if errors:raise ValueError('\n'.join(errors))
    print(f'PASS: {len(manifest["files"])} archived files; {len(files)} public files; links, order, notice, and draft exclusion')
    return True

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-path',default='');check(base_path=p.parse_args().base_path)
