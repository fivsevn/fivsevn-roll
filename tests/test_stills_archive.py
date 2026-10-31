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
from content import ROOT, load_posts, read_post, stills_path, write_post
from build import build


class StillsArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for folder in ('schemas', 'site-data'):
            shutil.copytree(ROOT / folder, self.root / folder)
        self.example, _ = read_post(ROOT / 'stills/2026/06/w-ren-min-rd-m-e/index.md')

    def save(self, slug='test-stills', published_at='2026-06-01T12:20:45+08:00'):
        data = copy.deepcopy(self.example)
        data['id'] = slug
        data['title'] = slug
        data['extra']['published_at'] = published_at
        data['extra']['images'] = [{'file': 'assets/sample.png', 'alt': 'Sample'}]
        data['extra'].pop('legacy_id', None)
        data['extra'].pop('source', None)
        path = stills_path(self.root, slug, published_at)
        path.parent.joinpath('assets').mkdir(parents=True)
        Image.new('RGB', (2, 2), 'green').save(path.parent / 'assets/sample.png')
        write_post(path, data)
        return path, data

    def test_archive_month_uses_shanghai_date_and_keeps_group_name(self):
        path, _ = self.save(published_at='2026-04-30T16:00:00+00:00')
        self.assertEqual('stills/2026/05/test-stills/index.md', path.relative_to(self.root).as_posix())
        self.assertEqual('test-stills', load_posts(self.root)['stills'][0]['id'])

    def test_misdated_or_flat_package_cannot_be_silently_skipped(self):
        correct, data = self.save()
        wrong_paths = [self.root / 'stills' / data['id'] / 'index.md',
                       self.root / 'stills/2026/05' / data['id'] / 'index.md']
        for wrong in wrong_paths:
            with self.subTest(path=wrong):
                wrong.parent.parent.mkdir(parents=True, exist_ok=True)
                correct.parent.rename(wrong.parent)
                try:
                    with self.assertRaisesRegex(ValueError, 'publication year/month'):
                        load_posts(self.root)
                finally:
                    wrong.parent.rename(correct.parent)

    def test_existing_portfolio_tie_order_is_kept(self):
        self.save('alpha')
        self.save('zeta')
        (self.root / 'site-data/history.json').write_text(json.dumps({'stills': ['zeta', 'alpha'], 'motion': []}))
        self.assertEqual(['zeta', 'alpha'], [post['id'] for post in load_posts(self.root)['stills']])

    def test_nested_archive_retains_existing_public_photo_url(self):
        path, data = self.save()
        for folder in ('templates', 'site-assets'):
            shutil.copytree(ROOT / folder, self.root / folder)
        shutil.copyfile(ROOT / 'CNAME', self.root / 'CNAME')
        original = (path.parent / 'assets/sample.png').read_bytes()
        build(self.root)
        output = self.root / '_site'
        page = BeautifulSoup((output / 'stills/test-stills/index.html').read_text(), 'html.parser')
        self.assertEqual('/stills/test-stills/assets/sample.png', page.select_one('.roll-photos img')['src'])
        self.assertEqual('/stills/test-stills/assets/sample.png', page.select_one('.roll-photos a')['href'])
        self.assertEqual(original, (output / 'stills/test-stills/assets/sample.png').read_bytes())
        self.assertFalse((output / 'stills/2026').exists())


if __name__ == '__main__':
    unittest.main()
