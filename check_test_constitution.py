"""Inspect constitutional PDFs in data/test_constitutional_pdfs/ (read-only)."""
from __future__ import annotations

import re
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # Report a useful message instead of a traceback.
    fitz = None
    FITZ_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
else:
    FITZ_IMPORT_ERROR = ""


ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "data" / "test_constitutional_pdfs"
PHRASES = (
    "Article 19",
    "Article 21",
    "freedom of speech and expression",
    "right to life",
    "personal liberty",
)
SNIPPET_CONTEXT = 100
SNIPPET_MAX_CHARS = 260


def make_pattern(phrase: str) -> re.Pattern[str]:
    """Match case-insensitively and allow line breaks between phrase words."""
    words = phrase.split()
    return re.compile(r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b", re.IGNORECASE)


PATTERNS = {phrase: make_pattern(phrase) for phrase in PHRASES}


def excerpt(text: str, start: int, end: int) -> str:
    left = max(0, start - SNIPPET_CONTEXT)
    right = min(len(text), end + SNIPPET_CONTEXT)
    snippet = " ".join(text[left:right].split())
    if left:
        snippet = "..." + snippet
    if right < len(text):
        snippet += "..."
    if len(snippet) > SNIPPET_MAX_CHARS:
        snippet = snippet[: SNIPPET_MAX_CHARS - 3].rstrip() + "..."
    return snippet


def inspect_pdf(pdf_path: Path) -> None:
    print(f"\nPDF: {pdf_path.name}")
    if fitz is None:
        print("  Pages: unknown")
        print("  Text extraction: unavailable (PyMuPDF/fitz could not be imported)")
        print(f"  Import error: {FITZ_IMPORT_ERROR}")
        return

    pages: list[str] = []
    extraction_errors: list[tuple[int, str]] = []
    try:
        with fitz.open(str(pdf_path)) as document:
            page_count = len(document)
            for page_index in range(page_count):
                try:
                    page_text = document.load_page(page_index).get_text("text") or ""
                    pages.append(page_text)
                except Exception as exc:  # Keep checking later pages.
                    pages.append("")
                    extraction_errors.append((page_index + 1, f"{type(exc).__name__}: {exc}"))
    except Exception as exc:  # A corrupt/unsupported PDF must not stop the scan.
        print("  Pages: unknown")
        print("  Text extraction: failed (could not open PDF)")
        print(f"  Error: {type(exc).__name__}: {exc}")
        print("  Phrase results: not assessable because the PDF could not be read.")
        return

    text_pages = sum(bool(page.strip()) for page in pages)
    print(f"  Pages: {page_count}")
    if extraction_errors:
        print(f"  Text extraction: partial ({text_pages}/{page_count} pages contain text; page errors occurred)")
        for page_number, error in extraction_errors:
            print(f"  Page {page_number} extraction error: {error}")
    elif text_pages:
        print(f"  Text extraction: succeeds ({text_pages}/{page_count} pages contain text)")
    else:
        print(f"  Text extraction: no extractable text (0/{page_count} pages contain text)")

    if not text_pages:
        print("  Phrase results: not assessable because no text could be extracted.")
        return

    for phrase, pattern in PATTERNS.items():
        page_matches: list[tuple[int, str]] = []
        for page_number, page_text in enumerate(pages, start=1):
            match = pattern.search(page_text)
            if match:
                page_matches.append((page_number, excerpt(page_text, match.start(), match.end())))

        if page_matches:
            pages_text = ", ".join(str(page_number) for page_number, _ in page_matches)
            print(f"  {phrase}: found on page(s) {pages_text}")
            for page_number, text_excerpt in page_matches:
                print(f"    Page {page_number} excerpt: {text_excerpt}")
        elif extraction_errors:
            print(f"  {phrase}: no match in extracted text; some pages had extraction errors")
        else:
            print(f"  {phrase}: absent from extracted text")


def main() -> None:
    print("Constitution PDF text diagnostic (read-only)")
    print(f"PDF folder: {PDF_DIR}")

    if not PDF_DIR.is_dir():
        print("Folder not found. Save the official English Constitution PDF in this folder, then run this script again.")
        return

    try:
        pdf_paths = sorted(
            (path for path in PDF_DIR.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
            key=lambda path: path.name.casefold(),
        )
    except OSError as exc:
        print(f"Could not list the PDF folder: {type(exc).__name__}: {exc}")
        return

    print(f"PDFs found: {len(pdf_paths)}")
    if not pdf_paths:
        print("No PDFs found. Save the official English Constitution PDF in:")
        print(f"  {PDF_DIR}")
        return

    for pdf_path in pdf_paths:
        inspect_pdf(pdf_path)

    print("\nNo files were modified; no internet, external APIs, or LLMs were used.")


if __name__ == "__main__":
    main()
