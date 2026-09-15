from pathlib import Path
from datetime import datetime, timezone
import hashlib
import requests

UA = "NazufiUKLivingScore/0.2 (+https://www.nazufienterprise.com/)"
DATA_DIR = Path(__file__).with_name("data")
STAGING_DIR = DATA_DIR / "staging"
ARCHIVE_DIR = DATA_DIR / "archive"
for p in (DATA_DIR, STAGING_DIR, ARCHIVE_DIR):
    p.mkdir(exist_ok=True)

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def request(url, timeout=120, stream=False):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout, stream=stream)
    r.raise_for_status()
    return r

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def download_to_staging(url, filename):
    target = STAGING_DIR / filename
    with request(url, stream=True) as r:
        with open(target, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
    return target
