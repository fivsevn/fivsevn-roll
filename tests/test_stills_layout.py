from pathlib import Path
import hashlib
import sys
import unittest

from bs4 import BeautifulSoup
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import build
from check import check
from content import load_posts, read_post
from stills_body import BODY_MARKER, body_images, display_images, is_body_layout, parse_layout, rewrite_image_paths
from stills_document import compose_document, image_reference
import test_stills_body as fixtures


class StillsLayoutParserTests(unittest.TestCase):
    def test_adjacent_image_lines_share_one_block_and_keep_literal_alt(self):
        resources = [{'file': 'assets/a&b.jpg', 'alt': 'inventory'}, {'file': 'assets/b.jpg'}]
        alt = '&amp; & <text> [brackets] *stars* _under_ `code` \\ slash'
        body = BODY_MARKER + '\n' + image_reference({**resources[0], 'alt': alt}) + '\n' + image_reference(resources[1])
        blocks = parse_layout(body, resources)
        self.assertEqual(['photos'], [block['kind'] for block in blocks])
        self.assertEqual(alt, display_images(blocks)[0]['alt'])
        self.assertEqual('inventory', resources[0]['alt'])
        for reference in body_images(body):
            self.assertTrue(body[reference['start']:reference['end']].startswith('!['))

    def test_rewrite_changes_only_actual_images_and_preserves_authored_alt(self):
        body = (BODY_MARKER + '\n\n![a \\[b\\] &amp;](<assets/raw (one).jpg>)\n'
                '![second][photo]\n\n[ordinary](assets/raw%20%28one%29.jpg)\n\n'
                '```md\n![example](assets/raw%20%28one%29.jpg)\n```\n\n'
                '    ![indented](assets/raw%20%28one%29.jpg)\n\n[photo]: assets/raw%20%28one%29.jpg\n')
        revised = rewrite_image_paths(body, {'assets/raw (one).jpg': 'assets/new (二).jpg'})
        self.assertEqual(['assets/new (二).jpg'] * 2, [image['file'] for image in body_images(revised)])
        self.assertIn('![a \\[b\\] &amp;](assets/new%20%28%E4%BA%8C%29.jpg)', revised)
        for unchanged in ('[ordinary](assets/raw%20%28one%29.jpg)', '![example](assets/raw%20%28one%29.jpg)',
                          '    ![indented](assets/raw%20%28one%29.jpg)', '[photo]: assets/raw%20%28one%29.jpg'):
            self.assertIn(unchanged, revised)

    def test_only_safe_package_assets_are_accepted(self):
        for target in ('https://example.com/a.jpg', '//example.com/a.jpg', '../a.jpg',
                       'assets/%2e%2e/a.jpg', '/assets/a.jpg', 'assets/a.jpg?size=1', 'assets/a.jpg#part'):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'local assets/'):
                body_images(f'![a]({target})')

    def test_images_must_be_separate_from_inline_text_links_and_tables(self):
        for body in ('before ![a](assets/a.jpg) after', '[![a](assets/a.jpg)](https://example.com)',
                     '# ![a](assets/a.jpg)', '| A |\n| - |\n| ![a](assets/a.jpg) |'):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, 'separate lines'):
                body_images(body)

    def test_empty_body_keeps_new_mode_and_unreferenced_resources(self):
        self.assertTrue(is_body_layout('', {'extra': {'stills_layout': 'body-v1'}}))
        self.assertTrue(is_body_layout(BODY_MARKER + '\n'))
        self.assertFalse(is_body_layout('Ordinary notes.'))
        self.assertEqual([], parse_layout('', [{'file': 'assets/a.jpg'}]))

    def test_missing_inventory_and_duplicate_references_are_rejected(self):
        body = '![one](assets/a.jpg)\n\nText.\n\n![again](assets/a.jpg)'
        with self.assertRaisesRegex(ValueError, 'resource inventory'):
            parse_layout(body, [])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            parse_layout(body, [{'file': 'assets/a.jpg', 'sha256': 'kept'}])

    def test_indented_code_is_not_reinterpreted_and_moved_marker_stays_internal(self):
        code = '    ![code](assets/example.jpg)\n'
        blocks = parse_layout(code, [])
        self.assertEqual([], body_images(code))
        self.assertIn('<pre><code>![code](assets/example.jpg)', blocks[0]['html'])
        body = 'Opening.\n\n' + BODY_MARKER + '\n\n![a](assets/a.jpg)\n\n```md\n' + BODY_MARKER + '\n```'
        self.assertTrue(is_body_layout(body))
        blocks = parse_layout(body, [{'file': 'assets/a.jpg'}])
        self.assertEqual(['text', 'photos', 'text'], [block['kind'] for block in blocks])
        self.assertNotIn('stills-layout', blocks[0]['html'])
        self.assertIn('stills-layout', blocks[-1]['html'])
        self.assertFalse(is_body_layout('```md\n' + BODY_MARKER + '\n```'))

    def test_text_retains_html_escaping_and_safe_link_rules(self):
        blocks = parse_layout('<script>alert(1)</script>\n\n[bad](javascript:alert) [good](/stills/)', [])
        fragment = BeautifulSoup(blocks[0]['html'], 'html.parser')
        self.assertFalse(fragment.select('script'))
        self.assertIn('<script>', fragment.get_text())
        self.assertEqual([None, '/stills/'], [link.get('href') for link in fragment.select('a')])


class StillsLayoutBuildTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.StillsBodyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        (self.root / 'site-data/originals.json').write_text('[]')

    def source(self):
        slug = self.fixture.save()
        path = next((self.root / 'stills/2026').rglob('index.md'))
        return slug, path, read_post(path)[0]

    def write(self, path, data, body):
        data['extra']['stills_layout'] = 'body-v1'
        path.write_text(compose_document(data, body))

    def test_migrating_legacy_gallery_preserves_every_public_byte(self):
        slug, path, data = self.source()
        data['extra']['images'][0]['alt'] = '&amp; & <photo> [one] *stars* `code` \\ slash'
        notes = 'Original **notes** and [link](/stills/).\n'
        path.write_text(compose_document(data, notes))
        Image.new('RGB', (1701, 900), 'gray').save(path.parent / data['extra']['images'][0]['file'])
        build(self.root)
        baseline = {file.relative_to(self.root / '_site'): file.read_bytes() for file in (self.root / '_site').rglob('*') if file.is_file()}
        body = BODY_MARKER + '\n\n' + '\n\n'.join(image_reference(image) for image in data['extra']['images']) + '\n\n' + notes
        self.write(path, data, body)
        build(self.root)
        revised = {file.relative_to(self.root / '_site'): file.read_bytes() for file in (self.root / '_site').rglob('*') if file.is_file()}
        self.assertEqual(baseline.keys(), revised.keys())
        for file in baseline:
            self.assertEqual(hashlib.sha256(baseline[file]).hexdigest(), hashlib.sha256(revised[file]).hexdigest(), str(file))
        check(self.root)

    def test_body_order_text_interleaving_and_alt_override_inventory_order(self):
        slug, path, data = self.source()
        first, second = data['extra']['images']
        body = (BODY_MARKER + '\n\nOpening.\n\n' + image_reference({**second, 'alt': 'Body & second'})
                + '\n\nMiddle.\n\n' + image_reference({**first, 'alt': 'Body first'}) + '\n\nClosing.\n')
        self.write(path, data, body)
        build(self.root, base_path='/preview')
        page = self.fixture.page('stills/' + slug)
        blocks = page.select('.entry-content > .roll-photos, .entry-content > .roll-stills-body')
        self.assertEqual(['Opening.', 'Body & second', 'Middle.', 'Body first', 'Closing.'],
                         [block.get_text().strip() if block.get_text().strip() else block.img['alt'] for block in blocks])
        figures = page.select('.roll-photos figure')
        self.assertEqual(['photo-1', 'photo-2'], [figure['id'] for figure in figures])
        self.assertEqual(['eager', 'lazy'], [figure.img['loading'] for figure in figures])
        self.assertEqual(2, len(page.select('.roll-photos img')))
        loaded = load_posts(self.root)['stills'][0]
        self.assertEqual([second['file'], first['file']], [image['file'] for image in loaded['_display_images']])
        self.assertEqual([first, second], loaded['extra']['images'])
        check(self.root, base_path='/preview')

    def test_removing_all_references_including_marker_never_restores_inventory(self):
        slug, path, data = self.source()
        for body in (BODY_MARKER + '\n', '', 'Only text remains.'):
            with self.subTest(body=body):
                self.write(path, data, body)
                build(self.root)
                self.assertFalse(self.fixture.page('stills/' + slug).select('.roll-photos'))
                self.assertEqual(2, len(read_post(path)[0]['extra']['images']))
                self.assertEqual([], load_posts(self.root)['stills'][0]['_display_images'])
                check(self.root)

    def test_body_marker_does_not_enable_images_for_bygone(self):
        self.fixture.save(collection=True, body=BODY_MARKER + '\n\n![bad](assets/a.webp)')
        with self.assertRaisesRegex(ValueError, 'body images are not published'):
            build(self.root)


if __name__ == '__main__':
    unittest.main()
