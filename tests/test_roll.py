from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import copy,json,shutil,sys,unittest,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from content import ROOT,read_post,write_post,public,safe_asset,load_posts
from sync_youtube import plan,existing_ids,sync,Video
from build import build


class PublishingTests(unittest.TestCase):
    def test_public_requires_both_controls(self):
        for data in [{},{'status':'published'},{'visibility':'public'},{'status':'draft','visibility':'public'},{'status':'published','visibility':'private'}]:self.assertFalse(public(data))
        self.assertTrue(public({'status':'published','visibility':'public'}))

    def test_all_manifest_files_are_eligible_for_git_archiving(self):
        rows=json.loads((ROOT/'migration/assets.json').read_text())['files']
        paths='\0'.join(r['destination'] for r in rows)+'\0'
        result=subprocess.run(['git','check-ignore','--no-index','-z','--stdin'],input=paths.encode(),cwd=ROOT,capture_output=True)
        self.assertIn(result.returncode,(0,1))
        self.assertEqual(b'',result.stdout, 'Reviewed originals must not be silently ignored by Git')

    def test_asset_paths_cannot_escape_package(self):
        package=ROOT/'stills/2026/06/w-ren-min-rd-m-e'
        for path in ['../drafts/test.jpg','assets/../../../drafts/test.jpg','/etc/passwd','assets\\test.jpg']:
            with self.assertRaises(ValueError):safe_asset(package,path)
        self.assertTrue(safe_asset(package,'assets/1.JPG').is_file())

    def test_legacy_group_order_and_draft_boundary(self):
        posts=load_posts(include_hidden=True);groups=[p for p in posts['stills'] if p['extra'].get('legacy_id')]
        self.assertEqual(17,len(groups));self.assertEqual(266,sum(len(p['extra']['images']) for p in groups))
        self.assertEqual(['assets/1.JPG','assets/2.JPG','assets/3.JPG'],groups[0]['extra']['images'] and [i['file'] for i in groups[0]['extra']['images']])
        self.assertEqual(136,len(next(p for p in posts['stills'] if p['id']=='bygone')['extra']['images']))
        manifest=json.loads((ROOT/'migration/assets.json').read_text())['files']
        self.assertEqual(91,sum(r['status']=='needs-review' and Path(r['source_path']).suffix.lower() in {'.jpg','.jpeg','.png','.webp'} for r in manifest))
        self.assertEqual(506,len([r for r in manifest if r['source_path'].startswith('stills/')]))

    def test_hidden_package_has_no_page_media_index_or_alias(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            for folder in ['schemas','templates','site-assets','site-data']:shutil.copytree(ROOT/folder,root/folder)
            shutil.copyfile(ROOT/'CNAME',root/'CNAME')
            package=root/'stills/2026/06/w-ren-min-rd-m-e';shutil.copytree(ROOT/'stills/2026/06/w-ren-min-rd-m-e',package)
            data,_=read_post(package/'index.md');data['status']='draft';write_post(package/'index.md',data)
            (root/'drafts').mkdir();(root/'drafts/PRIVATE.txt').write_text('DRAFT-CANARY')
            (root/'_site').mkdir();(root/'_site/stale.jpg').write_bytes(b'stale')
            build(root,base_path='/fivsevn-roll')
            self.assertIn("url('/fivsevn-roll/site-assets/fonts/",(root/'_site/site-assets/stills.css').read_text())
            self.assertNotIn('href="/fivsevn-roll/stills/bygone/"',(root/'_site/stills/index.html').read_text())
            self.assertFalse((root/'_site/stills/w-ren-min-rd-m-e').exists())
            self.assertFalse((root/'_site/2026/06/01/w-ren-min-rd-m-e').exists())
            self.assertFalse((root/'_site/drafts').exists());self.assertFalse((root/'_site/stale.jpg').exists())
            self.assertNotIn('w-ren-min-rd-m-e',(root/'_site/sitemap.xml').read_text())
            self.assertNotIn('W Ren min',(root/'_site/stills/index.html').read_text())


class SyncTests(unittest.TestCase):
    def test_duplicate_input_is_one_package_and_retry_preserves_edits(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);v=Video('Title','AbCdEf123_-','2026-10-31T00:00:00Z');pending=plan([v,v],root);self.assertEqual(1,len(pending))
            path,data=pending[0];data['title']='Edited title';data['status']='hidden';write_post(path,data)
            original=path.read_bytes();self.assertEqual([],plan([v],root));self.assertEqual(original,path.read_bytes())

    def test_draft_videos_are_not_republished(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);write_post(root/'drafts/video/index.md',{'extra':{'video_ids':['AbCdEf123_-']}})
            self.assertEqual([],plan([Video('Title','AbCdEf123_-','2026-10-31T00:00:00Z')],root))

    def test_case_sensitive_ids_get_distinct_routes(self):
        with TemporaryDirectory() as temp:
            pending=plan([Video('A','AbCdEf123_-','2026-10-31T00:00:00Z'),Video('B','abCdEf123_-','2026-10-31T00:00:00Z')],Path(temp))
            self.assertEqual(2,len({str(path) for path,_ in pending}))

    def test_invalid_batch_writes_nothing(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError):plan([Video('A','AbCdEf123_-','2026-10-31T00:00:00Z'),Video('B','ZyXwVu987_-',None)],root)
            self.assertEqual([],list(root.rglob('index.md')))

    def test_old_history_survives_small_or_empty_catalogue(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);path=root/'motion/old/index.md';write_post(path,{'extra':{'video_ids':['AbCdEf123_-']}})
            original=path.read_bytes();self.assertEqual([],plan([],root));self.assertEqual(original,path.read_bytes())

    def test_wrong_channel_fails_before_network(self):
        with patch.dict('os.environ',{'YOUTUBE_FIVSEVN_CHANNEL_ID':'UC'+'x'*22}),patch('sync_youtube.get_channel_videos') as network:
            with self.assertRaises(ValueError):sync()
            network.assert_not_called()

if __name__=='__main__':unittest.main()
