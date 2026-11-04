from pathlib import Path
import sys
import unittest
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import build, SITE_URL
from content import ROOT, motion_path, read_post
from site_post_metadata import dump_frontmatter
from stills_document import compose_document, image_reference, LAYOUT_MARKER
import test_stills_body as fixtures


class HeadMetadataTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.StillsBodyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def test_new_content_has_unique_escaped_metadata_and_production_urls_in_preview(self):
        title = 'Night & <field> "quoted" </title><script>alert(1)</script>'
        slug = self.fixture.save(title=title)
        path = next((self.root / 'stills/2026').rglob('index.md'))
        meta, _ = read_post(path)
        meta['summary'] = 'A <detail> & "quoted" description.'
        path.write_text(compose_document(meta, 'Authored notes.'))
        motion, _ = read_post(next((ROOT / 'motion').rglob('index.md')))
        motion.update(title='A newly generated room', status='published', visibility='public')
        destination = motion_path(self.root, motion['id'], motion['extra']['published_at'])
        destination.parent.mkdir(parents=True)
        destination.write_text(dump_frontmatter(motion) + '**New** room notes.')
        build(self.root, base_path='/preview')
        for file in (self.root / '_site').rglob('*.html'):
            page = BeautifulSoup(file.read_text(), 'html.parser')
            for selector in ('meta[name="description"]', 'link[rel="canonical"]', 'meta[property="og:title"]',
                             'meta[property="og:description"]', 'meta[property="og:url"]', 'meta[property="og:type"]',
                             'meta[name="twitter:card"]', 'meta[name="twitter:title"]', 'meta[name="twitter:description"]'):
                self.assertEqual(1, len(page.head.select(selector)), (str(file), selector))
            canonical = page.select_one('link[rel="canonical"]')['href']
            self.assertTrue(canonical.startswith(SITE_URL + '/'))
            self.assertNotIn('/preview/', canonical)
            self.assertEqual(canonical, page.select_one('meta[property="og:url"]')['content'])
            self.assertEqual(page.title.get_text(), page.select_one('meta[property="og:title"]')['content'])
            image = page.select_one('meta[property="og:image"]')
            if image:
                self.assertTrue((self.root / '_site' / unquote(urlparse(image['content']).path).lstrip('/')).is_file())
        detail = self.fixture.page('stills/' + slug)
        self.assertEqual(meta['summary'], detail.select_one('meta[name="description"]')['content'])
        self.assertEqual('article', detail.select_one('meta[property="og:type"]')['content'])
        self.assertFalse(detail.head.find('script'))
        room = self.fixture.page('motion/' + motion['id'])
        self.assertEqual('New room notes.', room.select_one('meta[name="description"]')['content'])
        missing = BeautifulSoup((self.root / '_site/404.html').read_text(), 'html.parser')
        self.assertEqual('noindex, follow', missing.select_one('meta[name="robots"]')['content'])

    def test_sharing_uses_body_selection_and_never_an_unpublished_inventory_image(self):
        slug = self.fixture.save()
        path = next((self.root / 'stills/2026').rglob('index.md'))
        meta, _ = read_post(path)
        first, second = meta['extra']['images']
        meta['extra']['stills_layout'] = 'body-v1'
        path.write_text(compose_document(meta, LAYOUT_MARKER + '\n\n' + image_reference(second)))
        build(self.root)
        page = self.fixture.page('stills/' + slug)
        selected = SITE_URL + '/stills/' + slug + '/' + second['file']
        self.assertEqual(selected, page.select_one('meta[property="og:image"]')['content'])
        self.assertEqual(selected, page.select_one('meta[name="twitter:image"]')['content'])
        self.assertFalse((self.root / '_site/stills' / slug / first['file']).exists())
        path.write_text(compose_document(meta, ''))
        build(self.root)
        page = self.fixture.page('stills/' + slug)
        self.assertIn('/site-assets/', page.select_one('meta[property="og:image"]')['content'])
        self.assertFalse(page.select('.roll-photos img'))


if __name__ == '__main__':
    unittest.main()
