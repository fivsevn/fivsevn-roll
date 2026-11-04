from copy import deepcopy
from io import BytesIO
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from content import ROOT, stills_path
from media_naming import media_filename
from prepare_stills import prepare
from site_post_metadata import dump_frontmatter, read_frontmatter
from stills_body import body_images
from stills_document import LAYOUT_MARKER, compose_document, image_reference


class PrepareStillsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / 'schemas', self.root / 'schemas')
        self.template, _ = read_frontmatter(ROOT / 'stills/2026/06/w-ren-min-rd-m-e/index.md')

    def jpeg(self, color='gray'):
        stream = BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        exif[270] = 'Original camera bytes'
        Image.new('RGB', (3, 2), color).save(stream, 'JPEG', quality=93, exif=exif)
        return stream.getvalue()

    def album(self, name='album', numbers=(1, 7), body='', layout=False, status='published'):
        meta = deepcopy(self.template)
        meta.update(id=name, title='Original title ' + name, status=status)
        meta['extra']['images'] = []
        meta['extra'].pop('stills_layout', None)
        if layout:
            meta['extra']['stills_layout'] = 'body-v1'
        source = stills_path(self.root, name, meta['extra']['published_at'])
        (source.parent / 'assets').mkdir(parents=True)
        for number in numbers:
            file = 'assets/' + media_filename('stills', name, meta['extra']['published_at'], number, '.jpg')
            data = self.jpeg('gray' if number == 1 else 'red')
            (source.parent / file).write_bytes(data)
            meta['extra']['images'].append({'file': file, 'alt': f'Old original {number}',
                                            'sha256': hashlib.sha256(data).hexdigest(),
                                            'source_path': f'old/{number}.JPG', 'source_commit': 'a' * 40})
        source.write_text(dump_frontmatter(meta) + body)
        return source, meta

    def write(self, source, meta, body):
        source.write_text(compose_document(meta, body))

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file() and '.git' not in path.parts}

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr.decode())
        return result.stdout.decode().strip()

    def test_migrates_in_inventory_order_preserving_old_names_bytes_and_metadata(self):
        source, meta = self.album(body='旧照片的说明。\n')
        originals = {item['file']: (source.parent / item['file']).read_bytes() for item in meta['extra']['images']}
        bygone = self.root / 'stills/bygone/index.md'
        bygone.parent.mkdir()
        bygone.write_text('An intentionally unrelated collection document')
        before_bygone = bygone.read_bytes()
        report = prepare(self.root)
        updated, body = read_frontmatter(source)
        self.assertEqual((1, 1, 0, []), (report['albums'], report['migrated'], report['added'], report['renamed']))
        self.assertEqual(meta['extra']['images'], updated['extra']['images'])
        self.assertEqual([item['file'] for item in meta['extra']['images']], [item['file'] for item in body_images(body)])
        self.assertLess(body.index(meta['extra']['images'][-1]['file']), body.index('旧照片的说明。'))
        self.assertEqual('body-v1', updated['extra']['stills_layout'])
        self.assertEqual(originals, {file: (source.parent / file).read_bytes() for file in originals})
        self.assertEqual(before_bygone, bygone.read_bytes())
        stable = self.snapshot()
        self.assertEqual(0, prepare(self.root)['changed'])
        self.assertEqual(stable, self.snapshot())

    def test_new_raw_files_get_append_only_numbers_and_rewrite_only_image_references(self):
        source, meta = self.album(layout=True)
        old = deepcopy(meta['extra']['images'])
        raw = 'assets/相机 (新) photo.JPEG'
        raw_bytes = self.jpeg('blue')
        (source.parent / raw).write_bytes(raw_bytes)
        second = source.parent / 'assets/z-next.jpg'
        second_bytes = self.jpeg('green')
        second.write_bytes(second_bytes)
        body = (LAYOUT_MARKER + '\n\n' + image_reference(old[1]) + '\n\n'
                + '![自己写的说明](<assets/相机 (新) photo.JPEG>)\n\n'
                + '[普通链接](<assets/相机 (新) photo.JPEG>)\n\n'
                + '```md\n![example](<assets/相机 (新) photo.JPEG>)\n```\n\n'
                + image_reference(old[0]) + '\n')
        self.write(source, meta, body)
        report = prepare(self.root)
        updated, rendered = read_frontmatter(source)
        new = updated['extra']['images'][2:]
        self.assertEqual(2, len(report['renamed']))
        self.assertEqual(old, updated['extra']['images'][:2])
        self.assertTrue(new[0]['file'].endswith('-008.jpg'))
        self.assertTrue(new[1]['file'].endswith('-009.jpg'))
        # Lexical allocation is independent of the intentional Markdown display order.
        named_raw = next(item for item in new if item['alt'] == Path(raw).name)
        named_second = next(item for item in new if item['alt'] == second.name)
        self.assertEqual(raw_bytes, (source.parent / named_raw['file']).read_bytes())
        self.assertEqual(second_bytes, (source.parent / named_second['file']).read_bytes())
        self.assertFalse((source.parent / raw).exists())
        self.assertEqual([old[1]['file'], named_raw['file'], old[0]['file'], named_second['file']],
                         [item['file'] for item in body_images(rendered)])
        self.assertIn('[普通链接](<assets/相机 (新) photo.JPEG>)', rendered)
        self.assertIn('```md\n![example](<assets/相机 (新) photo.JPEG>)\n```', rendered)
        self.assertEqual('自己写的说明', body_images(rendered)[1]['alt'])
        self.assertEqual(hashlib.sha256(raw_bytes).hexdigest(), named_raw['sha256'])

    def test_pre_named_new_file_keeps_name_and_reserves_its_number(self):
        source, meta = self.album(layout=True)
        numbered = 'assets/' + media_filename('stills', meta['id'], meta['extra']['published_at'], 12, '.png')
        Image.new('RGBA', (3, 2), (12, 34, 56, 0)).save(source.parent / numbered)
        numbered_bytes = (source.parent / numbered).read_bytes()
        (source.parent / 'assets/raw.jpg').write_bytes(self.jpeg())
        self.write(source, meta, LAYOUT_MARKER + '\n')
        result = prepare(self.root)
        updated, body = read_frontmatter(source)
        self.assertEqual(1, len(result['renamed']))
        self.assertEqual(numbered_bytes, (source.parent / numbered).read_bytes())
        self.assertIn(numbered, [item['file'] for item in updated['extra']['images']])
        self.assertTrue(updated['extra']['images'][-1]['file'].endswith('-013.jpg'))
        self.assertEqual(2, len(body_images(body)))

    def test_removed_old_references_and_intentional_order_remain_removed(self):
        source, meta = self.album(layout=True)
        self.write(source, meta, LAYOUT_MARKER + '\n\n说明。\n\n' + image_reference(meta['extra']['images'][1]) + '\n')
        prepare(self.root)
        updated, body = read_frontmatter(source)
        self.assertEqual(meta['extra']['images'], updated['extra']['images'])
        self.assertEqual([meta['extra']['images'][1]['file']], [image['file'] for image in body_images(body)])
        self.write(source, updated, '')
        prepare(self.root)
        empty_meta, empty_body = read_frontmatter(source)
        self.assertEqual([], body_images(empty_body))
        self.assertEqual(meta['extra']['images'], empty_meta['extra']['images'])
        (source.parent / 'assets/new.jpg').write_bytes(self.jpeg())
        prepare(self.root)
        latest, body = read_frontmatter(source)
        self.assertEqual([latest['extra']['images'][-1]['file']], [image['file'] for image in body_images(body)])

    def test_invalid_later_album_prevents_every_earlier_change(self):
        source, _ = self.album(name='a-album')
        (source.parent / 'assets/new.jpg').write_bytes(self.jpeg())
        later, _ = self.album(name='z-album')
        (later.parent / 'assets/broken.jpg').write_bytes(b'not an image')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Invalid or unsupported'):
            prepare(self.root)
        self.assertEqual(before, self.snapshot())

    def test_changed_original_checksum_and_disguised_upload_fail_without_writes(self):
        source, meta = self.album()
        original = source.parent / meta['extra']['images'][0]['file']
        original.write_bytes(self.jpeg('blue'))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'checksum changed'):
            prepare(self.root)
        self.assertEqual(before, self.snapshot())
        original.write_bytes(self.jpeg())
        Image.new('RGB', (3, 2)).save(source.parent / 'assets/disguised.jpg', 'PNG')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'extension does not match'):
            prepare(self.root)
        self.assertEqual(before, self.snapshot())

    def test_duplicate_numbers_or_destination_collision_fail_without_overwriting(self):
        source, meta = self.album()
        duplicate = 'assets/' + media_filename('stills', meta['id'], meta['extra']['published_at'], 7, '.png')
        Image.new('RGB', (3, 2)).save(source.parent / duplicate)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Duplicate Stills image number'):
            prepare(self.root)
        self.assertEqual(before, self.snapshot())
        (source.parent / duplicate).unlink()
        (source.parent / 'assets/new.jpg').write_bytes(self.jpeg())
        destination = source.parent / 'assets' / media_filename('stills', meta['id'], meta['extra']['published_at'], 8, '.jpg')
        destination.mkdir()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
            prepare(self.root)
        self.assertTrue(destination.is_dir())
        self.assertEqual(before, self.snapshot())

    def test_symlinks_and_unsafe_or_unknown_body_paths_fail_closed(self):
        source, meta = self.album(layout=True)
        outside = self.root / 'outside.jpg'
        outside.write_bytes(self.jpeg())
        link = source.parent / 'assets/linked.jpg'
        link.symlink_to(outside)
        before = source.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            prepare(self.root)
        self.assertEqual(before, source.read_bytes())
        self.assertEqual(self.jpeg(), outside.read_bytes())
        link.unlink()
        for target in ('../outside.jpg', 'assets/missing.jpg', 'https://example.com/photo.jpg'):
            self.write(source, meta, LAYOUT_MARKER + '\n\n![unsafe](' + target + ')\n')
            before = self.snapshot()
            with self.subTest(target=target), self.assertRaises(ValueError):
                prepare(self.root)
            self.assertEqual(before, self.snapshot())

    def test_duplicate_and_inline_image_references_fail_atomically(self):
        source, meta = self.album(layout=True)
        image = image_reference(meta['extra']['images'][0])
        for body in (LAYOUT_MARKER + '\n\n' + image + '\n\n' + image,
                     LAYOUT_MARKER + '\n\nMixed text ' + image):
            self.write(source, meta, body)
            (source.parent / 'assets/new.jpg').write_bytes(self.jpeg())
            before = self.snapshot()
            with self.assertRaises(ValueError):
                prepare(self.root)
            self.assertEqual(before, self.snapshot())

    def test_application_error_rolls_back_original_document_and_filename(self):
        source, _ = self.album()
        (source.parent / 'assets/new.jpg').write_bytes(self.jpeg())
        before = self.snapshot()
        with patch('prepare_stills.os.replace', side_effect=OSError('injected install failure')):
            with self.assertRaisesRegex(OSError, 'injected install'):
                prepare(self.root)
        self.assertEqual(before, self.snapshot())

    def test_staging_tracks_renames_and_already_named_new_files_but_not_unrelated_changes(self):
        source, meta = self.album(layout=True)
        self.write(source, meta, LAYOUT_MARKER + '\n')
        raw = source.parent / 'assets/[raw]*.jpg'
        raw.write_bytes(self.jpeg())
        unrelated = self.root / 'unrelated.txt'
        unrelated.write_text('committed')
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.test')
        self.git('config', 'user.name', 'Fixture')
        self.git('add', '.')
        self.git('commit', '-qm', 'Fixture')
        unrelated.write_text('not part of this preparation')
        named = source.parent / 'assets' / media_filename('stills', meta['id'], meta['extra']['published_at'], 12, '.jpg')
        named.write_bytes(self.jpeg('blue'))
        result = prepare(self.root, stage=True)
        staged = self.git('diff', '--cached', '--no-renames', '--name-only').splitlines()
        self.assertIn(source.relative_to(self.root).as_posix(), staged)
        self.assertIn(named.relative_to(self.root).as_posix(), staged)
        self.assertIn(result['renamed'][0]['from'], staged)
        self.assertIn(result['renamed'][0]['to'], staged)
        self.assertNotIn('unrelated.txt', staged)
        self.assertEqual('unrelated.txt', self.git('diff', '--name-only'))

    def test_staging_failure_restores_worktree_and_previous_index(self):
        source, _ = self.album()
        (source.parent / 'assets/new.jpg').write_bytes(self.jpeg())
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.test')
        self.git('config', 'user.name', 'Fixture')
        self.git('add', '.')
        self.git('commit', '-qm', 'Fixture')
        staged = self.root / 'prior-staged.txt'
        staged.write_text('retain this index entry')
        self.git('add', 'prior-staged.txt')
        before = self.snapshot()
        old_index = (self.root / '.git/index').read_bytes()
        import prepare_stills
        real_git = prepare_stills._git

        def fail_add(root, *args):
            if args[0] == 'add':
                raise ValueError('injected staging failure')
            return real_git(root, *args)

        with patch('prepare_stills._git', side_effect=fail_add):
            with self.assertRaisesRegex(ValueError, 'injected staging'):
                prepare(self.root, stage=True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(old_index, (self.root / '.git/index').read_bytes())

    def test_hidden_packages_are_prepared_without_changing_publication_status(self):
        source, _ = self.album(status='draft')
        data = self.jpeg('blue')
        (source.parent / 'assets/new.jpg').write_bytes(data)
        self.assertEqual(1, prepare(self.root)['albums'])
        meta, body = read_frontmatter(source)
        self.assertEqual('draft', meta['status'])
        self.assertEqual(3, len(body_images(body)))
        self.assertEqual(data, (source.parent / meta['extra']['images'][-1]['file']).read_bytes())

    def test_animated_gif_original_is_moved_byte_for_byte(self):
        source, meta = self.album(layout=True)
        self.write(source, meta, LAYOUT_MARKER + '\n')
        upload = source.parent / 'assets/animated.gif'
        frames = [Image.new('RGBA', (3, 2), color) for color in ('red', 'blue')]
        frames[0].save(upload, save_all=True, append_images=frames[1:], duration=[0, 120], loop=3, disposal=2)
        original = upload.read_bytes()
        prepare(self.root)
        updated, _ = read_frontmatter(source)
        saved = source.parent / updated['extra']['images'][-1]['file']
        self.assertEqual(original, saved.read_bytes())
        with Image.open(saved) as image:
            self.assertEqual(2, image.n_frames)
            self.assertEqual(3, image.info['loop'])


if __name__ == '__main__':
    unittest.main()
