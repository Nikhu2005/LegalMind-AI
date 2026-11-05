"""Isolated read-only lexical/semantic retrieval test for the test Constitution PDF.

This script creates temporary chunks in memory. It deliberately does not create a
HybridRetriever instance, because that constructor loads the production FAISS
index and metadata file.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import fitz
import numpy as np

try:
    from rank_bm25 import BM25Okapi
except ImportError as exc:
    BM25Okapi = None
    BM25_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
else:
    BM25_IMPORT_ERROR = ""


ROOT = Path(__file__).resolve().parent
PDF_PATH = ROOT / "data" / "test_constitutional_pdfs" / "constitution of india.pdf"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
TOP_K = 5
EXCERPT_CHARS = 440

QUERIES = (
    "What fundamental rights are protected under Article 19 of the Constitution of India?",
    "What does Article 21 say about the right to life and personal liberty?",
    "Which provision protects freedom of speech and expression?",
)


def tokenize(text: str) -> list[str]:
    """Use the same tokenization expression as HybridRetriever.tokenize()."""
    return re.findall(r"[a-z]+(?:'[a-z]+)?|\d+[a-z]?(?:\(\d+\))*", text.lower())


def compact(text: str, limit: int = EXCERPT_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def read_pdf_pages(pdf_path: Path) -> tuple[list[dict[str, Any]], int, list[tuple[int, str]]]:
    pages: list[dict[str, Any]] = []
    errors: list[tuple[int, str]] = []
    with fitz.open(str(pdf_path)) as document:
        page_count = len(document)
        for page_index in range(page_count):
            page_number = page_index + 1
            try:
                text = document.load_page(page_index).get_text("text") or ""
            except Exception as exc:  # Continue extracting the rest of the PDF.
                text = ""
                errors.append((page_number, f"{type(exc).__name__}: {exc}"))
            pages.append({"page_number": page_number, "text": text})
    return pages, page_count, errors


def make_chunks(pages: list[dict[str, Any]], source_filename: str) -> list[dict[str, Any]]:
    """Create page-bounded chunks with only the metadata needed by this test."""
    chunks: list[dict[str, Any]] = []
    stride = CHUNK_SIZE - CHUNK_OVERLAP
    for page in pages:
        text = str(page.get("text") or "").strip()
        start = 0
        while start < len(text):
            chunk_text = text[start : start + CHUNK_SIZE].strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "source_file": source_filename,
                    "page_number": page["page_number"],
                })
            if start + CHUNK_SIZE >= len(text):
                break
            start += stride
    return chunks


def print_results(
    method: str,
    query: str,
    scores: np.ndarray,
    chunks: list[dict[str, Any]],
    *,
    top_k: int = TOP_K,
) -> None:
    print(f"\n{method} — {query}")
    if not len(scores):
        print("  No scores available.")
        return

    order = np.argsort(scores)[::-1][:top_k]
    if not np.any(scores > 0):
        print("  No positive matches; the displayed zero-score passages are tied and not meaningful rankings.")

    for rank, index in enumerate(order, start=1):
        chunk = chunks[int(index)]
        print(
            f"  {rank}. score={float(scores[index]):.6f}; "
            f"source={chunk['source_file']}; page={chunk['page_number']}"
        )
        print(f"     {compact(chunk['text'])}")


def run_lexical_test(chunks: list[dict[str, Any]]) -> None:
    if BM25Okapi is None:
        print(f"\nLexical test unavailable: rank_bm25 import failed: {BM25_IMPORT_ERROR}")
        return
    if not chunks:
        print("\nLexical test unavailable: no text chunks were extracted.")
        return

    tokenized_chunks = [tokenize(chunk["text"]) for chunk in chunks]
    bm25 = BM25Okapi(tokenized_chunks)
    for query in QUERIES:
        scores = np.asarray(bm25.get_scores(tokenize(query)), dtype=np.float32)
        print_results("LEXICAL BM25 (raw score)", query, scores, chunks)


def run_semantic_test(chunks: list[dict[str, Any]]) -> None:
    if not chunks:
        print("\nSemantic test unavailable: no text chunks were extracted.")
        return

    # Prevent Hugging Face / Transformers from attempting network access. The
    # existing project model is used only if its files are already cached locally.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    try:
        from app.embeddings.embeddings import EmbeddingModel

        model = EmbeddingModel()
        all_inputs = [*QUERIES, *(chunk["text"] for chunk in chunks)]
        embeddings = np.asarray(model.generate_embeddings(all_inputs), dtype=np.float32)
        query_vectors = embeddings[: len(QUERIES)]
        chunk_vectors = embeddings[len(QUERIES) :]
        if len(chunk_vectors) != len(chunks):
            print("\nSemantic test unavailable: embedding model returned an unexpected number of vectors.")
            return

        # EmbeddingModel normalizes vectors, so dot product is cosine similarity.
        for query, query_vector in zip(QUERIES, query_vectors):
            scores = np.asarray(chunk_vectors @ query_vector, dtype=np.float32)
            print_results("SEMANTIC COSINE SIMILARITY", query, scores, chunks)
    except Exception as exc:
        detail = " ".join(str(exc).split())[:300]
        print("\nSemantic test skipped: the existing embedding model could not be loaded offline.")
        print(f"  {type(exc).__name__}: {detail or '[no error detail]'}")
        print("  No model download or network fallback was attempted.")


def main() -> None:
    print("Isolated Constitution PDF retrieval diagnostic (read-only)")
    print(f"Input PDF: {PDF_PATH}")
    print("Production index: not loaded or modified")
    print("HybridRetriever: not instantiated; its constructor loads production FAISS/metadata.")
    print(
        "Inspected production interface: HybridRetriever() loads EmbeddingModel, "
        "data/legal_index.faiss, data/metadata.json, then builds BM25; "
        "search(question, top_k=5, court=None, case_name=None, act=None, "
        "section=None, document_type=None) combines semantic and keyword ranks."
    )

    if not PDF_PATH.is_file():
        print("\nPDF not found. Save the official Constitution PDF at the path shown above and run again.")
        return
    if BM25Okapi is None:
        print(f"\nLexical dependency unavailable: rank_bm25 import failed: {BM25_IMPORT_ERROR}")
        print("The PDF was not processed because the required lexical retrieval dependency is missing.")
        return

    try:
        pages, page_count, extraction_errors = read_pdf_pages(PDF_PATH)
    except Exception as exc:
        print(f"\nCould not open/read PDF: {type(exc).__name__}: {exc}")
        return

    text_page_count = sum(bool(str(page["text"]).strip()) for page in pages)
    if extraction_errors:
        extraction_status = f"PARTIAL ({text_page_count}/{page_count} pages contain text; page errors occurred)"
    elif text_page_count:
        extraction_status = f"SUCCESS ({text_page_count}/{page_count} pages contain text)"
    else:
        extraction_status = f"NO EXTRACTABLE TEXT (0/{page_count} pages contain text)"
    print(f"PDF pages: {page_count}")
    print(f"Text extraction: {extraction_status}")
    for page_number, error in extraction_errors:
        print(f"  Page {page_number} extraction error: {error}")

    chunks = make_chunks(pages, PDF_PATH.name)
    print(f"Temporary in-memory chunks: {len(chunks)}")
    print(f"Chunking: {CHUNK_SIZE} characters with {CHUNK_OVERLAP} character overlap, bounded to each page")
    print("Scores are local to this PDF test; BM25 scores are raw, and semantic scores are cosine similarities.")

    if not chunks:
        print("\nNo extracted text is available to rank; lexical and semantic tests were skipped.")
        return

    run_lexical_test(chunks)
    run_semantic_test(chunks)
    print("\nThis isolated test says nothing about production FAISS/BM25 retrieval quality.")
    print("No files were modified; no downloads, external APIs, or LLM calls were made.")


if __name__ == "__main__":
    main()
