from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import sys
import unittest

from bs4 import BeautifulSoup
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import build
from content import ROOT, read_post, stills_path, write_post


class StillsBodyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for folder in ('schemas', 'templates', 'site-assets', 'site-data'):
            shutil.copytree(ROOT / folder, self.root / folder)
        shutil.copyfile(ROOT / 'CNAME', self.root / 'CNAME')

    def save(self, body='', status='published', collection=False):
        slug = 'bygone' if collection else 'w-ren-min-rd-m-e'
        source = ROOT / 'stills/bygone/index.md' if collection else ROOT / 'stills/2026/06' / slug / 'index.md'
        data, _ = read_post(source)
        data['status'] = status
        data['extra']['images'] = data['extra']['images'][:2]
        path = stills_path(self.root, slug, data['extra']['published_at'])
        (path.parent / 'assets').mkdir(parents=True, exist_ok=True)
        for item in data['extra']['images']:
            Image.new('RGB', (3, 2), 'gray').save(path.parent / item['file'])
        write_post(path, data)
        with path.open('a') as stream:
            stream.write(body)
        return slug

    def page(self, route):
        return BeautifulSoup((self.root / '_site' / route / 'index.html').read_text(), 'html.parser')

    def test_group_notes_follow_photos_before_the_unchanged_notice(self):
        slug = self.save('这是一组 **街头影像**。\n\n记录当时的光线。[Motion](/motion/)\n')
        build(self.root, base_path='/preview')
        page = self.page('stills/' + slug)
        photos = page.select_one('.roll-photos')
        notes = page.select_one('.roll-stills-body')
        notice = page.select_one('#rights-notice')
        self.assertEqual(2, len(photos.select('img')))
        self.assertIs(notes, photos.find_next_sibling())
        self.assertIs(notice, notes.find_next_sibling())
        self.assertEqual('街头影像', notes.strong.get_text())
        self.assertEqual('/preview/motion/', notes.a['href'])
        expected = json.loads((ROOT / 'site-data/rights-notice.json').read_text())['paragraphs']
        self.assertEqual(expected, [p.get_text() for p in notice.select('p')])
        listing = self.page('stills')
        self.assertFalse(listing.select('.roll-stills-body'))
        self.assertNotIn('街头影像', listing.get_text())

    def test_empty_notes_add_no_placeholder_and_drafts_stay_unpublished(self):
        slug = self.save()
        build(self.root)
        self.assertFalse(self.page('stills/' + slug).select('.roll-stills-body'))
        self.save('DRAFT-STILLS-NOTES', status='draft')
        build(self.root)
        self.assertFalse((self.root / '_site/stills' / slug).exists())
        for path in (self.root / '_site').rglob('*.html'):
            self.assertNotIn('DRAFT-STILLS-NOTES', path.read_text())

    def test_collection_notes_appear_once_after_the_final_photo_page(self):
        self.save('相册的结束语。', collection=True)
        config_path = self.root / 'site-data/bygone.json'
        config = json.loads(config_path.read_text())
        config['page_size'] = 1
        config_path.write_text(json.dumps(config))
        build(self.root)
        self.assertFalse(self.page('stills/bygone').select('.roll-stills-body'))
        last = self.page('stills/bygone/page/2')
        notes = last.select_one('.roll-stills-body')
        self.assertEqual('相册的结束语。', notes.get_text())
        self.assertIs(last.select_one('#rights-notice'), notes.find_next_sibling())
        self.assertLess(str(last).index('wp-block-post-template'), str(last).index('roll-stills-body'))


if __name__ == '__main__':
    unittest.main()
