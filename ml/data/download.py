#!/usr/bin/env python3
"""Download training data from S3 to ml/data/raw/.

Usage
-----
    python ml/data/download.py              # download all
    python ml/data/download.py --file mtsamples.csv
    python ml/data/download.py --file synthea/  # download synthea directory

Requires AWS credentials configured via `aws configure` or environment variables.
Bucket: s3://anilla-ml-data
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BUCKET = "s3://anilla-ml-data"
RAW_DIR = Path(__file__).parent / "raw"

FILES = [
    "raw/mtsamples.csv",
    "raw/synthea/",
]


def download(s3_key: str) -> None:
    dest = RAW_DIR / Path(s3_key).relative_to("raw")
    dest.parent.mkdir(parents=True, exist_ok=True)

    src = f"{BUCKET}/{s3_key}"
    cmd = ["aws", "s3", "cp", "--recursive", src, str(dest)] if s3_key.endswith("/") \
        else ["aws", "s3", "cp", src, str(dest)]

    print(f"Downloading {src} → {dest}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"Failed to download {src}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=None, help="Specific file or prefix to download")
    args = parser.parse_args()

    targets = [f"raw/{args.file}"] if args.file else FILES
    for target in targets:
        download(target)
    print("Done.")


if __name__ == "__main__":
    main()
