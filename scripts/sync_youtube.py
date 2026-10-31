"""Append verified public uploads, preserving every saved package and editorial decision."""
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,re,sys
from content import ROOT,read_post,write_post,motion_path
from youtube_source import get_channel_videos,get_video_metadata,Video


def existing_ids(root):
    ids=set()
    for folder in ('motion','drafts'):
        for path in (root/folder).rglob('index.md'):
            try:post,_=read_post(path)
            except ValueError:
                if folder=='motion':raise
                continue
            ids.update(post.get('extra',{}).get('video_ids',[]))
    return ids


def plan(videos,root=ROOT):
    seen=existing_ids(root);pending=[]
    for v in videos:
        if v.video_id in seen:continue
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',v.video_id):raise ValueError('Invalid video ID')
        if not v.title.strip() or not v.published_at:raise ValueError(f'Incomplete metadata: {v.video_id}')
        stamp=datetime.fromisoformat(v.published_at.replace('Z','+00:00'))
        if stamp.tzinfo is None:raise ValueError('Publication time needs timezone')
        local=stamp.astimezone(ZoneInfo('Asia/Shanghai'));date=local.date().isoformat()
        slug_id=re.sub(r'[-_]+','-',v.video_id.lower()).strip('-') or 'video'
        slug='youtube-'+slug_id+'-'+hashlib.sha256(v.video_id.encode()).hexdigest()[:8]
        path=motion_path(root,slug,local.isoformat())
        if path.exists():raise ValueError(f'Refusing to overwrite {path}')
        pending.append((path,dict(id=slug,title=v.title,module='motion',submodule='roll',topic=None,type='log',status='published',canonical=True,summary=None,parents=[],related=[],tags=[],audience=['public'],languages=['zh','en','ja'],maturity='evolving',confidence=None,visibility='public',source_of_truth='site',filename_policy='entrypoint',created=date,updated=date,metadata_updated=date,extra={'profile':'roll-post-v1','published_at':local.isoformat(),'author':'五月七日','source':'https://www.youtube.com/watch?v='+v.video_id,'video_ids':[v.video_id]})))
        seen.add(v.video_id)
    return pending


def sync(root=ROOT):
    configured=json.loads((root/'site-data/youtube.json').read_text())['channel_id']
    channel=os.environ.get('YOUTUBE_FIVSEVN_CHANNEL_ID','').strip() or configured
    if channel!=configured:raise ValueError('Channel differs from the reviewed configuration')
    videos=get_channel_videos(channel,'fivsevn');seen=existing_ids(root)
    resolved=[get_video_metadata(v.video_id,channel) if v.video_id not in seen and not v.published_at else v for v in videos]
    pending=plan(resolved,root)
    for path,data in pending:write_post(path,data)
    print(f'{len(videos)} verified public uploads; {len(pending)} new packages; saved history preserved')
    return len(pending)

if __name__=='__main__':
    try:sync()
    except Exception as error:
        print(f'YouTube sync failed ({type(error).__name__}); history has not been removed.',file=sys.stderr)
        raise SystemExit(1)
