"""Build only explicitly published packages into a clean, self-contained artifact."""
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from html import escape
from urllib.parse import urlparse, quote
import argparse, hashlib, json, re, shutil
from collections import Counter
from PIL import Image, ImageOps
from content import ROOT, load_posts, safe_asset
from bygone import render_pages as bygone_pages
from motion_body import render as render_body


def soup(text):
    return BeautifulSoup(text, 'html.parser')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stills_page_size(root):
    config=json.loads((root/'site-data/stills.json').read_text())
    size=config.get('page_size') if isinstance(config,dict) else None
    if type(size) is not int or size < 1:
        raise ValueError('Stills page_size must be a positive integer')
    return size


def photo_display_paths(post):
    """Keep established URLs unless a thumbnail would collide with another file."""
    originals={'stills/'+post['id']+'/'+item['file'] for item in post['extra']['images']}
    candidates=Counter(str(Path(path).with_suffix('.display.webp')) for path in originals)
    reserved=set(originals)|set(candidates)
    paths={}
    for path in sorted(originals):
        display=str(Path(path).with_suffix('.display.webp'))
        if display in originals or candidates[display]>1:
            suffix=hashlib.sha256(path.encode()).hexdigest()[:12]
            display=path+'.'+suffix+'.display.webp'
            while display in reserved:display=display+'.webp'
        paths[path]=display;reserved.add(display)
    return paths


def build(root=ROOT, base_path=''):
    if base_path and not re.fullmatch(r'/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', base_path):
        raise ValueError('Invalid base path')
    posts = load_posts(root)
    stills_size=stills_page_size(root)
    out = root/'_site'
    if out.exists(): shutil.rmtree(out)
    out.mkdir()
    shutil.copytree(root/'site-assets', out/'site-assets')
    if base_path:
        for css in (out/'site-assets').glob('*.css'):
            css.write_text(css.read_text().replace("url('/site-assets/", "url('"+base_path+"/site-assets/").replace('url("/site-assets/', 'url("'+base_path+'/site-assets/'))
    # Explicit site-assets scope. Source metadata, migration records and drafts are never copied.
    for p in (out/'site-assets').rglob('*'):
        if p.is_symlink() or p.is_file() and p.suffix.lower() not in {'.css','.js','.woff2','.woff','.ttf','.webp','.png','.svg','.ico'}:
            raise ValueError(f'Unexpected shared asset: {p}')
    shutil.copyfile(root/'CNAME',out/'CNAME')
    (out/'.nojekyll').touch()
    routes=[]
    def url(path):return base_path+path
    def template(name):return soup((root/'templates'/name).read_text())
    def stylesheet(name):return url('/site-assets/'+name+'.css')+'?v='+digest(out/'site-assets'/f'{name}.css')[:12]
    def write(route,title,kind,body,detail=False):
        frame=body.select_one('.wp-site-blocks > .wp-block-group > .wp-block-group')
        if frame:
            frame['class']=frame.get('class',[])+['roll-page-frame']
            column=frame.find('div',class_='wp-block-group',recursive=False)
            if column:column['class']=column.get('class',[])+['roll-page-column']
        for element in body.select('[href], [src]'):
            for attr in ('href','src'):
                value=element.get(attr,'')
                if value.startswith('/') and not value.startswith('//'):element[attr]=url(value)
        section='motion' if kind=='motion' else 'stills'
        scripts='';detail_class=' roll-motion-detail' if kind=='motion' and detail else ''
        if kind=='motion':
            navigation=json.dumps({'base_path':base_path,'post_pages':{key:url(value) for key,value in motion_pages.items()}}).replace('<','\\u003c')
            version=digest(out/'site-assets/motion-navigation.js')[:12]
            scripts=f'<script type="application/json" id="motion-navigation-config">{navigation}</script><script defer src="{url("/site-assets/motion-navigation.js")}?v={version}"></script>'
        page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>roll.fivsevn/{section}</title><link rel="canonical" href="https://roll.fivsevn.com{route}"><link rel="stylesheet" href="{stylesheet(kind)}"><link rel="stylesheet" href="{stylesheet('roll')}"></head><body class="wp-singular page-template-default page wp-embed-responsive wp-theme-mpho is-block-theme roll-{kind}{detail_class}">{body}{scripts}</body></html>'''
        dest=out/route.strip('/')/'index.html';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(page)
        routes.append(route)
    def pagination(page,page_routes,current,label,extra_class=''):
        nav=page.new_tag('nav',attrs={'class':('roll-pagination '+extra_class).strip(),'aria-label':label})
        if current>1:
            link=page.new_tag('a',attrs={'href':page_routes[current-2],'rel':'prev','aria-label':'Previous Page'});link.string='«';nav.append(link)
        for number,route in enumerate(page_routes,start=1):
            link=page.new_tag('a',attrs={'href':route,'class':'page-numbers'});link.string=str(number)
            if number==current:link['aria-current']='page'
            nav.append(link)
        if current<len(page_routes):
            link=page.new_tag('a',attrs={'href':page_routes[current],'rel':'next','aria-label':'Next Page'});link.string='»';nav.append(link)
        return nav
    def list_item(post,expanded=False):
        s=template('stills-item.html');a=s.select_one('h2 a');a.string=post['title'];a['href']='/stills/'+post['id']+'/'
        a['target']='_blank';a['rel']='noopener'
        if expanded:
            s.select_one('p.wp-block-paragraph').string='▽'
        time=s.select_one('time');time['datetime']=post['extra']['published_at'];time.string=post['extra'].get('display_date',post['extra']['published_at'][:10])
        s.li['class']=['wp-block-post'];return s.li
    def photos(post,collection=False):
        fragment=soup('<div class="roll-photos"></div>');target=fragment.div
        display_paths=photo_display_paths(post)
        for n,item in enumerate(post['extra']['images']):
            original=safe_asset(post['_path'].parent,item['file']);rel='stills/'+post['id']+'/'+item['file'];dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,dest)
            with Image.open(original) as im:
                width,height=ImageOps.exif_transpose(im).size
                # Keep originals byte-for-byte; display-only derivatives are disposable.
                if max(width,height)>1600 and not getattr(im,'is_animated',False):
                    image=ImageOps.exif_transpose(im);image.thumbnail((1600,1600));rel_display=display_paths[rel];thumb=out/rel_display
                    image.save(thumb,'WEBP',quality=88,icc_profile=im.info.get('icc_profile',b''));width,height=image.size
                else:rel_display=rel
            fig=fragment.new_tag('figure',attrs={'class':'wp-block-image','id':f'photo-{n+1}'})
            img=fragment.new_tag('img',attrs={'src':'/'+quote(rel_display,safe='/'),'alt':item.get('alt',''),'width':width,'height':height,'loading':'lazy' if n else 'eager','decoding':'async'})
            if collection:fig.append(img)
            else:
                a=fragment.new_tag('a',attrs={'href':'/'+quote(rel,safe='/'),'aria-label':f"{post['title']} — photo {n+1}, original"});a.append(img);fig.append(a)
            target.append(fig)
        return fragment.div
    def stills_body(post):
        rendered=render_body(post.get('_body',''))
        if not rendered:return None
        fragment=soup('<div class="roll-stills-body"></div>')
        for block in list(soup(rendered).children):fragment.div.append(block)
        return fragment.div
    stills=[p for p in posts['stills'] if p['extra'].get('mode')!='collection']
    stills_count=max(1,(len(stills)+stills_size-1)//stills_size)
    def stills_route(number):return '/stills/' if number==1 else f'/stills/page/{number}/'
    stills_pages={post['id']:stills_route(index//stills_size+1) for index,post in enumerate(stills)}
    for number in range(1,stills_count+1):
        page=template('stills.html');ul=page.select_one('ul.wp-block-post-template')
        if not any(p['id']=='bygone' for p in posts['stills']):
            for link in page.select('a[href="/stills/bygone/"]'):link.parent.decompose()
        for post in stills[(number-1)*stills_size:number*stills_size]:ul.append(list_item(post))
        if stills_count>1:
            ul.parent['class']=ul.parent.get('class',[])+['roll-stills-paged-list']
            placeholder=ul.parent.find('div',class_='wp-elements-35',recursive=False)
            if placeholder and not placeholder.find(True) and not placeholder.get_text(strip=True):placeholder.decompose()
            nav=pagination(page,[stills_route(target) for target in range(1,stills_count+1)],number,'Stills pages','roll-stills-pagination')
            ul.insert_after(nav)
        write(stills_route(number),'Stills','stills',page)
    for post in posts['stills']:
        if post['extra'].get('mode')=='collection':
            collection_pages=bygone_pages(root,post,photos(post,True),template)
            for index,(route,page) in enumerate(collection_pages):
                # Collection notes follow the complete album, once on its final page.
                if index==len(collection_pages)-1:
                    body=stills_body(post)
                    if body:page.select_one('#rights-notice').insert_before(body)
                write(route,post['title'],'bygone',page)
            continue
        page=template('stills.html');ul=page.select_one('ul.wp-block-post-template');ul.append(list_item(post,expanded=True))
        back=page.new_tag('a',attrs={'href':stills_pages[post['id']],'title':'Back to Stills'});back.string='viewfinder'
        navigation=page.new_tag('p',attrs={'class':'wp-block-paragraph roll-viewfinder','style':'font-size:10px'})
        navigation.append('◁ ');navigation.append(back)
        page.find('p',string='▽ load roll').parent.insert_before(navigation)
        # Detail uses the unchanged camera/header/current roll row, followed immediately by the group.
        for banner in page.select('a[href="/stills/bygone/"]'):banner.parent.decompose()
        header=page.select_one('.entry-content').find('div',recursive=False)
        for child in list(header.children)[::-1]:
            if not getattr(child,'name',None):continue
            if 'wp-block-spacer' in child.get('class',[]):child.decompose()
            else:break
        entry=page.select_one('.entry-content');entry.append(photos(post))
        body=stills_body(post)
        if body:entry.append(body)
        entry.append(template('rights-notice.html'))
        write('/stills/'+post['id']+'/',post['title'],'stills',page)
    config=json.loads((root/'site-data/youtube.json').read_text());page_size=config['page_size']
    motion=posts['motion'];pages=max(1,(len(motion)+page_size-1)//page_size)
    motion_pages={post['id']:('/motion/' if i//page_size==0 else f'/motion/page/{i//page_size+1}/') for i,post in enumerate(motion)}
    def card(post,detail=False):
        s=template('motion-card.html');s.li['class']=['wp-block-post'];s.li['id']=post['id'];s.li['data-motion-room']=''
        a=s.select_one('h2 a');a.string=post['title'];a['href']='/motion/'+post['id']+'/'
        if not detail:a['data-motion-open']=''
        embed=s.select_one('.entry-content');original_markup=str(embed.select_one('figure'));embed.clear()
        for v in post['extra']['video_ids']:
            figure=soup(original_markup).figure;iframe=figure.iframe
            iframe['src']=re.sub(r'/embed/[A-Za-z0-9_-]{11}', '/embed/'+v, iframe['src'])
            iframe['title']=post['title'];iframe['referrerpolicy']='strict-origin-when-cross-origin'
            iframe['allow']='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share'
            embed.append(figure)
        stamp=datetime.fromisoformat(post['extra']['published_at'])
        times=s.select('time')
        for t in times:t['datetime']=post['extra']['published_at']
        times[0].string=stamp.strftime('%M:%S');times[1].string=stamp.strftime('%m:%d')
        s.select_one('.wp-block-post-comments-count').string=str(post['extra'].get('comment_count',0))
        if detail:
            leave=s.find('a',string='LEAVE ROOM');leave['href']=motion_pages[post['id']]+'#'+quote(post['id'],safe='');leave['title']='Back to Motion';leave['data-motion-return']=''
        authored=soup(render_body(post.get('_body','')) if detail else '')
        feed=s.select_one('.roll-comment-feed')
        for block in reversed(list(authored.children)):
            if not getattr(block,'name',None):continue
            row=s.new_tag('div',attrs={'class':'wp-block-group is-layout-flex wp-block-group-is-layout-flex roll-authored-message'})
            time=s.new_tag('time',attrs={'datetime':post['extra']['published_at']});time.string=stamp.strftime('%H:%M')
            date=s.new_tag('div',attrs={'class':'wp-block-post-date','style':'font-size:11px'});date.append(time);row.append(date)
            author=s.new_tag('span',attrs={'class':'roll-comment-author'});author.string='guest_d';row.append(author)
            marker=s.new_tag('span',attrs={'class':'roll-comment-marker','aria-hidden':'true'});marker.string='>';row.append(marker)
            content=s.new_tag('div',attrs={'class':'roll-comment-body'});content.append(block);row.append(content)
            feed.insert(0,row)
        return s.li
    for n in range(1,pages+1):
        page=template('motion.html');ul=page.select_one('ul.wp-block-post-template')
        for post in motion[(n-1)*page_size:n*page_size]:ul.append(card(post))
        nav=pagination(page,['/motion/' if i==1 else f'/motion/page/{i}/' for i in range(1,pages+1)],n,'Motion pages')
        ul.parent.append(nav);write('/motion/' if n==1 else f'/motion/page/{n}/','Motion','motion',page)
    for post in motion:
        page=template('motion.html');page.select_one('ul.wp-block-post-template').append(card(post,detail=True))
        home=page.find('a',string='HOME')
        if home:home.find_parent('p').parent.decompose()
        write('/motion/'+post['id']+'/',post['title'],'motion',page,detail=True)
    def redirect(route,target):
        dest=out/route.strip('/')/'index.html';dest.parent.mkdir(parents=True,exist_ok=True);link=url(target)
        section='motion' if target.startswith('/motion/') else 'stills'
        dest.write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={escape(link)}"><link rel="canonical" href="https://roll.fivsevn.com{target}"><title>roll.fivsevn/{section}</title><a href="{escape(link)}">Continue to Roll</a></html>')
    redirect('/','/stills/')
    (out/'404.html').write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><title>Not found · Roll</title><p>This page is not published.</p><a href="{url("/stills/")}">Stills</a> · <a href="{url("/motion/")}">Motion</a></html>')
    (out/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: https://roll.fivsevn.com/sitemap.xml\n')
    (out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>https://roll.fivsevn.com'+r+'</loc></url>' for r in routes)+'</urlset>')
    files={p.relative_to(out).as_posix():digest(p) for p in sorted(out.rglob('*')) if p.is_file()}
    receipt={'version':1,'files':files,'fingerprint':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),'counts':{'stills_groups':len(stills),'bygone_photos':sum(len(p['extra']['images']) for p in posts['stills'] if p['extra'].get('mode')=='collection'),'motion_posts':len(motion)}}
    (out/'build-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt['counts']),len(files),'public files')
    return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base-path',default='');args=parser.parse_args();build(base_path=args.base_path)
