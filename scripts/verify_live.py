"""Compare the deployed receipt and every public file with this build."""
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
import argparse,hashlib,json,time,requests
from content import ROOT


def verify(url,root=ROOT):
    receipt=json.loads((root/'_site/build-receipt.json').read_text())
    for attempt in range(12):
        try:
            r=requests.get(url.rstrip('/')+'/build-receipt.json',params={'v':receipt['fingerprint']},timeout=30);r.raise_for_status()
            if r.json()==receipt:break
        except (requests.RequestException,ValueError):pass
        if attempt==11:raise RuntimeError('Live deployment receipt does not match this build')
        time.sleep(10)
    def check(item):
        path,expected=item
        for attempt in range(3):
            r=requests.get(url.rstrip('/')+'/'+quote(path,safe='/'),timeout=45)
            if r.status_code==200 and hashlib.sha256(r.content).hexdigest()==expected:return
            if attempt<2:time.sleep(2)
        raise RuntimeError(f'Live file mismatch: {path} ({r.status_code})')
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(check,receipt['files'].items()))
    print(f"Verified {len(receipt['files'])} live files at {url}; {receipt['fingerprint']}")

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='https://roll.fivsevn.com');verify(p.parse_args().url)
