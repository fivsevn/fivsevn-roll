from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from content import ROOT, load_posts, motion_path, write_post
from sync_youtube import plan, existing_ids, Video


class MotionArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'schemas').mkdir()
        shutil.copytree(ROOT / 'schemas', self.root / 'schemas', dirs_exist_ok=True)
        (self.root / 'site-data').mkdir()
        (self.root / 'site-data/history.json').write_text(json.dumps({'stills': [], 'motion': []}))

    def save(self, video, **updates):
        path, data = plan([video], self.root)[0]
        data.update(updates)
        write_post(path, data)
        return path, data

    def test_sync_uses_shanghai_year_and_month_at_utc_boundaries(self):
        videos = [Video('New year', 'AbCdEf123_-', '2025-12-31T16:00:00Z'),
                  Video('New month', 'BcDeFg234_-', '2026-01-31T16:00:00Z'),
                  Video('Previous month', 'CdEfGh345_-', '2026-01-31T15:59:59Z')]
        pending = plan(videos, self.root)
        self.assertEqual([('2026', '01'), ('2026', '02'), ('2026', '01')],
                         [path.relative_to(self.root).parts[1:3] for path, _ in pending])
        self.assertEqual('2026-01-01T00:00:00+08:00', pending[0][1]['extra']['published_at'])
        self.assertTrue(pending[0][0].parent.name.startswith('2026-01-01-000000-'))
        for path, data in pending:
            write_post(path, data)
        loaded = load_posts(self.root)['motion']
        self.assertEqual(['New month', 'Previous month', 'New year'], [post['title'] for post in loaded])

    def test_loader_rejects_flat_or_wrong_month_instead_of_omitting_content(self):
        video = Video('Archive', 'AbCdEf123_-', '2026-01-31T16:00:00Z')
        correct, data = self.save(video)
        wrong_paths = [self.root / 'motion' / data['id'] / 'index.md',
                       self.root / 'motion/2026/01' / correct.parent.name / 'index.md',
                       self.root / 'motion/2026/02' / data['id'] / 'index.md']
        for wrong in wrong_paths:
            with self.subTest(path=wrong):
                wrong.parent.mkdir(parents=True, exist_ok=True)
                correct.rename(wrong)
                try:
                    with self.assertRaisesRegex(ValueError, 'publication year/month'):
                        load_posts(self.root)
                finally:
                    wrong.rename(correct)

    def test_duplicate_ids_across_months_cannot_overwrite_public_route(self):
        _, data = self.save(Video('Archive', 'AbCdEf123_-', '2026-01-01T00:00:00Z'))
        data['extra']['published_at'] = '2026-02-01T00:00:00+08:00'
        write_post(motion_path(self.root, data['id'], data['extra']['published_at']), data)
        with self.assertRaisesRegex(ValueError, 'duplicate package ID'):
            load_posts(self.root)

    def test_hidden_nested_package_stays_saved_and_is_never_reimported(self):
        video = Video('Hidden', 'AbCdEf123_-', '2026-01-01T00:00:00Z')
        path, _ = self.save(video, status='hidden')
        original = path.read_bytes()
        self.assertEqual([], load_posts(self.root)['motion'])
        self.assertEqual(1, len(load_posts(self.root, include_hidden=True)['motion']))
        self.assertIn(video.video_id, existing_ids(self.root))
        self.assertEqual([], plan([Video('Updated upstream', video.video_id, '2026-02-01T00:00:00Z')], self.root))
        self.assertEqual(original, path.read_bytes())

    def test_loader_keeps_saved_identity_and_original_timezone(self):
        path, data = self.save(Video('Saved title', 'AbCdEf123_-', '2026-01-31T16:00:00Z'))
        data['extra']['published_at'] = '2026-01-31T16:00:00+00:00'
        write_post(path, data)
        original = path.read_bytes()
        loaded = load_posts(self.root)['motion'][0]
        self.assertEqual(data['id'], loaded['id'])
        self.assertEqual(data['extra']['published_at'], loaded['extra']['published_at'])
        self.assertEqual(original, path.read_bytes())

    def test_sync_can_archive_a_separator_only_video_id(self):
        path, data = self.save(Video('Unusual ID', '___________', '2026-01-01T00:00:00Z'))
        self.assertTrue(data['id'].startswith('youtube-video-'))
        self.assertEqual(path, load_posts(self.root)['motion'][0]['_path'])


if __name__ == '__main__':
    unittest.main()
