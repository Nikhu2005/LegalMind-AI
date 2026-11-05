"""Read-only diagnostics for downloaded PDFs and the existing legal index.

This script never downloads files or writes to the PDF, metadata, or FAISS index.
Run it from any working directory with the project's Python environment.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "data" / "ingestion" / "downloaded"
METADATA_PATH = ROOT / "data" / "metadata.json"
FAISS_PATH = ROOT / "data" / "legal_index.faiss"

TARGETS = (
    "Article 19",
    "Article 21",
    "freedom of speech",
    "right to life",
)
PREVIEW_CHARS = 280
SAMPLE_CHARS = 360


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Match a phrase case-insensitively, allowing PDF line breaks as spaces."""
    parts = [re.escape(part) for part in phrase.split()]
    return re.compile(r"\s+".join(parts), re.IGNORECASE)


PATTERNS = {phrase: phrase_pattern(phrase) for phrase in TARGETS}


def compact(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def inspect_pdfs() -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    pdf_paths = sorted(
        (path for path in PDF_DIR.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: str(path).casefold(),
    ) if PDF_DIR.is_dir() else []

    print("=" * 78)
    print(f"PDF directory: {PDF_DIR}")
    print(f"Total PDFs: {len(pdf_paths)}")
    print("=" * 78)

    pdf_records: list[dict[str, Any]] = []
    phrase_files: dict[str, list[tuple[str, list[int]]]] = {
        phrase: [] for phrase in TARGETS
    }

    for path in pdf_paths:
        pages: list[str] = []
        page_count: int | None = None
        page_errors: list[tuple[int, str]] = []
        open_error: str | None = None

        try:
            with fitz.open(path) as document:
                page_count = len(document)
                for page_index in range(page_count):
                    try:
                        page_text = document.load_page(page_index).get_text("text") or ""
                        pages.append(page_text)
                    except Exception as exc:  # Continue with the remaining pages.
                        pages.append("")
                        page_errors.append((page_index + 1, f"{type(exc).__name__}: {exc}"))
        except Exception as exc:  # A corrupt PDF must not stop the directory scan.
            open_error = f"{type(exc).__name__}: {exc}"

        text_pages = sum(bool(page.strip()) for page in pages)
        if open_error:
            status = "OPEN ERROR"
        elif page_errors:
            status = "PARTIAL EXTRACTION ERROR"
        elif text_pages:
            status = "TEXT EXTRACTED"
        else:
            status = "NO EXTRACTABLE TEXT"

        print(f"\nPDF: {path.relative_to(PDF_DIR)}")
        print(f"  Pages: {page_count if page_count is not None else 'unknown'}")
        print(f"  Text extraction: {status} ({text_pages}/{page_count or 0} pages contain text)")
        if open_error:
            print(f"  Error: {open_error}")
        for page_number, error in page_errors:
            print(f"  Page {page_number} extraction error: {error}")

        matches: dict[str, list[int]] = {}
        for phrase, pattern in PATTERNS.items():
            matching_pages = [
                page_number
                for page_number, page_text in enumerate(pages, start=1)
                if pattern.search(page_text)
            ]
            if matching_pages:
                matches[phrase] = matching_pages
                phrase_files[phrase].append((path.name, matching_pages))

        if matches:
            print("  Target phrase matches:")
            for phrase, page_numbers in matches.items():
                print(f"    {phrase}: page(s) {', '.join(map(str, page_numbers))}")
        elif not open_error:
            if text_pages:
                print("  Target phrase matches: none of the four phrases")
            else:
                print("  Target phrase matches: not assessable (no extractable text)")

        for page_number in range(1, min(3, len(pages)) + 1):
            preview = compact(pages[page_number - 1], PREVIEW_CHARS)
            print(f"  Preview page {page_number}: {preview or '[no extractable text]'}")

        pdf_records.append({
            "path": path,
            "page_count": page_count,
            "pages": pages,
            "status": status,
            "open_error": open_error,
        })

    print("\n" + "=" * 78)
    print("PDF PHRASE SUMMARY")
    for phrase in TARGETS:
        print(f"\n{phrase}:")
        if phrase_files[phrase]:
            for filename, page_numbers in phrase_files[phrase]:
                print(f"  {filename}: page(s) {', '.join(map(str, page_numbers))}")
        else:
            print("  No extracted-text matches in readable PDFs.")

    # Key by lowercase basename because metadata stores the source filename.
    pages_by_filename = {
        record["path"].name.casefold(): record["pages"]
        for record in pdf_records
        if not record["open_error"]
    }
    return pdf_records, pages_by_filename


def load_chunks() -> tuple[list[dict[str, Any]], list[str]]:
    if not METADATA_PATH.is_file():
        print(f"\nMetadata file not found: {METADATA_PATH}")
        return [], []

    try:
        with METADATA_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception as exc:
        print(f"\nCould not read metadata JSON: {type(exc).__name__}: {exc}")
        return [], []

    if isinstance(data, list):
        chunks = data
        schema_description = ["top-level JSON array"]
    elif isinstance(data, dict) and isinstance(data.get("chunks"), list):
        chunks = data["chunks"]
        schema_description = ["top-level object", *data.keys()]
    else:
        print("\nUnsupported metadata schema; expected a list of chunks")
        if isinstance(data, dict):
            print(f"Top-level keys: {', '.join(map(str, data.keys()))}")
        else:
            print(f"Top-level JSON type: {type(data).__name__}")
        return [], []

    first_record = next((item for item in chunks if isinstance(item, dict)), {})
    fields = sorted(first_record.keys())
    print("\n" + "=" * 78)
    print(f"Metadata file: {METADATA_PATH}")
    print(f"Schema: {'; '.join(map(str, schema_description))}")
    print(f"Chunk fields observed: {', '.join(fields) if fields else '[no records]'}")
    print(f"Total indexed chunks: {len(chunks)}")

    valid_chunks = [item for item in chunks if isinstance(item, dict)]
    sources = sorted({
        str(item.get("source_file"))
        for item in valid_chunks
        if item.get("source_file")
    }, key=str.casefold)
    print(f"Unique indexed source files: {len(sources)}")
    for source in sources:
        print(f"  {source}")

    return valid_chunks, fields


def inspect_index(
    chunks: list[dict[str, Any]],
    pages_by_filename: dict[str, list[str]],
) -> None:
    if not chunks:
        return

    print("\n" + "=" * 78)
    print("INDEXED PHRASE COUNTS AND SAMPLES")

    for phrase, pattern in PATTERNS.items():
        matches = [
            chunk for chunk in chunks
            if pattern.search(str(chunk.get("text") or ""))
        ]
        print(f"\n{phrase}: {len(matches)} matching chunk(s)")
        for chunk in matches[:3]:
            print(
                "  source_file={}; page_number={}; text={}".format(
                    chunk.get("source_file", "[missing]"),
                    chunk.get("page_number", "[missing]"),
                    compact(str(chunk.get("text") or ""), SAMPLE_CHARS),
                )
            )

    compared = defaultdict(int)
    mismatch_samples: list[str] = []
    for chunk in chunks:
        text = str(chunk.get("text") or "")
        source = str(chunk.get("source_file") or "").replace("\\", "/").split("/")[-1]
        if not text.strip() or not source:
            compared["missing_source_or_text"] += 1
            continue

        source_pages = pages_by_filename.get(source.casefold())
        if source_pages is None:
            compared["source_pdf_missing_or_unreadable"] += 1
            continue

        try:
            page_number = int(chunk.get("page_number"))
        except (TypeError, ValueError):
            compared["missing_or_invalid_page_number"] += 1
            continue

        if not 1 <= page_number <= len(source_pages):
            compared["page_number_out_of_range"] += 1
            if len(mismatch_samples) < 5:
                mismatch_samples.append(f"{source}, invalid page {page_number}")
            continue

        chunk_text = normalized(text)
        page_text = normalized(source_pages[page_number - 1])
        if chunk_text and chunk_text in page_text:
            compared["text_matches_source_page"] += 1
        else:
            compared["text_not_found_on_source_page"] += 1
            if len(mismatch_samples) < 5:
                mismatch_samples.append(
                    f"{source}, page {page_number}: {compact(text, 120)}"
                )

    total = len(chunks)
    matched = compared["text_matches_source_page"]
    print("\nINDEX-TO-PDF CORRESPONDENCE")
    print(f"  Chunks checked: {total}")
    print(f"  Text exactly found on declared PDF page (whitespace-normalized): {matched}")
    for label in (
        "source_pdf_missing_or_unreadable",
        "text_not_found_on_source_page",
        "page_number_out_of_range",
        "missing_or_invalid_page_number",
        "missing_source_or_text",
    ):
        if compared[label]:
            print(f"  {label.replace('_', ' ')}: {compared[label]}")
    if total and matched == total:
        print("  Finding: every indexed chunk matches its recorded source PDF page.")
    elif matched:
        print("  Finding: some indexed text matches; investigate the unmatched categories above.")
    else:
        print("  Finding: no indexed chunk could be confirmed against an extracted source page.")
    for sample in mismatch_samples:
        print(f"  Mismatch sample: {sample}")

    inspect_faiss_count(total)


def inspect_faiss_count(metadata_chunk_count: int) -> None:
    print("\nFAISS INDEX CHECK")
    if not FAISS_PATH.is_file():
        print(f"  Index file not found: {FAISS_PATH}")
        return
    try:
        import faiss

        index = faiss.read_index(str(FAISS_PATH))
        vector_count = int(index.ntotal)
        print(f"  FAISS vectors: {vector_count}")
        print(f"  Metadata chunks: {metadata_chunk_count}")
        print(f"  Counts match: {'yes' if vector_count == metadata_chunk_count else 'NO'}")
    except Exception as exc:
        print(f"  Could not inspect FAISS index: {type(exc).__name__}: {exc}")


def inspect_index_timestamps(pdf_records: list[dict[str, Any]]) -> None:
    print("\nINDEX FRESHNESS TIMESTAMPS (a clue, not proof of correct content)")
    readable_stats = []
    for label, path in (
        ("metadata", METADATA_PATH),
        ("FAISS", FAISS_PATH),
    ):
        if path.is_file():
            modified = path.stat().st_mtime
            readable_stats.append((label, modified))
            print(f"  {label}: {datetime.fromtimestamp(modified).isoformat(sep=' ', timespec='seconds')}")
        else:
            print(f"  {label}: file missing")

    pdf_stats = [
        (record["path"], record["path"].stat().st_mtime)
        for record in pdf_records
        if record["path"].is_file()
    ]
    if not pdf_stats:
        print("  Source PDFs: no files to compare")
        return

    latest_pdf, latest_time = max(pdf_stats, key=lambda item: item[1])
    print(
        "  Newest PDF: {} ({})".format(
            latest_pdf.name,
            datetime.fromtimestamp(latest_time).isoformat(sep=" ", timespec="seconds"),
        )
    )
    if readable_stats:
        older_artifacts = [label for label, modified in readable_stats if modified < latest_time]
        if older_artifacts:
            print(
                "  Potentially stale by timestamp: "
                + ", ".join(older_artifacts)
                + " predates the newest PDF (confirm before rebuilding)."
            )
        else:
            print("  Both available index artifacts are at least as new as the PDFs.")


def main() -> None:
    print("LegalMind AI read-only PDF and index diagnostic")
    pdf_records, pages_by_filename = inspect_pdfs()
    chunks, _ = load_chunks()
    inspect_index(chunks, pages_by_filename)
    inspect_index_timestamps(pdf_records)

    no_text = sum(record["status"] == "NO EXTRACTABLE TEXT" for record in pdf_records)
    errors = sum(record["status"] in {"OPEN ERROR", "PARTIAL EXTRACTION ERROR"} for record in pdf_records)
    print("\n" + "=" * 78)
    print(
        f"PDF total: {len(pdf_records)}; PDFs with no extractable text: {no_text}; "
        f"PDFs with extraction/open errors: {errors}"
    )
    print("No files were modified; no network or LLM calls were made.")


if __name__ == "__main__":
    main()
