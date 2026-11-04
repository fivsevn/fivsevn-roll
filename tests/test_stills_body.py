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

    def save(self, body='', status='published', collection=False, title=None):
        slug = 'bygone' if collection else 'w-ren-min-rd-m-e'
        source = ROOT / 'stills/bygone/index.md' if collection else ROOT / 'stills/2026/06' / slug / 'index.md'
        data, _ = read_post(source)
        data['status'] = status
        if title is not None:
            data['title'] = title
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
        title = '中文 & <光影> "双引号" \'单引号\' </title><script>window.titleInjected=true</script>'
        slug = self.save('这是一组 **街头影像**。\n\n记录当时的光线。[Motion](/motion/)\n', title=title)
        build(self.root, base_path='/preview')
        page = self.page('stills/' + slug)
        self.assertEqual(1, len(page.find_all('title')))
        self.assertEqual(title + ' · roll.fivsevn', page.title.get_text())
        self.assertFalse(page.head.find_all('script'))
        self.assertFalse(page.find('script', string='window.titleInjected=true'))
        self.assertEqual('https://roll.fivsevn.com/stills/' + slug + '/', page.select_one('link[rel="canonical"]')['href'])
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
        self.save('相册的结束语。', collection=True, title='Bygone & 回忆')
        config_path = self.root / 'site-data/bygone.json'
        config = json.loads(config_path.read_text())
        config['page_size'] = 1
        config_path.write_text(json.dumps(config))
        build(self.root)
        first = self.page('stills/bygone')
        self.assertEqual(1, len(first.find_all('title')))
        self.assertEqual('Bygone & 回忆 · roll.fivsevn', first.title.get_text())
        self.assertFalse(first.select('.roll-stills-body'))
        last = self.page('stills/bygone/page/2')
        self.assertEqual(1, len(last.find_all('title')))
        self.assertEqual('Bygone & 回忆 · Page 2 · roll.fivsevn', last.title.get_text())
        notes = last.select_one('.roll-stills-body')
        self.assertEqual('相册的结束语。', notes.get_text())
        self.assertIs(last.select_one('#rights-notice'), notes.find_next_sibling())
        self.assertLess(str(last).index('wp-block-post-template'), str(last).index('roll-stills-body'))

    def test_bygone_keeps_original_resolution_without_changing_album_derivatives(self):
        self.save(collection=True)
        collection, _ = read_post(self.root/'stills/bygone/index.md')
        photo = collection['extra']['images'][0]['file']
        Image.new('RGB', (1701, 900), 'gray').save(self.root/'stills/bygone'/photo, 'WEBP', lossless=True)
        slug = self.save()
        album, _ = read_post(self.root/'stills/2026/06'/slug/'index.md')
        original = self.root/'stills/2026/06'/slug/album['extra']['images'][0]['file']
        Image.new('RGB', (1701, 900), 'gray').save(original)
        original_bytes = original.read_bytes()
        build(self.root)
        shown = self.page('stills/bygone').select_one('li.wp-block-post figure img')
        self.assertEqual(shown['src'], '/stills/bygone/'+photo)
        self.assertEqual((shown['width'], shown['height']), ('1701', '900'))
        self.assertFalse(list((self.root/'_site/stills/bygone/assets').glob('*.display.webp')))
        album_image = self.page('stills/'+slug).select_one('.roll-photos img')
        self.assertTrue(album_image['src'].endswith('.display.webp'))
        self.assertEqual(album_image['width'], '1600')
        self.assertEqual((self.root/'_site/stills'/slug/album['extra']['images'][0]['file']).read_bytes(), original_bytes)
        self.assertEqual(original.read_bytes(), original_bytes)

    def test_bygone_rejects_unlisted_jpeg_but_allows_pending_inbox_originals(self):
        self.save(collection=True)
        inbox = self.root/'stills/bygone/trigger_img'
        inbox.mkdir()
        pending = inbox/'pending.jpg'
        Image.new('RGB', (3, 2), 'gray').save(pending)
        build(self.root)
        self.assertTrue((self.root/'_site/stills/bygone/index.html').exists())
        self.assertTrue(pending.exists())
        manual = self.root/'stills/bygone/assets/manual.jpg'
        Image.new('RGB', (3, 2), 'gray').save(manual)
        originals = {path: path.read_bytes() for path in (self.root/'stills/bygone').rglob('*') if path.is_file()}
        with self.assertRaisesRegex(ValueError, 'Bygone.*WebP'):
            build(self.root)
        self.assertEqual(originals, {path: path.read_bytes() for path in originals})

    def test_bygone_rejects_disguised_webp_without_restricting_other_album_jpeg(self):
        slug = self.save()
        album, _ = read_post(self.root/'stills/2026/06'/slug/'index.md')
        original = self.root/'stills/2026/06'/slug/album['extra']['images'][0]['file']
        original_bytes = original.read_bytes()
        build(self.root)
        self.assertTrue((self.root/'_site/stills'/slug/'index.html').exists())
        self.save(collection=True)
        collection, _ = read_post(self.root/'stills/bygone/index.md')
        disguised = self.root/'stills/bygone'/collection['extra']['images'][0]['file']
        Image.new('RGB', (3, 2), 'gray').save(disguised, 'JPEG')
        disguised_bytes = disguised.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Bygone.*WebP'):
            build(self.root)
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual(disguised.read_bytes(), disguised_bytes)


if __name__ == '__main__':
    unittest.main()
