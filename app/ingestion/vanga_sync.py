"""Download English Supreme Court judgment PDFs from the vanga open dataset.

Source: https://registry.opendata.aws/indian-supreme-court-judgments/ (CC-BY-4.0).
The S3 bucket is public, so this uses plain HTTPS and needs no AWS account.
Downloads are sequential (no concurrency) to respect the dataset maintainers.

Files land in data/external/vanga/ (git-ignored). PDFs are then handed to
app.ingestion.import_local_pdfs, which de-duplicates by SHA-256 and does NOT
rebuild the search index.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

BUCKET_URL = "https://indian-supreme-court-judgments.s3.amazonaws.com"
DATASET_PAGE = "https://registry.opendata.aws/indian-supreme-court-judgments/"
DEST_ROOT = Path("data/external/vanga")
COPY_CHUNK_BYTES = 1024 * 1024
HTTP_TIMEOUT_SECONDS = 120
IMPORT_BATCH_SIZE = 100
IMPORTER_MODULE = "app.ingestion.import_local_pdfs"


def _tar_base_url(year: int, language: str) -> str:
    return f"{BUCKET_URL}/data/tar/year={year}/{language}"


def index_url(year: int, language: str = "english") -> str:
    return f"{_tar_base_url(year, language)}/{language}.index.json"


def part_urls(year: int, language: str, index: dict[str, Any]) -> list[str]:
    base = _tar_base_url(year, language)
    return [f"{base}/{part['name']}" for part in index["parts"]]


def load_index(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def download(url: str, destination: Path) -> Path:
    """Stream url to destination. Skips if the file already exists."""
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_SECONDS) as response:
        expected = int(response.headers.get("Content-Length", "0"))
        with partial.open("wb") as handle:
            shutil.copyfileobj(response, handle, COPY_CHUNK_BYTES)
    actual = partial.stat().st_size
    if expected and actual != expected:
        partial.unlink(missing_ok=True)
        raise OSError(f"Incomplete download for {url}: {actual} of {expected} bytes")
    partial.replace(destination)
    return destination


def extract_pdfs(tar_path: Path, out_dir: Path, limit: int | None = None) -> list[Path]:
    """Extract PDF members flat into out_dir, keeping only their basenames.

    Using the basename prevents path traversal ("../x.pdf") from archive members.
    Already-extracted files with the same size are skipped.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    accepted = 0  # counts already-extracted PDFs too, so --limit holds across reruns
    with tarfile.open(tar_path) as archive:
        for member in archive:
            if limit is not None and accepted >= limit:
                break
            if not member.isfile():
                continue
            name = Path(member.name).name
            if not name.lower().endswith(".pdf") or name in ("", ".", ".."):
                continue
            accepted += 1
            target = out_dir / name
            if target.exists() and target.stat().st_size == member.size:
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            with source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle, COPY_CHUNK_BYTES)
            written.append(target)
    return written


def sync_year(
    year: int, language: str, limit: int | None, keep_archives: bool
) -> list[Path]:
    year_dir = DEST_ROOT / f"year={year}" / language
    index_path = download(index_url(year, language), year_dir / f"{language}.index.json")
    index = load_index(index_path)

    pdf_dir = year_dir / "pdfs"
    for url in part_urls(year, language, index):
        if limit is not None and len(list(pdf_dir.glob("*.pdf"))) >= limit:
            break
        archive = download(url, year_dir / url.rsplit("/", 1)[-1])
        extract_pdfs(archive, pdf_dir, limit)
        if not keep_archives:
            archive.unlink()  # PDFs are extracted; free disk space
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    return pdfs if limit is None else pdfs[:limit]


def run_importer(pdfs: list[Path]) -> None:
    """Hand PDFs to the existing importer in batches (keeps command lines short)."""
    python = sys.executable
    for start in range(0, len(pdfs), IMPORT_BATCH_SIZE):
        batch = [str(p) for p in pdfs[start : start + IMPORT_BATCH_SIZE]]
        subprocess.run(
            [python, "-m", IMPORTER_MODULE, *batch, "--source-url", DATASET_PAGE],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync vanga open-dataset judgments.")
    parser.add_argument("--years", nargs="+", type=int, required=True, help="Years, e.g. 2023")
    parser.add_argument("--language", default="english", choices=["english", "regional"])
    parser.add_argument("--limit", type=int, default=None, help="Max PDFs per year (testing)")
    parser.add_argument(
        "--keep-archives",
        action="store_true",
        help="Keep the downloaded .tar files after extraction (uses more disk)",
    )
    parser.add_argument(
        "--import",
        dest="do_import",
        action="store_true",
        help="Also run the existing PDF importer on the downloaded files",
    )
    args = parser.parse_args()

    all_pdfs: list[Path] = []
    for year in args.years:
        pdfs = sync_year(year, args.language, args.limit, args.keep_archives)
        print(f"year={year}: {len(pdfs)} PDFs available in {DEST_ROOT}")
        all_pdfs.extend(pdfs)

    if args.do_import:
        run_importer(all_pdfs)
    print("Done. The FAISS index has NOT been rebuilt.")


if __name__ == "__main__":
    main()
