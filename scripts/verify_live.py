"""Compare the deployed receipt and every served public file with this build."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import quote
import argparse,hashlib,json,os,tempfile,time,requests
from content import ROOT

# This root-level build marker is omitted by the Pages artifact upload. It is
# still covered by receipt equality, but is not a public HTTP resource. Keep
# this exact allowlist: CNAME and any other dotfiles must still be verified.
PAGES_CONTROL_FILES = frozenset({'.nojekyll'})


def verify(url,root=ROOT):
    marker=root/'_site/.verified-live.json'
    marker.unlink(missing_ok=True)
    receipt_bytes=(root/'_site/build-receipt.json').read_bytes()
    receipt=json.loads(receipt_bytes)
    for attempt in range(12):
        try:
            r=requests.get(url.rstrip('/')+'/build-receipt.json',params={'v':receipt['fingerprint']},timeout=30);r.raise_for_status()
            if r.json()==receipt:break
        except (requests.RequestException,ValueError):pass
        if attempt==11:raise RuntimeError('Live deployment receipt does not match this build')
        time.sleep(10)
    def check(item):
        path,expected=item
        failure = 'no response'
        for attempt in range(3):
            try:
                r=requests.get(url.rstrip('/')+'/'+quote(path,safe='/'),timeout=45)
                if r.status_code==200 and hashlib.sha256(r.content).hexdigest()==expected:return
                failure = f'HTTP {r.status_code}' if r.status_code != 200 else 'content hash mismatch'
            except requests.RequestException as exc:
                failure = type(exc).__name__
            if attempt<2:time.sleep(2)
        raise RuntimeError(f'Live file mismatch: {path} ({failure})')
    public_files = {path: sha for path, sha in receipt['files'].items() if path not in PAGES_CONTROL_FILES}
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(check,public_files.items()))
    proof={'version':1,'fingerprint':receipt['fingerprint'],
           'receipt_sha256':hashlib.sha256(receipt_bytes).hexdigest(),
           'url':url.rstrip('/'),'verified_at':datetime.now(timezone.utc).isoformat()}
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',prefix='.verified-live-',dir=marker.parent,delete=False) as temporary:
        json.dump(proof,temporary,ensure_ascii=False,indent=2)
        temporary.write('\n')
    os.replace(temporary.name,marker)
    print(f"Verified receipt and {len(public_files)} live files at {url}; {receipt['fingerprint']}")

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='https://roll.fivsevn.com');verify(p.parse_args().url)
