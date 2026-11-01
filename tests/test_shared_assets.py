"""Shared assets must never dereference draft files while publishing."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import build, validate_shared_assets


class SharedAssetBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'site-assets'
        self.source.mkdir()
        self.drafts = self.root / 'drafts'
        self.drafts.mkdir()
        self.secret = self.drafts / 'unreviewed.png'
        self.secret.write_bytes(b'NEW-DRAFT-NOT-IN-THE-MIGRATION-MANIFEST')

    def test_regular_shared_files_are_accepted_without_modification(self):
        originals = {'roll.css': b'body{}', 'navigation.js': b'/* ok */',
                     'fonts/example.woff2': b'font', 'nested/banner.PNG': b'image'}
        for name, value in originals.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        validate_shared_assets(self.source)
        for name, value in originals.items():
            self.assertEqual(value, (self.source / name).read_bytes())

    def test_file_link_to_untracked_draft_is_rejected(self):
        (self.source / 'banner.png').symlink_to(self.secret)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            validate_shared_assets(self.source)

    def test_directory_link_to_drafts_is_rejected(self):
        (self.source / 'photos').symlink_to(self.drafts, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            validate_shared_assets(self.source)

    def test_shared_root_cannot_be_a_link(self):
        self.source.rmdir()
        self.source.symlink_to(self.drafts, target_is_directory=True)
        with self.assertRaises(ValueError):
            validate_shared_assets(self.source)

    def test_dangling_link_is_rejected(self):
        (self.source / 'missing.png').symlink_to(self.root / 'missing.png')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            validate_shared_assets(self.source)

    def test_disallowed_extension_is_rejected(self):
        (self.source / 'notes.md').write_text('Unreviewed notes')
        with self.assertRaisesRegex(ValueError, 'Unexpected shared asset'):
            validate_shared_assets(self.source)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX FIFO test')
    def test_special_file_is_rejected_without_reading_it(self):
        os.mkfifo(self.source / 'blocked.png')
        with self.assertRaisesRegex(ValueError, 'Unexpected shared asset'):
            validate_shared_assets(self.source)

    def test_missing_or_non_directory_root_is_rejected(self):
        self.source.rmdir()
        with self.assertRaises(ValueError):
            validate_shared_assets(self.source)
        self.source.write_bytes(b'not a directory')
        with self.assertRaises(ValueError):
            validate_shared_assets(self.source)

    def test_build_rejects_before_replacing_previous_output(self):
        (self.source / 'banner.png').symlink_to(self.secret)
        output = self.root / '_site'
        output.mkdir()
        (output / 'index.html').write_text('previous valid build')
        with patch('build.load_posts', return_value={'stills': [], 'motion': []}), \
             patch('build.stills_page_size', return_value=30), \
             patch('build.shutil.copytree') as copier:
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                build(self.root)
            copier.assert_not_called()
        self.assertEqual('previous valid build', (output / 'index.html').read_text())
        self.assertFalse((output / 'site-assets').exists())
        self.assertEqual(b'NEW-DRAFT-NOT-IN-THE-MIGRATION-MANIFEST', self.secret.read_bytes())


if __name__ == '__main__':
    unittest.main()
