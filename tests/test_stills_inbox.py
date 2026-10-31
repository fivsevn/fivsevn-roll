from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import subprocess
import sys
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from content import ROOT, read_post, write_post
from stills_inbox import cleanup


class StillsInboxTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.com')
        self.upload_name = 'stills/trigger_imgs/frames/a [1].png'
        self.upload = self.root / self.upload_name
        self.upload.parent.mkdir(parents=True)
        data = BytesIO()
        Image.new('RGB', (3, 2), 'blue').save(data, 'PNG')
        self.original = data.getvalue()
        self.upload.write_bytes(self.original)
        self.commit('Upload photographs')
        self.after = self.git('rev-parse', 'HEAD').strip()
        self.blob = self.git('rev-parse', 'HEAD:' + self.upload_name).strip()
        self.ident = '2026-10-31-170000-abc123abc123'
        self.package = 'stills/2026/10/' + self.ident
        self.image_file = 'assets/frames/a [1].png'
        self.saved = self.root / self.package / self.image_file
        self.saved.parent.mkdir(parents=True)
        self.saved.write_bytes(self.original)
        self.index = self.root / self.package / 'index.md'
        self.meta, _ = read_post(ROOT / 'stills/2026/06/w-ren-min-rd-m-e/index.md')
        self.meta.update(id=self.ident, title='Uploaded album')
        self.meta['extra']['published_at'] = '2026-10-31T17:00:00+08:00'
        self.meta['extra']['images'] = [{'file': self.image_file}]
        write_post(self.index, self.meta)
        self.sha256 = hashlib.sha256(self.original).hexdigest()
        self.event = {'id': self.ident, 'published_at': self.meta['extra']['published_at'],
                      'before': '0' * 40, 'after': self.after, 'package': self.package,
                      'images': [{'upload_path': self.upload_name, 'blob_sha': self.blob,
                                  'sha256': self.sha256, 'file': self.image_file}]}
        self.state = {'version': 1, 'events': {'push:' + self.after: self.event}}
        self.state_path = self.root / '.publishing/stills.json'
        self.state_path.parent.mkdir()
        self.save_state()
        self.commit('Save generated package')
        self.served = 'stills/' + self.ident + '/' + self.image_file
        self.served_page = 'stills/' + self.ident + '/index.html'
        self.page_hash = hashlib.sha256(b'<html>Published album</html>').hexdigest()
        (self.root / '_site').mkdir()
        self.proof_path = self.root / '_site/.verified-live.json'
        self.receipt_path = self.root / '_site/build-receipt.json'
        self.prove()

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)
        return result.stdout.decode()

    def commit(self, message):
        self.git('add', '--all')
        self.git('commit', '-qm', message)

    def save_state(self):
        self.state_path.write_text(json.dumps(self.state))

    def prove(self, files=None):
        files = {self.served: self.sha256, self.served_page: self.page_hash} if files is None else files
        fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        receipt = {'version': 1, 'files': files, 'fingerprint': fingerprint}
        raw = (json.dumps(receipt) + '\n').encode()
        self.receipt_path.write_bytes(raw)
        self.proof_path.write_text(json.dumps({'version': 1, 'fingerprint': fingerprint,
                                               'receipt_sha256': hashlib.sha256(raw).hexdigest()}))

    def test_only_verified_copy_is_removed_and_retry_is_a_noop(self):
        unrelated = self.upload.parent / 'new.png'
        unrelated.write_bytes(self.original)
        ledger = self.state_path.read_bytes()
        self.assertEqual([self.upload_name], cleanup(self.root))
        self.assertFalse(self.upload.exists())
        self.assertEqual(self.original, self.saved.read_bytes())
        self.assertEqual(self.original, unrelated.read_bytes())
        self.assertEqual(ledger, self.state_path.read_bytes())
        self.assertEqual([], cleanup(self.root))

    def test_missing_stale_or_changed_receipt_proof_cannot_delete(self):
        self.proof_path.unlink()
        with self.assertRaisesRegex(ValueError, 'successful live verification'):
            cleanup(self.root)
        self.prove()
        proof = json.loads(self.proof_path.read_text())
        proof['fingerprint'] = '0' * 64
        self.proof_path.write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError, 'does not match'):
            cleanup(self.root)
        self.prove()
        self.receipt_path.write_bytes(self.receipt_path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            cleanup(self.root)
        self.assertTrue(self.upload.is_file())

    def test_original_must_be_selected_and_match_verified_receipt(self):
        for files in ({self.served: self.sha256}, {self.served_page: self.page_hash},
                      {self.served: '0' * 64, self.served_page: self.page_hash}):
            with self.subTest(files=files):
                self.prove(files)
                self.assertEqual([], cleanup(self.root))
        self.prove()
        self.saved.write_bytes(b'changed package bytes')
        self.assertEqual([], cleanup(self.root))
        self.saved.write_bytes(self.original)
        self.meta['extra']['images'] = []
        write_post(self.index, self.meta)
        self.assertEqual([], cleanup(self.root))
        self.assertTrue(self.upload.is_file())

    def test_unpublished_packages_never_clear_the_upload(self):
        for status, visibility in [('draft', 'public'), ('published', 'private')]:
            with self.subTest(status=status, visibility=visibility):
                self.meta.update(status=status, visibility=visibility)
                write_post(self.index, self.meta)
                self.assertEqual([], cleanup(self.root))
        self.assertTrue(self.upload.is_file())

    def test_changed_working_copy_or_git_blob_is_kept(self):
        self.upload.write_bytes(b'new upload still being edited')
        self.assertEqual([], cleanup(self.root))
        self.upload.write_bytes(self.original)
        self.event['images'][0]['blob_sha'] = '0' * 40
        self.save_state()
        self.assertEqual([], cleanup(self.root))
        self.assertTrue(self.upload.is_file())

    def test_newer_identical_reupload_is_not_mistaken_for_old_copy(self):
        self.git('rm', '--', self.upload_name)
        self.commit('Remove old inbox copy')
        self.upload.parent.mkdir(parents=True, exist_ok=True)
        self.upload.write_bytes(self.original)
        self.commit('Upload identical photo in a new push')
        self.assertEqual(self.blob, self.git('rev-parse', 'HEAD:' + self.upload_name).strip())
        self.assertEqual([], cleanup(self.root))
        self.assertTrue(self.upload.is_file())

    def test_staged_new_upload_is_not_overwritten_by_cleanup(self):
        self.upload.write_bytes(b'new staged upload')
        self.git('add', '--', self.upload_name)
        self.upload.write_bytes(self.original)
        self.assertEqual([], cleanup(self.root))
        self.assertTrue(self.upload.is_file())

    def test_symlink_upload_is_rejected_and_target_is_untouched(self):
        outside = self.root / 'outside.png'
        outside.write_bytes(self.original)
        self.upload.unlink()
        self.upload.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            cleanup(self.root)
        self.assertTrue(self.upload.is_symlink())
        self.assertEqual(self.original, outside.read_bytes())

    def test_symlink_parent_and_escaping_ledger_are_rejected(self):
        actual = self.upload.parent.with_name('actual-frames')
        self.upload.parent.rename(actual)
        self.upload.parent.symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            cleanup(self.root)
        self.upload.parent.unlink()
        actual.rename(self.upload.parent)
        self.event['images'][0]['upload_path'] = 'stills/trigger_imgs/../../outside.png'
        self.save_state()
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            cleanup(self.root)
        self.assertTrue(self.upload.is_file())

    def test_symlink_proof_is_not_accepted(self):
        saved_proof = self.root / 'saved-proof.json'
        self.proof_path.rename(saved_proof)
        self.proof_path.symlink_to(saved_proof)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            cleanup(self.root)
        self.assertTrue(self.upload.is_file())


if __name__ == '__main__':
    unittest.main()
