"""Read-only hybrid retrieval baseline using only the test Constitution PDF.

Text chunks, BM25, embeddings, and FAISS are created in memory. No production
index or metadata file is loaded, modified, or rebuilt.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz  # Ensure PyMuPDF is present before importing the project parser.
import numpy as np
from rank_bm25 import BM25Okapi

from app.documents.chunker import create_chunks
from app.documents.parser import extract_text_from_pdf
from app.embeddings.vector_store import FAISSVectorStore


ROOT = Path(__file__).resolve().parent
PDF_PATH = ROOT / "data" / "test_constitutional_pdfs" / "constitution of india.pdf"
REPORT_PATH = ROOT / "constitution_retrieval_baseline.txt"
TOP_K = 5
RRF_CONSTANT = 60
SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30
EXCERPT_CHARS = 420

# Expected passages/pages are a review guide, not automatic relevance labels.
EVALUATION_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "Q01",
        "question": "Which freedoms are protected by Article 19(1)?",
        "expected_pages": (40, 41),
        "expected_passage": "Clauses (a)-(e) and (g): speech/expression, assembly, associations, movement, residence, and occupation/trade/business; clause (f) is omitted.",
    },
    {
        "id": "Q02",
        "question": "Which provision protects freedom of speech and expression?",
        "expected_pages": (40,),
        "expected_passage": "Article 19(1)(a).",
    },
    {
        "id": "Q03",
        "question": "What restrictions may apply to Article 19(1)(a)?",
        "expected_pages": (41,),
        "expected_passage": "Article 19(2), including grounds such as public order, security of the State, decency or morality, contempt of court, defamation, and incitement to an offence.",
    },
    {
        "id": "Q04",
        "question": "What right allows citizens to assemble peacefully without arms?",
        "expected_pages": (40,),
        "expected_passage": "Article 19(1)(b).",
    },
    {
        "id": "Q05",
        "question": "What right covers forming associations or unions?",
        "expected_pages": (40,),
        "expected_passage": "Article 19(1)(c), including associations, unions, or co-operative societies.",
    },
    {
        "id": "Q06",
        "question": "What right allows citizens to move freely throughout India?",
        "expected_pages": (40,),
        "expected_passage": "Article 19(1)(d).",
    },
    {
        "id": "Q07",
        "question": "What right covers residing and settling in any part of India?",
        "expected_pages": (41,),
        "expected_passage": "Article 19(1)(e).",
    },
    {
        "id": "Q08",
        "question": "What right covers practising a profession or carrying on a trade or business?",
        "expected_pages": (41,),
        "expected_passage": "Article 19(1)(g).",
    },
    {
        "id": "Q09",
        "question": "What does Article 21 say about life and personal liberty?",
        "expected_pages": (42,),
        "expected_passage": "No person shall be deprived of life or personal liberty except according to procedure established by law.",
    },
    {
        "id": "Q10",
        "question": "What does Article 21A require regarding children's education?",
        "expected_pages": (42,),
        "expected_passage": "The State shall provide free and compulsory education to children aged six to fourteen, as determined by law.",
    },
    {
        "id": "Q11",
        "question": "What protections does Article 20 provide against repeated punishment and compelled testimony?",
        "expected_pages": (42,),
        "expected_passage": "Article 20(2) addresses repeated prosecution and punishment for the same offence; Article 20(3) protects an accused from being compelled to be a witness against himself.",
    },
    {
        "id": "Q12",
        "question": "What safeguards does Article 22 provide following arrest?",
        "expected_pages": (42,),
        "expected_passage": "The arrested person must be informed of the grounds of arrest and may consult and be defended by a legal practitioner of choice.",
    },
    {
        "id": "Q13",
        "question": "What does Article 14 guarantee?",
        "expected_pages": (37,),
        "expected_passage": "Equality before the law and equal protection of the laws.",
    },
    {
        "id": "Q14",
        "question": "What provision provides freedom of speech in Parliament?",
        "expected_pages": (78,),
        "expected_passage": "Article 105(1), freedom of speech in Parliament, subject to the Constitution and parliamentary rules.",
    },
    {
        "id": "Q15",
        "question": "What provision provides freedom of speech in State Legislatures?",
        "expected_pages": (118,),
        "expected_passage": "Article 194(1), freedom of speech in a State Legislature, subject to the Constitution and legislative rules.",
    },
)


def tokenize(text: str) -> list[str]:
    """Match HybridRetriever.tokenize exactly, without initializing that class."""
    return re.findall(r"[a-z]+(?:'[a-z]+)?|\d+[a-z]?(?:\(\d+\))*", text.lower())


def compact(text: str, limit: int = EXCERPT_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def result_key(result: dict[str, Any]) -> tuple[str, ...]:
    metadata = result["metadata"]
    source_file = metadata.get("source_file", "unknown")
    chunk_id = metadata.get("chunk_id")
    if chunk_id is not None:
        return str(source_file), str(chunk_id)
    text = " ".join(str(metadata.get("text", "")).lower().split())
    return str(source_file), str(metadata.get("page_number", "unknown")), text


def fuse_rankings(
    semantic_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    """Apply the production weighted reciprocal rank fusion and dedup rules."""
    combined: dict[tuple[str, ...], dict[str, Any]] = {}
    for rank, result in enumerate(semantic_results, start=1):
        key = result_key(result)
        combined.setdefault(key, {
            "metadata": result["metadata"],
            "semantic_score": 0.0,
            "keyword_score": 0.0,
            "semantic_rank": None,
            "keyword_rank": None,
        })
        combined[key]["semantic_score"] = float(result["score"])
        combined[key]["semantic_rank"] = rank

    for rank, result in enumerate(keyword_results, start=1):
        key = result_key(result)
        combined.setdefault(key, {
            "metadata": result["metadata"],
            "semantic_score": 0.0,
            "keyword_score": 0.0,
            "semantic_rank": None,
            "keyword_rank": None,
        })
        combined[key]["keyword_score"] = float(result["score"])
        combined[key]["keyword_rank"] = rank

    results = []
    for item in combined.values():
        semantic_rank = item["semantic_rank"]
        keyword_rank = item["keyword_rank"]
        score = (
            (SEMANTIC_WEIGHT / (RRF_CONSTANT + semantic_rank)
             if semantic_rank is not None else 0.0)
            +
            (KEYWORD_WEIGHT / (RRF_CONSTANT + keyword_rank)
             if keyword_rank is not None else 0.0)
        )
        results.append({
            "score": score,
            "semantic_score": item["semantic_score"],
            "keyword_score": item["keyword_score"],
            "semantic_rank": semantic_rank,
            "keyword_rank": keyword_rank,
            "metadata": item["metadata"],
        })

    results.sort(key=lambda item: item["score"], reverse=True)

    unique_results = []
    seen_passages = set()
    for result in results:
        metadata = result["metadata"]
        text = " ".join(str(metadata.get("text", "")).lower().split())
        passage_key = (
            metadata.get("source_file", "unknown"),
            metadata.get("page_number", "unknown"),
            text,
        )
        if passage_key in seen_passages:
            continue
        seen_passages.add(passage_key)
        unique_results.append(result)
        if len(unique_results) >= top_k:
            break
    return unique_results


def build_report_header(pdf_hash: str, page_count: int, chunks: list[dict[str, Any]]) -> list[str]:
    return [
        "LEGALMIND AI — CONSTITUTION RETRIEVAL BASELINE",
        "=" * 78,
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Input PDF: {PDF_PATH}",
        f"PDF SHA-256: {pdf_hash}",
        f"PDF pages: {page_count}; temporary chunks: {len(chunks)}",
        "Chunking: existing parser/chunker; 1,200 characters, 200 overlap, page-bounded.",
        "Page references: one-based physical PDF page positions.",
        "Production data: not loaded or changed (no FAISS/metadata/BM25 production files accessed).",
        "Temporary retrieval: in-memory BM25 and in-memory FAISS IndexFlatIP only.",
        f"Fusion: {SEMANTIC_WEIGHT:.2f}/(60 + semantic rank) + {KEYWORD_WEIGHT:.2f}/(60 + keyword rank); top {TOP_K} per method, then production-style dedup.",
        "Embedding: project EmbeddingModel; normalized embeddings; offline mode enforced.",
        "Human judgments: none supplied; metrics are intentionally not computed.",
        "",
    ]


def run_evaluation() -> tuple[list[str], str | None]:
    if not PDF_PATH.is_file():
        return [
            "LEGALMIND AI — CONSTITUTION RETRIEVAL BASELINE",
            "=" * 78,
            f"BLOCKED: input PDF not found: {PDF_PATH}",
            "Save the official PDF at the path above and rerun.",
        ], "input PDF not found"

    try:
        pages = extract_text_from_pdf(str(PDF_PATH))
        chunks = create_chunks(
            pages,
            chunk_size=1200,
            overlap=200,
            case_metadata={
                "case_name": "Constitution of India",
                "document_type": "constitution",
                "jurisdiction": "India",
                "source_file": PDF_PATH.name,
                "acts": [],
                "sections": [],
            },
        )
    except Exception as exc:
        return [
            "LEGALMIND AI — CONSTITUTION RETRIEVAL BASELINE",
            "=" * 78,
            f"BLOCKED: PDF extraction/chunking failed: {type(exc).__name__}: {exc}",
            "No production files were accessed or changed.",
        ], f"PDF extraction/chunking failed: {type(exc).__name__}: {exc}"

    pdf_hash = hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()
    page_count = max((int(page["page_number"]) for page in pages), default=0)
    lines = build_report_header(pdf_hash, page_count, chunks)

    if not chunks:
        lines.extend(["BLOCKED: no extractable PDF text produced chunks.", ""])
        return lines, "no extractable PDF text"

    tokenized_chunks = [tokenize(str(chunk.get("text") or "")) for chunk in chunks]
    bm25 = BM25Okapi(tokenized_chunks)

    # No model download or external request is allowed; use only local cached weights.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        from app.embeddings.embeddings import EmbeddingModel

        model = EmbeddingModel()
        document_embeddings = np.asarray(
            model.generate_embeddings([str(chunk["text"]) for chunk in chunks]),
            dtype=np.float32,
        )
        if document_embeddings.ndim != 2 or document_embeddings.shape[0] != len(chunks):
            raise RuntimeError("Embedding model returned an unexpected document-vector shape.")

        # Build an ephemeral vector index in memory. Never call load() or save().
        vector_store = FAISSVectorStore(dimension=int(document_embeddings.shape[1]))
        vector_store.add_embeddings(document_embeddings, chunks)
    except Exception as exc:
        lines.extend([
            "SEMANTIC/HYBRID RESULTS UNAVAILABLE",
            "The existing embedding model could not be loaded or used offline; no network fallback was attempted.",
            f"Blocker: {type(exc).__name__}: {' '.join(str(exc).split())[:400]}",
            "BM25-only rankings are not presented as hybrid results.",
            "",
        ])
        return lines, "embedding model unavailable offline"

    lines.extend([
        f"Extracted non-empty pages: {len(pages)}",
        "Semantic model loaded from local availability; offline flags were set before model initialization.",
        "",
        "RANKED HYBRID RESULTS",
        "=" * 78,
    ])

    try:
        for case in EVALUATION_CASES:
            query = case["question"]
            query_embedding = np.asarray(
                model.generate_embeddings([query])[0],
                dtype=np.float32,
            )
            semantic_results = vector_store.search(query_embedding, top_k=TOP_K)

            query_tokens = tokenize(query)
            keyword_scores = bm25.get_scores(query_tokens)
            keyword_indices = np.argsort(keyword_scores)[::-1][:TOP_K]
            keyword_results = [
                {"score": float(keyword_scores[index]), "metadata": chunks[int(index)]}
                for index in keyword_indices
            ]

            hybrid_results = fuse_rankings(semantic_results, keyword_results, TOP_K)
            lines.extend([
                "",
                f"{case['id']}: {query}",
                f"Expected source passage/page(s): PDF page(s) {', '.join(map(str, case['expected_pages']))}; {case['expected_passage']}",
            ])
            if not hybrid_results:
                lines.append("  No hybrid results.")
                continue

            for rank, result in enumerate(hybrid_results, start=1):
                metadata = result["metadata"]
                bm25_rank = result["keyword_rank"]
                semantic_rank = result["semantic_rank"]
                lines.append(
                    f"  #{rank} hybrid={result['score']:.8f} | "
                    f"BM25 rank={bm25_rank if bm25_rank is not None else '—'} "
                    f"score={result['keyword_score']:.6f} | "
                    f"semantic rank={semantic_rank if semantic_rank is not None else '—'} "
                    f"cosine={result['semantic_score']:.6f} | "
                    f"page={metadata.get('page_number', 'unknown')} | "
                    f"source={metadata.get('source_file', 'unknown')}"
                )
                lines.append(f"     Excerpt: {compact(str(metadata.get('text') or ''))}")

        lines.extend([
            "",
            "HUMAN REVIEW — RELEVANCE LABELS",
            "=" * 78,
            "No relevance judgments have been assigned by this script.",
            "For each query/result above, a reviewer should label the passage as exactly one of:",
            "  direct | partial | related | wrong",
            "Do not treat expected page references as automatic relevance labels.",
        ])
        for case in EVALUATION_CASES:
            lines.append(f"{case['id']} labels: R1 [UNJUDGED]  R2 [UNJUDGED]  R3 [UNJUDGED]  R4 [UNJUDGED]  R5 [UNJUDGED]")

        lines.extend([
            "",
            "METRICS",
            "=" * 78,
            "Recall@5: NOT COMPUTED — no human relevance labels supplied.",
            "MRR@5: NOT COMPUTED — no human relevance labels supplied.",
            "Top-result direct-answer rate: NOT COMPUTED — no human relevance labels supplied.",
            "Expected passages/pages are listed for review, but they are not used as fabricated judgments.",
            "",
            "SAFETY / SCOPE",
            "=" * 78,
            "Only the test Constitution PDF was parsed as a source document.",
            "The production HybridRetriever was not instantiated; production FAISS, metadata, and BM25 inputs were not loaded.",
            "Only a temporary in-memory BM25 model and FAISS vector store were created.",
            "No downloads, external APIs, LLM calls, or production index writes were made.",
        ])
    except Exception as exc:
        lines.extend([
            "",
            f"BLOCKED DURING QUERY EVALUATION: {type(exc).__name__}: {' '.join(str(exc).split())[:400]}",
            "Results may be incomplete; do not treat them as a complete baseline.",
        ])
        return lines, "query evaluation failed"

    return lines, None


def main() -> None:
    lines, blocker = run_evaluation()
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"\nReport saved to: {REPORT_PATH}")
    if blocker:
        print(f"Diagnostic status: BLOCKED — {blocker}")


if __name__ == "__main__":
    main()
