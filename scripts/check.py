"""Validate archive integrity, image ordering and the public artifact boundary."""
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse,unquote
import argparse,hashlib,json
from content import ROOT,load_posts,public
from build import stills_page_size,photo_display_paths


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root=ROOT,base_path=''):
    posts=load_posts(root,True);out=root/'_site';errors=[]
    stills=[p for p in posts['stills'] if public(p) and p['extra'].get('mode')!='collection']
    stills_size=stills_page_size(root);stills_count=max(1,(len(stills)+stills_size-1)//stills_size)
    stills_routes=['/stills/' if number==1 else f'/stills/page/{number}/' for number in range(1,stills_count+1)]
    stills_listing_files={route.strip('/')+'/index.html' for route in stills_routes}
    stills_pages={post['id']:stills_routes[index//stills_size] for index,post in enumerate(stills)}
    motion=[p for p in posts['motion'] if public(p)]
    motion_size=json.loads((root/'site-data/youtube.json').read_text())['page_size']
    motion_count=max(1,(len(motion)+motion_size-1)//motion_size)
    # Derive expected document titles from source records and public routes,
    # independently of the rendered headings or the builder's title helper.
    page_titles={'index.html':'Stills · roll.fivsevn','404.html':'Not found · Roll'}
    for number,route in enumerate(stills_routes,start=1):
        page_titles[route.strip('/')+'/index.html']='Stills'+(f' · Page {number}' if number>1 else '')+' · roll.fivsevn'
    for number in range(1,motion_count+1):
        route='motion/index.html' if number==1 else f'motion/page/{number}/index.html'
        page_titles[route]='Motion'+(f' · Page {number}' if number>1 else '')+' · roll.fivsevn'
    for post in posts['stills']:
        if not public(post):continue
        count=1
        if post['extra'].get('mode')=='collection':
            collection_size=json.loads((root/'site-data/bygone.json').read_text())['page_size']
            count=max(1,(len(post['extra']['images'])+collection_size-1)//collection_size)
        for number in range(1,count+1):
            route='stills/'+post['id']+('/index.html' if number==1 else f'/page/{number}/index.html')
            page_titles[route]=post['title']+(f' · Page {number}' if number>1 else '')+' · roll.fivsevn'
    for post in motion:
        page_titles['motion/'+post['id']+'/index.html']=post['title']+' · roll.fivsevn'
    for route in page_titles:
        if not (out/route).is_file():errors.append(f'Missing titled page: {route}')
    manifest={'files':json.loads((root/'site-data/originals.json').read_text())}
    for row in manifest['files']:
        path=root/row['path']
        if not path.is_file() or sha(path)!=row['sha256']:errors.append(f"Archive checksum: {row['path']}")
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
        titles=s.find_all('title')
        if rel not in page_titles or len(titles)!=1 or titles[0].parent is not s.head or titles[0].get_text()!=page_titles[rel]:errors.append(f'Page title: {rel}')
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
        if rel.startswith('stills/') and rel.endswith('/index.html') and rel not in stills_listing_files:
            n=s.select_one('#rights-notice');expected=json.loads((root/'site-data/rights-notice.json').read_text())['paragraphs']
            if not n or [x.get_text() for x in n.select('p')]!=expected:errors.append(f'Rights Notice changed: {rel}')
    for index,route in enumerate(stills_routes):
        listing_path=out/route.strip('/')/'index.html'
        if not listing_path.is_file():
            errors.append(f'Missing Stills list page: {route}');continue
        listing=BeautifulSoup(listing_path.read_text(),'html.parser')
        actual=[a.get('href') for a in listing.select('ul.wp-block-post-template h2 a')]
        expected=[base_path+'/stills/'+p['id']+'/' for p in stills[index*stills_size:(index+1)*stills_size]]
        if actual!=expected:errors.append(f'Stills portfolio ordering: {route}')
        pager=listing.select_one('.roll-stills-pagination')
        if stills_count==1:
            if pager:errors.append('Single-page Stills must not show pagination')
        elif not pager or [a.get('href') for a in pager.select('a.page-numbers')]!=[base_path+value for value in stills_routes] or [a.get_text() for a in pager.select('[aria-current="page"]')]!=[str(index+1)]:
            errors.append(f'Stills pagination: {route}')
        if pager:
            previous=pager.select_one('[rel="prev"]');following=pager.select_one('[rel="next"]')
            if (index>0 and (not previous or previous.get('href')!=base_path+stills_routes[index-1])) or (index==0 and previous):errors.append(f'Stills previous page: {route}')
            if (index<stills_count-1 and (not following or following.get('href')!=base_path+stills_routes[index+1])) or (index==stills_count-1 and following):errors.append(f'Stills next page: {route}')
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
            if not back or back.get('href')!=base_path+stills_pages[p['id']]:errors.append(f"Back to Stills: {p['id']}")
        if len(images)!=len(expected):errors.append(f"Image count: {p['id']}")
        displays=photo_display_paths(p)
        for image,item in zip(images,expected):
            path=unquote(urlparse(image['src']).path);original='stills/'+p['id']+'/'+item['file']
            if path not in {base_path+'/'+original,base_path+'/'+displays[original]}:errors.append(f"Image ordering: {p['id']}: {path}")
    for index,p in enumerate(motion):
        page=BeautifulSoup((out/'motion'/p['id']/'index.html').read_text(),'html.parser')
        leave=page.find('a',string='LEAVE ROOM')
        route='/motion/' if index//motion_size==0 else f'/motion/page/{index//motion_size+1}/'
        if not leave or leave.get('href')!=base_path+route+'#'+p['id'] or not leave.has_attr('data-motion-return'):errors.append(f"Leave Motion room: {p['id']}")
        if any(a.get_text() in {'HOME','◁ motion'} and not a.find_parent('li') for a in page.select('a')):errors.append(f"Extra Motion footer navigation: {p['id']}")
    draft_hashes={r['sha256'] for r in manifest['files'] if r['role']=='draft' and Path(r['path']).suffix.lower() in {'.jpg','.jpeg','.png','.webp'}}
    for p in files:
        if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'} and sha(p) in draft_hashes:errors.append(f'Draft bytes leaked: {p}')
    if errors:raise ValueError('\n'.join(errors))
    print(f'PASS: {len(manifest["files"])} archived files; {len(files)} public files; links, order, notice, and draft exclusion')
    return True

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-path',default='');check(base_path=p.parse_args().base_path)
