from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json
import sys
import unittest

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_live import verify


BASE_URL = 'https://roll.example'


def response(content, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = content
    result.url = BASE_URL
    return result


class LiveVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / '_site').mkdir()
        self.sleep = patch('verify_live.time.sleep').start()
        self.addCleanup(patch.stopall)

    def receipt(self, files):
        hashes = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
        receipt = {'version': 1, 'files': hashes, 'fingerprint': 'fixture'}
        (self.root / '_site/build-receipt.json').write_text(json.dumps(receipt))
        return json.dumps(receipt).encode()

    def test_only_root_pages_marker_is_excluded(self):
        files = {'.nojekyll': b'', 'CNAME': b'roll.example\n',
                 '.well-known/probe.txt': b'probe', 'nested/.nojekyll': b'public'}
        receipt = self.receipt(files)
        fetched = []

        def get(url, **kwargs):
            path = url.removeprefix(BASE_URL + '/')
            fetched.append(path)
            if path == 'build-receipt.json':
                return response(receipt)
            self.assertNotEqual('.nojekyll', path)
            return response(files[path])

        with patch('verify_live.requests.get', side_effect=get):
            verify(BASE_URL, self.root)
        self.assertCountEqual(fetched, ['build-receipt.json', 'CNAME',
                                       '.well-known/probe.txt', 'nested/.nojekyll'])
        proof = json.loads((self.root / '_site/.verified-live.json').read_text())
        self.assertEqual('fixture', proof['fingerprint'])
        self.assertEqual(hashlib.sha256(receipt).hexdigest(), proof['receipt_sha256'])
        self.assertEqual(BASE_URL, proof['url'])

    def test_public_missing_or_changed_file_still_fails(self):
        receipt = self.receipt({'index.html': b'expected'})
        for status in (404, 200):
            with self.subTest(status=status):
                calls = Counter()
                proof_path = self.root / '_site/.verified-live.json'
                proof_path.write_text('{"fingerprint":"fixture"}')

                def get(url, **kwargs):
                    calls[url] += 1
                    return response(receipt) if url.endswith('/build-receipt.json') else response(b'wrong', status)

                with patch('verify_live.requests.get', side_effect=get):
                    with self.assertRaisesRegex(RuntimeError, 'Live file mismatch: index.html'):
                        verify(BASE_URL, self.root)
                self.assertEqual(3, calls[BASE_URL + '/index.html'])
                self.assertFalse(proof_path.exists())

    def test_transient_network_failure_is_retried(self):
        receipt = self.receipt({'index.html': b'expected'})
        with patch('verify_live.requests.get', side_effect=[response(receipt),
                   requests.ConnectionError('temporary'), response(b'expected')]) as get:
            verify(BASE_URL, self.root)
        self.assertEqual(3, get.call_count)
        self.sleep.assert_called_once_with(2)

    def test_persistent_network_failure_is_reported_with_path(self):
        receipt = self.receipt({'index.html': b'expected'})
        with patch('verify_live.requests.get', side_effect=[response(receipt)] +
                   [requests.Timeout('temporary')] * 3) as get:
            with self.assertRaisesRegex(RuntimeError, r'index.html \(Timeout\)'):
                verify(BASE_URL, self.root)
        self.assertEqual(4, get.call_count)

    def test_marker_remains_part_of_receipt_validation(self):
        receipt = json.loads(self.receipt({'.nojekyll': b'', 'index.html': b'expected'}))
        receipt['files'].pop('.nojekyll')
        with patch('verify_live.requests.get', return_value=response(json.dumps(receipt).encode())) as get:
            with self.assertRaisesRegex(RuntimeError, 'receipt does not match'):
                verify(BASE_URL, self.root)
        self.assertEqual(12, get.call_count)
        self.assertTrue(all(call.args[0].endswith('/build-receipt.json') for call in get.call_args_list))
        self.assertFalse((self.root / '_site/.verified-live.json').exists())


if __name__ == '__main__':
    unittest.main()
