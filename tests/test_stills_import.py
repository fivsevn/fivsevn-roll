from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from io import BytesIO

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from content import ROOT, load_posts, read_post
from import_stills import INBOX, STATE, ingest, read_state


def png(color):
    stream = BytesIO()
    Image.new('RGB', (3, 2), color).save(stream, 'PNG')
    return stream.getvalue()


class StillsUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'schemas').mkdir()
        shutil.copyfile(ROOT/'schemas/content-metadata.schema.json', self.root/'schemas/content-metadata.schema.json')
        (self.root/'site-data').mkdir()
        (self.root/'site-data/history.json').write_text('{"stills":[],"motion":[]}')
        (self.root/INBOX).mkdir(parents=True)
        (self.root/INBOX/'README.md').write_text('Upload images here.')
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'test')
        self.git('config', 'user.email', 'test@example.com')
        self.base = self.commit('Initialize test repository')

    def git(self, *args, env=None):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE, env=env).decode().strip()

    def commit(self, message, date='2026-10-31T09:04:00Z'):
        self.git('add', '--all')
        self.git('commit', '-m', message, env={**os.environ, 'GIT_AUTHOR_DATE':date, 'GIT_COMMITTER_DATE':date})
        return self.git('rev-parse', 'HEAD')

    def upload(self, name, data=None):
        target = self.root/INBOX/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data or png('red'))
        return target

    def saved(self, event):
        return self.root/event['package']/'index.md'

    def test_multicommit_push_is_one_group_with_original_files_and_shanghai_title(self):
        originals = {'02 相片.png':png('blue'), '01.png':png('green')}
        self.upload('02 相片.png', originals['02 相片.png'])
        self.commit('First upload in the same push')
        self.upload('01.png', originals['01.png'])
        after = self.commit('Second upload in the same push')
        event = ingest(self.root, before=self.base, after=after)
        self.assertEqual(2, len(event['images']))
        meta, body = read_post(self.saved(event))
        self.assertEqual('31 Oct, 2026 17:04', meta['title'])
        self.assertEqual('2026-10-31T17:04:00+08:00', meta['extra']['published_at'])
        self.assertEqual(['assets/01.png','assets/02 相片.png'], [i['file'] for i in meta['extra']['images']])
        self.assertFalse(body.strip())
        self.assertEqual(1, len(load_posts(self.root)['stills']))
        for name, data in originals.items():
            self.assertEqual(data, (self.saved(event).parent/'assets'/name).read_bytes())
            self.assertTrue((self.root/INBOX/name).is_file())
        self.assertEqual(1, len(read_state(self.root)['events']))

    def test_rerun_preserves_edited_title_body_and_hidden_decision(self):
        self.upload('one.png')
        after = self.commit('Upload')
        event = ingest(self.root, before=self.base, after=after)
        path = self.saved(event)
        revised = path.read_text().replace('status: published','status: hidden') + '\nEdited story.\n'
        path.write_text(revised)
        self.assertIsNone(ingest(self.root, before=self.base, after=after))
        self.assertEqual(revised, path.read_text())
        self.assertEqual(1, len(read_state(self.root)['events']))

    def test_later_push_reusing_filename_creates_new_group_and_preserves_old_bytes(self):
        self.upload('phone.png', png('red'))
        first = self.commit('First push')
        one = ingest(self.root, before=self.base, after=first)
        self.commit('Save generated package')
        before = self.git('rev-parse','HEAD')
        self.upload('phone.png', png('blue'))
        second = self.commit('Second push', date='2026-11-01T00:10:00Z')
        two = ingest(self.root, before=before, after=second)
        self.assertNotEqual(one['id'], two['id'])
        self.assertEqual(png('red'), (self.saved(one).parent/'assets/phone.png').read_bytes())
        self.assertEqual(png('blue'), (self.saved(two).parent/'assets/phone.png').read_bytes())
        self.assertIn('/2026/11/', two['package'])
        self.assertEqual([two['id'],one['id']], [p['id'] for p in load_posts(self.root)['stills']])

    def test_delayed_push_reads_exact_snapshot_not_later_inbox_contents(self):
        self.upload('same.png', png('red'))
        first = self.commit('First push')
        self.upload('same.png', png('blue'))
        latest = self.commit('Later push')
        event = ingest(self.root, before=self.base, after=first)
        self.assertEqual(png('red'), (self.saved(event).parent/'assets/same.png').read_bytes())
        self.assertEqual(png('blue'), (self.root/INBOX/'same.png').read_bytes())
        other = ingest(self.root, before=first, after=latest)
        self.assertNotEqual(event['id'], other['id'])

    def test_only_explicit_inbox_changes_are_published(self):
        self.upload('old.png')
        prior = self.commit('An earlier upload')
        (self.root/'drafts').mkdir()
        (self.root/'drafts/new.png').write_bytes(png('blue'))
        (self.root/'unrelated.png').write_bytes(png('green'))
        after = self.commit('Ordinary code or draft push')
        self.upload('uncommitted.png')
        self.assertIsNone(ingest(self.root, before=prior, after=after))
        self.assertFalse((self.root/STATE).exists())

    def test_manual_import_is_explicit_pending_batch_and_reruns_do_not_duplicate(self):
        self.upload('a.png')
        head = self.commit('Upload a')
        first = ingest(self.root, manual=True)
        self.assertIsNone(ingest(self.root, manual=True))
        self.commit('Save a')
        self.upload('b.png')
        self.upload('c.png')
        self.commit('Upload b and c')
        second = ingest(self.root, manual=True)
        self.assertEqual(['stills/trigger_imgs/b.png','stills/trigger_imgs/c.png'], [i['upload_path'] for i in second['images']])
        self.assertNotEqual(first['id'],second['id'])

    def test_invalid_batch_is_atomic_and_keeps_inbox(self):
        self.upload('01-good.png')
        self.upload('02-invalid.png', b'not an image')
        after = self.commit('Upload a mixed batch')
        with self.assertRaisesRegex(ValueError,'Invalid Stills image'):
            ingest(self.root,before=self.base,after=after)
        self.assertFalse((self.root/STATE).exists())
        self.assertEqual([],list((self.root/'stills').rglob('index.md')))
        self.assertTrue((self.root/INBOX/'01-good.png').exists())

    def test_rejects_extension_mismatch_and_symlink_uploads(self):
        self.upload('wrong.jpg', png('red'))
        after = self.commit('Upload mislabeled image')
        with self.assertRaisesRegex(ValueError,'extension'):
            ingest(self.root,before=self.base,after=after)
        (self.root/INBOX/'wrong.jpg').unlink()
        (self.root/INBOX/'link.png').symlink_to('../../README.md')
        latest = self.commit('Upload symlink')
        with self.assertRaisesRegex(ValueError,'[Ss]ymlink'):
            ingest(self.root,before=after,after=latest)

    def test_subdirectories_prevent_same_basename_collisions_and_staging_is_scoped(self):
        self.upload('left/photo.png',png('red'))
        self.upload('right/photo.png',png('blue'))
        after = self.commit('Upload both directories')
        (self.root/'unrelated.txt').write_text('Never stage this.')
        event = ingest(self.root,before=self.base,after=after,stage=True)
        self.assertEqual(['assets/left/photo.png','assets/right/photo.png'], [x['file'] for x in event['images']])
        staged = self.git('diff','--cached','--name-only').splitlines()
        self.assertNotIn('unrelated.txt',staged)
        self.assertEqual(4,len(staged))
        self.assertIn(STATE,staged)

    def test_deleted_within_push_is_not_published_and_existing_package_is_never_overwritten(self):
        self.upload('removed.png')
        self.commit('Add then remove within push')
        (self.root/INBOX/'removed.png').unlink()
        after = self.commit('Remove before push ends')
        self.assertIsNone(ingest(self.root,before=self.base,after=after))
        self.upload('new.png')
        latest = self.commit('Upload')
        event = ingest(self.root,before=after,after=latest)
        (self.root/STATE).unlink()
        with self.assertRaisesRegex(ValueError,'overwrite'):
            ingest(self.root,before=after,after=latest)
        self.assertTrue(self.saved(event).is_file())

    def test_nonancestor_push_is_rejected(self):
        self.upload('one.png')
        after = self.commit('Upload')
        with self.assertRaises(ValueError):
            ingest(self.root,before=after,after=self.base)


if __name__ == '__main__':
    unittest.main()
