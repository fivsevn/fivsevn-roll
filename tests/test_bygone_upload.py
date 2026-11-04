from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from unittest.mock import patch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest

from PIL import Image, ImageCms, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bygone_webp import convert
from bygone_inbox import cleanup
from content import ROOT, read_post
from import_bygone import INBOX, PACKAGE, STATE, ingest, read_state
from media_naming import media_filename
from site_post_metadata import dump_frontmatter


def picture(format='PNG', color='red', size=(7, 5), **options):
    output = BytesIO()
    Image.new('RGBA' if isinstance(color, tuple) and len(color) == 4 else 'RGB', size, color).save(output, format, **options)
    return output.getvalue()


class BygoneWebPTests(unittest.TestCase):
    def test_png_transparency_and_pixels_are_lossless(self):
        source = picture(color=(70, 90, 120, 0))
        output, size = convert(source, '透明.png')
        self.assertEqual(size, (7, 5))
        with Image.open(BytesIO(source)) as before, Image.open(BytesIO(output)) as after:
            self.assertEqual(after.format, 'WEBP')
            self.assertEqual(before.convert('RGBA').tobytes(), after.convert('RGBA').tobytes())

    def test_jpeg_orientation_is_applied_without_resizing(self):
        exif = Image.Exif(); exif[274] = 6
        output, size = convert(picture('JPEG', size=(1701, 900), exif=exif), 'camera.jpg')
        self.assertEqual(size, (900, 1701))
        with Image.open(BytesIO(output)) as image:
            self.assertEqual(image.size, (900, 1701))
            self.assertIsNone(image.getexif().get(274))

    def test_palette_png_keeps_transparency_and_rgb_profile(self):
        image = Image.new('P', (5, 4))
        image.putpalette([70, 90, 120] + [0, 0, 0] * 255)
        source = BytesIO()
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        image.save(source, 'PNG', transparency=0, icc_profile=profile)
        output, _ = convert(source.getvalue(), 'palette.png')
        with Image.open(BytesIO(source.getvalue())) as before, Image.open(BytesIO(output)) as after:
            self.assertEqual(before.convert('RGBA').tobytes(), after.convert('RGBA').tobytes())
            self.assertEqual(after.info['icc_profile'], profile)

    def test_existing_webp_is_not_recompressed(self):
        source = picture('WEBP', quality=95)
        self.assertEqual(convert(source, 'photo.webp')[0], source)

    def test_heic_heif_keep_oriented_resolution_exif_and_color_profile(self):
        exif = Image.Exif(); exif[274] = 6; exif[270] = 'Bygone scan'
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        source = picture('HEIF', size=(18, 12), exif=exif, icc_profile=profile)
        with Image.open(BytesIO(source)) as original:
            expected_size = ImageOps.exif_transpose(original).size
        for filename in ['phone.heic', 'phone.HEIF']:
            with self.subTest(filename=filename):
                output, size = convert(source, filename)
                self.assertEqual(size, expected_size)
                with Image.open(BytesIO(output)) as image:
                    self.assertEqual(image.format, 'WEBP')
                    self.assertEqual(image.size, expected_size)
                    self.assertEqual(image.getexif().get(270), 'Bygone scan')
                    self.assertEqual(image.getexif().get(274, 1), 1)
                    self.assertEqual(image.info['icc_profile'], profile)

    def test_animation_and_misnamed_data_are_rejected(self):
        for format, filename in [('GIF', 'animation.gif'), ('HEIF', 'sequence.heic')]:
            with self.subTest(format=format):
                output = BytesIO()
                Image.new('RGB', (18, 12), 'red').save(output, format, save_all=True,
                    append_images=[Image.new('RGB', (18, 12), 'blue')], duration=100, loop=0)
                with self.assertRaisesRegex(ValueError, 'Animated'):
                    convert(output.getvalue(), filename)
        with self.assertRaisesRegex(ValueError, 'extension'):
            convert(picture(), 'misnamed.jpg')


class BygoneUploadTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(ROOT/'schemas', self.root/'schemas')
        (self.root/'site-data').mkdir()
        (self.root/INBOX).mkdir(parents=True)
        (self.root/INBOX/'README.md').write_text('Bygone upload entry')
        (self.root/PACKAGE/'assets').mkdir()
        meta, _ = read_post(ROOT/PACKAGE/'index.md')
        self.first = 'assets/' + media_filename('stills', 'bygone', meta['extra']['published_at'], 1, '.webp')
        baseline = picture('WEBP', color='green')
        (self.root/PACKAGE/self.first).write_bytes(baseline)
        meta['extra']['images'] = [{'file': self.first, 'alt': 'Saved photo'}]
        (self.root/PACKAGE/'index.md').write_text(dump_frontmatter(meta) + '\nExisting collection note.\n')
        self.card = {'file': self.first, 'title': 'Saved photo', 'published_at': '2026-06-19T02:06:52+08:00',
                     'display_date': '2026-06-19T02:06:52+08:00', 'comment_count': '0'}
        (self.root/'site-data/bygone.json').write_text(json.dumps({'page_size': 30, 'cards': [self.card]}))
        (self.root/'site-data/originals.json').write_text(json.dumps([{'path': PACKAGE+'/'+self.first,
            'bytes': len(baseline), 'sha256': hashlib.sha256(baseline).hexdigest(), 'role': 'post'}]))
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.base = self.commit('Initial collection')

    def git(self, *args, env=None):
        return subprocess.check_output(['git', '-C', str(self.root), *args], env=env, stderr=subprocess.PIPE).decode().strip()

    def commit(self, title, date='2026-11-05T00:30:00Z'):
        self.git('add', '--all')
        self.git('commit', '-m', title, env={**os.environ, 'GIT_AUTHOR_DATE': date, 'GIT_COMMITTER_DATE': date})
        return self.git('rev-parse', 'HEAD')

    def upload(self, filename, data=None):
        path = self.root/INBOX/filename; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data or picture()); return path

    def photos(self):
        return read_post(self.root/PACKAGE/'index.md')[0]['extra']['images']

    def proof(self):
        folder = self.root/'_site'; folder.mkdir(exist_ok=True)
        files = {PACKAGE+'/'+item['file']: hashlib.sha256((self.root/PACKAGE/item['file']).read_bytes()).hexdigest()
                 for item in self.photos()}
        fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        content = json.dumps({'files': files, 'fingerprint': fingerprint}).encode()
        (folder/'build-receipt.json').write_bytes(content)
        (folder/'.verified-live.json').write_text(json.dumps({'version': 1, 'fingerprint': fingerprint,
            'receipt_sha256': hashlib.sha256(content).hexdigest()}))

    def test_batch_uses_next_stable_number_and_commit_time_with_old_order_untouched(self):
        self.upload('new scan.png')
        after = self.commit('Upload')
        event = ingest(self.root, before=self.base, after=after)
        images = self.photos()
        self.assertTrue(images[0]['file'].endswith('-002.webp'))
        self.assertEqual(images[1]['file'], self.first)
        self.assertEqual(images[0]['alt'], 'new scan')
        cards = json.loads((self.root/'site-data/bygone.json').read_text())['cards']
        self.assertEqual(cards[0]['published_at'], '2026-11-05T08:30:00+08:00')
        self.assertEqual(cards[1], self.card)
        self.assertIn('Existing collection note.', (self.root/PACKAGE/'index.md').read_text())
        self.assertIsNone(ingest(self.root, before=self.base, after=after))
        self.assertEqual(event, next(iter(read_state(self.root)['events'].values())))
        self.assertTrue((self.root/INBOX/'new scan.png').exists())

    def test_identical_bytes_in_same_batch_and_later_upload_do_not_duplicate(self):
        data = picture()
        self.upload('a.png', data); self.upload('b.png', data)
        after = self.commit('Same bytes twice')
        ingest(self.root, before=self.base, after=after)
        self.assertEqual(len(self.photos()), 2)
        self.commit('Save collection')
        before = self.git('rev-parse', 'HEAD')
        self.upload('later.png', data)
        later = self.commit('Upload same bytes under another name')
        event = ingest(self.root, before=before, after=later)
        self.assertEqual(len(self.photos()), 2)
        self.assertEqual(event['images'][0]['file'], self.photos()[0]['file'])

    def test_heif_upload_uses_the_same_numbering_and_deduplication(self):
        source = picture('HEIF', size=(18, 12))
        self.upload('phone.heic', source); self.upload('same.HEIF', source)
        after = self.commit('Upload phone photos')
        event = ingest(self.root, before=self.base, after=after)
        self.assertEqual(len(self.photos()), 2)
        self.assertEqual(len({image['file'] for image in event['images']}), 1)
        self.assertTrue(self.photos()[0]['file'].endswith('-002.webp'))
        with Image.open(self.root/PACKAGE/self.photos()[0]['file']) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertEqual(image.size, (18, 12))
        self.assertTrue((self.root/INBOX/'phone.heic').exists())

    def test_retry_preserves_edited_collection_title_notes_and_card_title(self):
        self.upload('one.png'); after = self.commit('Upload')
        ingest(self.root, before=self.base, after=after)
        source = self.root/PACKAGE/'index.md'
        edited = source.read_text().replace('title: Bygone', 'title: Edited collection') + '\nNew note.\n'
        source.write_text(edited)
        cards = self.root/'site-data/bygone.json'
        content = json.loads(cards.read_text()); content['cards'][0]['title'] = 'Edited scan'
        cards.write_text(json.dumps(content))
        self.assertIsNone(ingest(self.root, before=self.base, after=after))
        self.assertEqual(source.read_text(), edited)
        self.assertEqual(json.loads(cards.read_text())['cards'][0]['title'], 'Edited scan')

    def test_delayed_push_reads_its_own_snapshot(self):
        red = picture(color='red'); blue = picture(color='blue')
        self.upload('phone.png', red); first = self.commit('First')
        self.upload('phone.png', blue); self.commit('Later upload')
        event = ingest(self.root, before=self.base, after=first)
        self.assertEqual(event['images'][0]['source_sha256'], hashlib.sha256(red).hexdigest())
        self.assertEqual((self.root/INBOX/'phone.png').read_bytes(), blue)

    def test_bad_batch_leaves_collection_ledger_and_all_inputs_untouched(self):
        self.upload('a.png'); self.upload('z.jpg', picture())
        after = self.commit('Invalid batch')
        before = (self.root/PACKAGE/'index.md').read_bytes()
        with self.assertRaisesRegex(ValueError, 'extension'):
            ingest(self.root, before=self.base, after=after)
        self.assertEqual((self.root/PACKAGE/'index.md').read_bytes(), before)
        self.assertFalse((self.root/STATE).exists())
        self.assertEqual(len(list((self.root/PACKAGE/'assets').iterdir())), 1)
        self.assertTrue((self.root/INBOX/'a.png').exists())
        self.assertTrue((self.root/INBOX/'z.jpg').exists())

    def test_partial_install_rolls_back_before_consuming_inputs(self):
        self.upload('one.png'); after = self.commit('Upload')
        before = (self.root/PACKAGE/'index.md').read_bytes()
        original_replace = os.replace
        count = 0
        def fail_second(source, target):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('disk failure')
            return original_replace(source, target)
        with patch('import_bygone.os.replace', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'disk failure'):
                ingest(self.root, before=self.base, after=after)
        self.assertEqual((self.root/PACKAGE/'index.md').read_bytes(), before)
        self.assertFalse((self.root/STATE).exists())
        self.assertEqual(len(list((self.root/PACKAGE/'assets').iterdir())), 1)
        self.assertTrue((self.root/INBOX/'one.png').exists())

    def test_orphaned_name_is_reserved_and_manual_entry_is_idempotent(self):
        reserved = self.first.replace('-001.webp', '-002.webp')
        (self.root/PACKAGE/reserved).write_bytes(picture('WEBP'))
        self.upload('one.png'); self.commit('Upload pending')
        ingest(self.root, manual=True)
        self.assertTrue(self.photos()[0]['file'].endswith('-003.webp'))
        self.assertIsNone(ingest(self.root, manual=True))

    def test_cleanup_waits_for_matching_live_proof_and_protects_newer_inputs(self):
        path = self.upload('one.png'); after = self.commit('Upload')
        ingest(self.root, before=self.base, after=after)
        self.commit('Save collection')
        with self.assertRaisesRegex(ValueError, 'verification'):
            cleanup(self.root)
        self.proof()
        self.assertEqual(cleanup(self.root), [INBOX+'/one.png'])
        self.assertFalse(path.exists())
        self.assertTrue((self.root/PACKAGE/self.photos()[0]['file']).exists())

    def test_cleanup_does_not_delete_replaced_upload_or_changed_output(self):
        path = self.upload('one.png'); after = self.commit('Upload')
        ingest(self.root, before=self.base, after=after)
        self.commit('Save collection'); self.proof()
        path.write_bytes(picture(color='blue')); self.commit('New upload at same path')
        self.assertEqual(cleanup(self.root), [])
        self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()
