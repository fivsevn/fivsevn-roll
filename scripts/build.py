"""Build only explicitly published packages into a clean, self-contained artifact."""
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from html import escape
from urllib.parse import urlparse, quote
import argparse, hashlib, json, re, shutil
from PIL import Image, ImageOps
from content import ROOT, load_posts, safe_asset


def soup(text):
    return BeautifulSoup(text, 'html.parser')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root=ROOT, base_path=''):
    if base_path and not re.fullmatch(r'/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', base_path):
        raise ValueError('Invalid base path')
    posts = load_posts(root)
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
    def write(route,title,kind,body):
        for element in body.select('[href], [src]'):
            for attr in ('href','src'):
                value=element.get(attr,'')
                if value.startswith('/') and not value.startswith('//'):element[attr]=url(value)
        page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · roll.fivsevn</title><link rel="canonical" href="https://roll.fivsevn.com{route}"><link rel="stylesheet" href="{url('/site-assets/'+kind+'.css')}"><link rel="stylesheet" href="{url('/site-assets/roll.css')}"></head><body class="wp-singular page-template-default page wp-embed-responsive wp-theme-mpho is-block-theme roll-{kind}">{body}</body></html>'''
        dest=out/route.strip('/')/'index.html';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(page)
        routes.append(route)
    def list_item(post):
        s=template('stills-item.html');a=s.select_one('h2 a');a.string=post['title'];a['href']='/stills/'+post['id']+'/'
        a['target']='_blank';a['rel']='noopener'
        time=s.select_one('time');time['datetime']=post['extra']['published_at'];time.string=post['extra'].get('display_date',post['extra']['published_at'][:10])
        s.li['class']=['wp-block-post'];return s.li
    def photos(post,collection=False):
        fragment=soup('<div class="roll-photos"></div>');target=fragment.div
        for n,item in enumerate(post['extra']['images']):
            original=safe_asset(post['_path'].parent,item['file']);rel=original.relative_to(root).as_posix();dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,dest)
            with Image.open(original) as im:
                width,height=ImageOps.exif_transpose(im).size
                # Keep originals byte-for-byte; display-only derivatives are disposable.
                if max(width,height)>1600 and not getattr(im,'is_animated',False):
                    image=ImageOps.exif_transpose(im);image.thumbnail((1600,1600));rel_display=str(Path(rel).with_suffix('.display.webp'));thumb=out/rel_display
                    image.save(thumb,'WEBP',quality=88,icc_profile=im.info.get('icc_profile',b''));width,height=image.size
                else:rel_display=rel
            fig=fragment.new_tag('figure',attrs={'class':'wp-block-image','id':f'photo-{n+1}'})
            img=fragment.new_tag('img',attrs={'src':'/'+quote(rel_display,safe='/'),'alt':item.get('alt',''),'width':width,'height':height,'loading':'lazy' if n else 'eager','decoding':'async'})
            if collection:fig.append(img)
            else:
                a=fragment.new_tag('a',attrs={'href':'/'+quote(rel,safe='/'),'aria-label':f"{post['title']} — photo {n+1}, original"});a.append(img);fig.append(a)
            target.append(fig)
        return fragment.div
    stills=[p for p in posts['stills'] if p['extra'].get('mode')!='collection']
    page=template('stills.html');ul=page.select_one('ul.wp-block-post-template')
    if not any(p['id']=='bygone' for p in posts['stills']):
        for link in page.select('a[href="/stills/bygone/"]'):link.parent.decompose()
    for post in stills:ul.append(list_item(post))
    write('/stills/','Stills','stills',page)
    for post in posts['stills']:
        if post['extra'].get('mode')=='collection':
            page=template('bygone.html');page.select_one('.wp-block-query').replace_with(photos(post,True));page.select_one('.entry-content').append(template('rights-notice.html'))
            write('/stills/'+post['id']+'/',post['title'],'bygone',page)
            continue
        page=template('stills.html');ul=page.select_one('ul.wp-block-post-template');ul.append(list_item(post))
        # Detail uses the unchanged camera/header/current roll row, followed immediately by the group.
        for banner in page.select('a[href="/stills/bygone/"]'):banner.parent.decompose()
        header=page.select_one('.entry-content').find('div',recursive=False)
        for child in list(header.children)[::-1]:
            if not getattr(child,'name',None):continue
            if 'wp-block-spacer' in child.get('class',[]):child.decompose()
            else:break
        entry=page.select_one('.entry-content');entry.append(photos(post));entry.append(template('rights-notice.html'))
        write('/stills/'+post['id']+'/',post['title'],'stills',page)
    config=json.loads((root/'site-data/youtube.json').read_text());page_size=config['page_size']
    def card(post):
        s=template('motion-card.html');s.li['class']=['wp-block-post'];s.li['id']=post['id']
        a=s.select_one('h2 a');a.string=post['title'];a['href']='/motion/'+post['id']+'/'
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
        return s.li
    motion=posts['motion'];pages=max(1,(len(motion)+page_size-1)//page_size)
    for n in range(1,pages+1):
        page=template('motion.html');ul=page.select_one('ul.wp-block-post-template')
        for post in motion[(n-1)*page_size:n*page_size]:ul.append(card(post))
        nav=page.new_tag('nav',attrs={'class':'roll-pagination','aria-label':'Motion pages'})
        for i in range(1,pages+1):
            a=page.new_tag('a',attrs={'href':'/motion/' if i==1 else f'/motion/page/{i}/'});a.string=str(i)
            if i==n:a['aria-current']='page'
            nav.append(a)
        ul.parent.append(nav);write('/motion/' if n==1 else f'/motion/page/{n}/','Motion','motion',page)
    for post in motion:
        page=template('motion.html');page.select_one('ul.wp-block-post-template').append(card(post))
        back=page.new_tag('a',href='/motion/');back.string='◁ motion';page.select_one('.entry-content').append(back)
        write('/motion/'+post['id']+'/',post['title'],'motion',page)
    def redirect(route,target):
        dest=out/route.strip('/')/'index.html';dest.parent.mkdir(parents=True,exist_ok=True);link=url(target)
        dest.write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={escape(link)}"><link rel="canonical" href="https://roll.fivsevn.com{target}"><title>Roll</title><a href="{escape(link)}">Continue to Roll</a></html>')
    redirect('/','/stills/')
    for kind in posts:
        for post in posts[kind]:
            source=post['extra'].get('source','');old=urlparse(source)
            if old.hostname=='fivsevn.com' and re.fullmatch(r'/\d{4}/\d{2}/\d{2}/[^/]+/',old.path):redirect(old.path,'/'+kind+'/'+post['id']+'/')
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
