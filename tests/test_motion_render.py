from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import sys
import unittest
import json
from bs4 import BeautifulSoup

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build import build
from content import ROOT,load_posts,motion_path,write_post


class MotionRoomTests(unittest.TestCase):
    def setUp(self):
        self.temporary=TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        for folder in ['schemas','templates','site-assets','site-data']:
            shutil.copytree(ROOT/folder,self.root/folder)
        shutil.copyfile(ROOT/'CNAME',self.root/'CNAME')
        self.post={k:v for k,v in load_posts(ROOT)['motion'][0].items() if not k.startswith('_')}
        self.path=motion_path(self.root,self.post['id'],self.post['extra']['published_at'])

    def render(self,body='',status='published'):
        self.post['status']=status
        write_post(self.path,self.post)
        with self.path.open('a') as stream:stream.write(body)
        build(self.root,base_path='/preview')
        page=self.root/'_site/motion'/self.post['id']/'index.html'
        return BeautifulSoup(page.read_text(),'html.parser') if page.exists() else None

    def test_markdown_is_first_in_feed_and_room_navigation_returns_to_list(self):
        page=self.render('这里是 **拍摄记录**。\n\n第二段 [链接](https://example.com)。\n')
        feed=page.select_one('.roll-comment-feed')
        messages=feed.select('.roll-authored-message')
        self.assertEqual(2,len(messages))
        self.assertIs(feed.find(recursive=False),messages[0])
        self.assertEqual('拍摄记录',messages[0].strong.get_text())
        self.assertEqual('guest_d',messages[0].select_one('.roll-comment-author').get_text())
        self.assertLess(str(feed).index('拍摄记录'),str(feed).index('guest_507'))
        self.assertEqual('/preview/motion/#'+self.post['id'],page.find('a',string='LEAVE ROOM')['href'])
        self.assertFalse(any(a.get_text() in {'HOME','◁ motion'} and not a.find_parent('li') for a in page.select('a')))
        listing=BeautifulSoup((self.root/'_site/motion/index.html').read_text(),'html.parser')
        self.assertFalse(listing.select('.roll-authored-message'))
        self.assertNotIn('拍摄记录',listing.get_text())

    def test_detail_fallback_returns_to_its_current_list_page_and_card(self):
        posts=load_posts(ROOT)['motion'][:2]
        for post in posts:
            data={k:v for k,v in post.items() if not k.startswith('_')}
            path=motion_path(self.root,data['id'],data['extra']['published_at'])
            write_post(path,data)
            with path.open('a') as stream:stream.write('DETAIL-ONLY-MOTION-TEXT')
        config_path=self.root/'site-data/youtube.json'
        config=json.loads(config_path.read_text());config['page_size']=1
        config_path.write_text(json.dumps(config))
        build(self.root,base_path='/preview')
        page=BeautifulSoup((self.root/'_site/motion'/posts[1]['id']/'index.html').read_text(),'html.parser')
        self.assertEqual('/preview/motion/page/2/#'+posts[1]['id'],page.select_one('[data-motion-return]')['href'])
        self.assertIn('roll-motion-detail',page.body['class'])
        navigation=json.loads(page.select_one('#motion-navigation-config').string)
        self.assertEqual('/preview/motion/page/2/',navigation['post_pages'][posts[1]['id']])
        listing=BeautifulSoup((self.root/'_site/motion/page/2/index.html').read_text(),'html.parser')
        self.assertEqual(posts[1]['id'],listing.select_one('[data-motion-room]')['id'])
        self.assertEqual('/preview/motion/'+posts[1]['id']+'/',listing.select_one('[data-motion-open]')['href'])
        self.assertNotIn('DETAIL-ONLY-MOTION-TEXT',listing.get_text())
        self.assertIn('DETAIL-ONLY-MOTION-TEXT',page.select_one('.roll-comment-feed').get_text())

    def test_empty_body_has_no_placeholder_and_hidden_text_is_not_published(self):
        page=self.render()
        self.assertFalse(page.select('.roll-authored-message'))
        self.assertIsNone(self.render('UNPUBLISHED-MOTION-TEXT',status='hidden'))
        for path in (self.root/'_site').rglob('*.html'):
            self.assertNotIn('UNPUBLISHED-MOTION-TEXT',path.read_text())


if __name__=='__main__':unittest.main()
