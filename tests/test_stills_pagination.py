from pathlib import Path
from tempfile import TemporaryDirectory
import copy
import json
import shutil
import sys
import unittest

from PIL import Image
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from content import ROOT, read_post, stills_path, write_post
from build import build, stills_page_size
from sync_youtube import plan, Video


class StillsPaginationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for folder in ('schemas', 'site-data', 'templates', 'site-assets'):
            shutil.copytree(ROOT / folder, self.root / folder)
        shutil.copyfile(ROOT / 'CNAME', self.root / 'CNAME')
        self.example, _ = read_post(ROOT / 'stills/2026/06/w-ren-min-rd-m-e/index.md')

    def configure(self, size):
        (self.root / 'site-data/stills.json').write_text(json.dumps({'page_size': size}))

    def save(self, slug, status='published'):
        data = copy.deepcopy(self.example)
        data.update(id=slug, title=slug, status=status)
        data['extra'].pop('source', None)
        data['extra'].pop('legacy_id', None)
        data['extra']['images'] = [{'file': 'assets/sample.png', 'alt': slug}]
        path = stills_path(self.root, slug, data['extra']['published_at'])
        (path.parent / 'assets').mkdir(parents=True)
        Image.new('RGB', (2, 2), 'green').save(path.parent / 'assets/sample.png')
        write_post(path, data)

    def page(self, route):
        return BeautifulSoup((self.root / '_site' / route / 'index.html').read_text(), 'html.parser')

    def assert_arrows(self, pager, number, routes):
        previous = pager.select_one('[aria-label="Previous Page"]')
        following = pager.select_one('[aria-label="Next Page"]')
        if number == 1:
            self.assertIsNone(previous)
        else:
            self.assertEqual('«', previous.get_text())
            self.assertEqual(routes[number - 2], previous['href'])
        if number == len(routes):
            self.assertIsNone(following)
        else:
            self.assertEqual('»', following.get_text())
            self.assertEqual(routes[number], following['href'])

    def test_current_sized_collection_has_no_pager(self):
        self.save('one')
        build(self.root)
        self.assertIsNone(self.page('stills').select_one('.roll-stills-pagination'))
        self.assertFalse((self.root / '_site/stills/page').exists())
        self.assertEqual('/stills/', self.page('stills/one').find('a', string='viewfinder')['href'])

    def test_pages_preserve_portfolio_order_and_detail_return_destinations(self):
        self.configure(2)
        order = ['zeta', 'alpha', 'epsilon', 'beta', 'gamma']
        for slug in order:
            self.save(slug)
        self.save('unpublished', status='draft')
        (self.root / 'site-data/history.json').write_text(json.dumps({'stills': ['unpublished', *order], 'motion': []}))
        build(self.root, base_path='/roll')
        all_titles = []
        for number, expected in enumerate([order[:2], order[2:4], order[4:]], start=1):
            route = 'stills' if number == 1 else f'stills/page/{number}'
            page = self.page(route)
            titles = [link.get_text() for link in page.select('ul.wp-block-post-template h2 a')]
            self.assertEqual(expected, titles)
            all_titles.extend(titles)
            pager = page.select_one('.roll-stills-pagination')
            self.assertEqual(['1', '2', '3'], [link.get_text() for link in pager.select('a.page-numbers')])
            self.assertEqual([str(number)], [link.get_text() for link in pager.select('[aria-current="page"]')])
            self.assertEqual(['/roll/stills/', '/roll/stills/page/2/', '/roll/stills/page/3/'],
                             [link['href'] for link in pager.select('a.page-numbers')])
            self.assert_arrows(pager, number, ['/roll/stills/', '/roll/stills/page/2/', '/roll/stills/page/3/'])
            self.assertIs(pager, page.select_one('ul.wp-block-post-template').find_next_sibling('nav'))
            for slug in expected:
                detail = self.page('stills/' + slug)
                self.assertEqual('/roll/' + route + '/', detail.find('a', string='viewfinder')['href'])
        self.assertEqual(order, all_titles)
        self.assertFalse((self.root / '_site/stills/unpublished').exists())
        sitemap = (self.root / '_site/sitemap.xml').read_text()
        self.assertIn('https://roll.fivsevn.com/stills/page/3/', sitemap)
        self.assertNotIn('unpublished', sitemap)

    def test_motion_uses_the_same_previous_and_next_boundary_controls(self):
        videos = [Video('one', 'AbCdEf12345', '2026-01-01T00:00:00Z'),
                  Video('two', 'BcDeFg23456', '2026-01-02T00:00:00Z'),
                  Video('three', 'CdEfGh34567', '2026-01-03T00:00:00Z')]
        for path, data in plan(videos, self.root):
            write_post(path, data)
        config_path = self.root / 'site-data/youtube.json'
        config = json.loads(config_path.read_text())
        config['page_size'] = 1
        config_path.write_text(json.dumps(config))
        build(self.root, base_path='/roll')
        routes = ['/roll/motion/', '/roll/motion/page/2/', '/roll/motion/page/3/']
        for number in range(1, 4):
            route = 'motion' if number == 1 else f'motion/page/{number}'
            pager = self.page(route).select_one('.roll-pagination')
            self.assert_arrows(pager, number, routes)
            self.assertEqual(routes, [link['href'] for link in pager.select('a.page-numbers')])

    def test_page_size_rejects_zero_negative_boolean_and_noninteger(self):
        for invalid in (0, -1, True, 1.5, '2', None):
            with self.subTest(value=invalid):
                self.configure(invalid)
                with self.assertRaisesRegex(ValueError, 'positive integer'):
                    stills_page_size(self.root)

    def test_shrinking_collection_removes_stale_list_pages(self):
        self.configure(2)
        for slug in ('one', 'two', 'three'):
            self.save(slug)
        build(self.root)
        self.assertTrue((self.root / '_site/stills/page/2/index.html').is_file())
        self.configure(30)
        build(self.root)
        self.assertFalse((self.root / '_site/stills/page').exists())
        self.assertIsNone(self.page('stills').select_one('.roll-stills-pagination'))


if __name__ == '__main__':
    unittest.main()
