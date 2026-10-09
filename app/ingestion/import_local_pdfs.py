
"""Import manually downloaded Supreme Court judgment PDFs.

This script processes local files only. It does not make network requests.
It validates PDF structure, extracts text, calculates SHA-256 hashes,
and records imports in the existing download manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

DOWNLOAD_DIR = Path("data/ingestion/downloaded")
MANIFEST = Path("data/ingestion/download_manifest.jsonl")
MAX_BYTES = 80 * 1024 * 1024


def read_manifest() -> tuple[set[str], set[str]]:
    seen_hashes: set[str] = set()
    seen_names: set[str] = set()

    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if row.get("sha256"):
                    seen_hashes.add(row["sha256"])
                if row.get("file_name"):
                    seen_names.add(row["file_name"])
            except json.JSONDecodeError:
                continue

    return seen_hashes, seen_names


def safe_name(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return (cleaned or "sci_judgment")[:100]


def extract_title(text: str, fallback: str) -> str:
    """Use a likely case-title line, falling back to the filename."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for i, line in enumerate(lines[:100]):
        if re.search(r"\bVERSUS\b|\bVS\.?\b", line, re.IGNORECASE):
            before = lines[i - 1] if i > 0 else ""
            after = lines[i + 1] if i + 1 < len(lines) else ""
            candidate = f"{before} vs. {after}".strip(" .")
            if len(candidate) >= 8:
                return candidate[:200]

    return fallback


def import_pdf(
    source: Path,
    source_url: str | None,
    seen_hashes: set[str],
) -> bool:
    if not source.exists() or not source.is_file():
        print(f"SKIP: File not found: {source}")
        return False

    if source.suffix.lower() != ".pdf":
        print(f"SKIP: Not a .pdf file: {source}")
        return False

    size = source.stat().st_size
    if size == 0 or size > MAX_BYTES:
        print(f"SKIP: Empty or oversized file ({size:,} bytes): {source}")
        return False

    try:
        with source.open("rb") as file:
            if file.read(5) != b"%PDF-":
                print(f"SKIP: Invalid PDF signature: {source}")
                return False

        # Validate that PyMuPDF can open the document and extract text.
        with fitz.open(source) as document:
            if document.is_encrypted:
                print(f"SKIP: Encrypted PDF needs separate review: {source}")
                return False

            if len(document) == 0:
                print(f"SKIP: PDF has no pages: {source}")
                return False

            text = "\n".join(page.get_text() for page in document[:5]).strip()
            page_count = len(document)

        if len(text) < 40:
            print(
                f"REVIEW REQUIRED: Very little extractable text in {source.name}. "
                "It may be a scanned PDF; OCR may be needed."
            )
            return False

        digest = hashlib.sha256(source.read_bytes()).hexdigest()

        if digest in seen_hashes:
            print(f"SKIP: Duplicate content (SHA-256): {source.name}")
            return False

        title = extract_title(text, source.stem)
        filename = f"{safe_name(source.stem)}_{digest[:12]}.pdf"

        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        destination = DOWNLOAD_DIR / filename

        if destination.exists():
            print(f"SKIP: Destination already exists: {destination}")
            return False

        # Copy to a temporary file first; preserve the original download.
        temporary = destination.with_suffix(".pdf.part")
        shutil.copyfile(source, temporary)
        temporary.replace(destination)

        record = {
            "case_title": title,
            "court": "Supreme Court of India",
            "document_type": "Judgment",
            "source_url": source_url or "",
            "discovery_url": "",
            "import_method": "manual_browser_download",
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "sha256": digest,
            "file_name": filename,
            "file_path": str(destination).replace("\\", "/"),
            "bytes": size,
            "pages": page_count,
            "text_preview": text[:500],
        }

        with MANIFEST.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

        seen_hashes.add(digest)
        print(f"IMPORTED: {source.name}")
        print(f"  Case/title: {title}")
        print(f"  Pages: {page_count}")
        print(f"  Saved to: {destination}")
        print(f"  SHA-256: {digest}")
        return True

    except (OSError, ValueError, RuntimeError) as exc:
        print(f"IMPORT FAILED: {source} ({exc})")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import local PDF judgments into LegalMind AI."
    )
    parser.add_argument(
        "pdfs",
        nargs="+",
        help="Paths to PDF files downloaded manually through your browser",
    )
    parser.add_argument(
        "--source-url",
        default="",
        help="Optional official source page URL for this import",
    )
    args = parser.parse_args()

    seen_hashes, _ = read_manifest()
    imported = 0

    for item in args.pdfs:
        if import_pdf(Path(item).expanduser(), args.source_url or None, seen_hashes):
            imported += 1

    print(f"\nImport complete. New PDFs imported: {imported}")
    print(f"PDF directory: {DOWNLOAD_DIR}")
    print(f"Manifest: {MANIFEST}")
    print("The FAISS index has NOT been modified.")


if __name__ == "__main__":
    main()
