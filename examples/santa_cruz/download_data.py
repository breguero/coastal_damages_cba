"""Download and unpack the Santa Cruz sample data (Google Drive), then check file hashes.

    python examples/santa_cruz/download_data.py                  # into examples/santa_cruz/data/
    python examples/santa_cruz/download_data.py --zip <file.zip> # use a zip downloaded by hand

The archive holds the inputs (flood maps, exposure, study units, adaptation dimensions and costs,
damage tables) and the reference results. See README.md in this folder.
"""

import argparse
import csv
import hashlib
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

# Google Drive share link of cosmos_adapts_santacruz_sample.zip ("Anyone with the link can view").
DRIVE_LINK = "https://drive.google.com/file/d/REPLACE_WITH_FILE_ID/view?usp=sharing"
ZIP_NAME = "cosmos_adapts_santacruz_sample.zip"
ZIP_SHA256 = "22f4f4ede3308d7b66d0043656368e4cc09ac7867ac676ee51202967f69ab1e4"
PACKAGE_DIR = "cosmos_adapts_santacruz_sample"

HERE = Path(__file__).resolve().parent


def drive_file_id(link: str) -> str:
    m = re.search(r"/d/([\w-]{20,})", link) or re.search(r"[?&]id=([\w-]{20,})", link)
    if not m or "REPLACE_WITH" in link:
        sys.exit("No Google Drive file id set: edit DRIVE_LINK in download_data.py or pass --link.")
    return m.group(1)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(file_id: str, dest: Path) -> None:
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    print(f"Downloading {ZIP_NAME} from Google Drive ...")
    with urllib.request.urlopen(url) as r, open(dest, "wb") as fh:
        if "text/html" in r.headers.get("Content-Type", ""):
            sys.exit("Google Drive returned a web page instead of the file. Check that the link is public, "
                     "or download the zip by hand and pass --zip.")
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while chunk := r.read(1 << 20):
            fh.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
    print()


def check_manifest(root: Path) -> int:
    bad = 0
    with open(root / "MANIFEST.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            f = root / row["path"]
            if not f.exists() or f.stat().st_size != int(row["bytes"]) or sha256(f) != row["sha256"]:
                print(f"  hash mismatch or missing: {row['path']}")
                bad += 1
    return bad


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dest", type=Path, default=HERE / "data", help="folder to unpack into")
    p.add_argument("--link", default=DRIVE_LINK, help="Google Drive share link of the zip")
    p.add_argument("--zip", type=Path, help="local copy of the zip (skips the download)")
    a = p.parse_args(argv)

    a.dest.mkdir(parents=True, exist_ok=True)
    zip_path = a.zip or a.dest / ZIP_NAME
    if a.zip is None and not zip_path.exists():
        download(drive_file_id(a.link), zip_path)
    digest = sha256(zip_path)
    if digest != ZIP_SHA256:
        print(f"WARNING: zip sha256 {digest} differs from the expected {ZIP_SHA256} (different data version?)")

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(a.dest)
    root = a.dest / PACKAGE_DIR
    bad = check_manifest(root)
    if bad:
        sys.exit(f"{bad} files failed the hash check")
    print(f"Data ready: {root}")
    print("Run:  python pipeline/run_pipeline.py --data-root", root, "--output outputs")


if __name__ == "__main__":
    main()
