"""Compare page-based and article-aware Constitution chunks offline.

All text, BM25 scores, embeddings, and similarities are held in memory. This
diagnostic never instantiates HybridRetriever or loads/saves a production index.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PDF_PATH = ROOT / "data" / "test_constitutional_pdfs" / "constitution of india.pdf"
REPORT_PATH = ROOT / "constitution_chunking_comparison.txt"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
TOP_K = 5
RRF_CONSTANT = 60
SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30
EXCERPT_CHARS = 300

# Keep the exact 15 questions and expected source references from the existing
# Constitution evaluation plan. Expected passages are review guides, not labels.
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

# The supplied English Constitution prints article headings as e.g.
# "19. Protection of certain rights ...". Keep this anchored to a line start.
ARTICLE_HEADER_RE = re.compile(
    r"(?m)^[ \t]*(?:(?:Article|ART\.?)\s+)?"
    r"(?P<article_id>\d{1,3}[A-Z]?)[.\u2013\u2014:-][ \t]+"
    r"(?P<title>[A-Z][^\r\n]{2,180})[ \t]*$"
)
CLAUSE_MARKER_RE = re.compile(r"(?<!\w)\((?P<clause>\d+[A-Z]?|[a-z]|[ivxlcdm]+)\)")
TOKEN_RE = re.compile(r"[a-z]+(?:'[a-z]+)?|\d+[a-z]?(?:\(\d+\))*")


def tokenize(text: str) -> list[str]:
    """Use the exact tokenizer expression from HybridRetriever.tokenize()."""
    return TOKEN_RE.findall(text.lower())


def compact(text: str, limit: int = EXCERPT_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def add_segment(
    article_records: dict[str | None, dict[str, Any]],
    article_id: str | None,
    title: str | None,
    page_number: int,
    page_text: str,
    start: int,
    end: int,
) -> None:
    raw = page_text[start:end]
    content = raw.strip()
    if not content:
        return

    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw) - len(raw.rstrip())
    page_start = start + leading
    page_end = end - trailing
    record = article_records.setdefault(
        article_id,
        {"article_id": article_id, "title": title, "segments": [], "text": ""},
    )
    if title and not record.get("title"):
        record["title"] = title

    separator = "\n" if record["text"] else ""
    unit_start = len(record["text"]) + len(separator)
    record["text"] += separator + content
    unit_end = unit_start + len(content)
    record["segments"].append(
        {
            "page_number": page_number,
            "page_start": page_start,
            "page_end": page_end,
            "unit_start": unit_start,
            "unit_end": unit_end,
        }
    )


def parse_article_units(
    pages: list[dict[str, Any]],
) -> tuple[dict[str | None, dict[str, Any]], dict[int, list[tuple[int, int, str | None]]]]:
    """Group text by detected article headings while tracking its PDF page spans."""
    article_records: dict[str | None, dict[str, Any]] = {}
    page_intervals: dict[int, list[tuple[int, int, str | None]]] = {}
    active_id: str | None = None
    active_title: str | None = None

    for page in pages:
        page_number = int(page["page_number"])
        text = str(page.get("text") or "")
        matches = list(ARTICLE_HEADER_RE.finditer(text))
        intervals: list[tuple[int, int, str | None]] = []
        cursor = 0

        for index, match in enumerate(matches):
            if cursor < match.start():
                intervals.append((cursor, match.start(), active_id))
                add_segment(
                    article_records, active_id, active_title, page_number,
                    text, cursor, match.start(),
                )

            active_id = match.group("article_id").upper()
            active_title = match.group("title").strip()
            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            intervals.append((match.start(), next_start, active_id))
            add_segment(
                article_records, active_id, active_title, page_number,
                text, match.start(), next_start,
            )
            cursor = next_start

        if not matches:
            intervals.append((0, len(text), active_id))
            add_segment(article_records, active_id, active_title, page_number, text, 0, len(text))
        elif cursor < len(text):
            # Normally the final heading interval reaches the page end. Retain any
            # remainder if unusual extraction formatting makes it shorter.
            intervals.append((cursor, len(text), active_id))
            add_segment(article_records, active_id, active_title, page_number, text, cursor, len(text))

        page_intervals[page_number] = intervals

    for record in article_records.values():
        record["page_spans"] = list(record["segments"])
    return article_records, page_intervals


def make_article_aware_chunks(
    article_records: dict[str | None, dict[str, Any]],
    source_filename: str,
) -> list[dict[str, Any]]:
    """Split within each detected article, preferring clause/paragraph boundaries."""
    chunks: list[dict[str, Any]] = []

    for article_id, record in article_records.items():
        text = str(record.get("text") or "")
        if not text.strip():
            continue
        title = str(record.get("title") or "").strip()
        cursor = 0
        chunk_number = 1

        while cursor < len(text):
            continuation = cursor > 0 and article_id is not None
            prefix = (
                f"Article {article_id} (continued): {title}\n"
                if continuation and title
                else f"Article {article_id} (continued)\n" if continuation
                else ""
            )
            source_limit = max(1, CHUNK_SIZE - len(prefix))
            hard_end = min(len(text), cursor + source_limit)
            end = hard_end

            if hard_end < len(text):
                clause_breaks = [
                    match.start()
                    for match in CLAUSE_MARKER_RE.finditer(text, cursor + source_limit // 2, hard_end)
                    if match.start() > cursor
                ]
                if clause_breaks:
                    end = clause_breaks[-1]
                else:
                    line_breaks = [
                        match.end()
                        for match in re.finditer(r"\n", text[cursor:hard_end])
                        if cursor + match.end() > cursor + source_limit // 2
                    ]
                    if line_breaks:
                        end = cursor + line_breaks[-1]
                    else:
                        sentence_breaks = [
                            match.end()
                            for match in re.finditer(r"[.;:!?][ \t]+", text[cursor:hard_end])
                            if cursor + match.end() > cursor + source_limit // 2
                        ]
                        if sentence_breaks:
                            end = cursor + sentence_breaks[-1]

            if end <= cursor:
                end = min(len(text), cursor + source_limit)
            body = text[cursor:end]
            page_numbers = sorted(
                {
                    int(span["page_number"])
                    for span in record["page_spans"]
                    if span["unit_start"] < end and span["unit_end"] > cursor
                }
            )
            clause_ids = list(dict.fromkeys(
                f"({match.group('clause')})"
                for match in CLAUSE_MARKER_RE.finditer(body)
            ))
            chunk_text = (prefix + body).strip()
            chunks.append(
                {
                    "chunk_id": f"article_{article_id or 'unassigned'}_chunk_{chunk_number}",
                    "page_number": page_numbers[0] if page_numbers else "unknown",
                    "page_numbers": page_numbers,
                    "text": chunk_text,
                    "source_file": source_filename,
                    "article_id": article_id,
                    "article_ids": [article_id] if article_id is not None else [],
                    "clause_ids": clause_ids,
                    "_article_source_spans": (
                        {article_id: [(cursor, end)]} if article_id is not None else {}
                    ),
                }
            )
            if end >= len(text):
                break

            # Retain approximately 200 characters of context. When a clause marker
            # is nearby, align the next chunk there to avoid cutting its identifier.
            desired_start = max(cursor + 1, end - CHUNK_OVERLAP)
            aligned_starts = [
                match.start()
                for match in CLAUSE_MARKER_RE.finditer(text, desired_start, end)
            ]
            next_cursor = aligned_starts[0] if aligned_starts else desired_start
            cursor = next_cursor if next_cursor > cursor else end
            chunk_number += 1

    return chunks


def enrich_page_chunks(
    chunks: list[dict[str, Any]],
    pages: list[dict[str, Any]],
    page_intervals: dict[int, list[tuple[int, int, str | None]]],
) -> list[dict[str, Any]]:
    """Attach article/clause diagnostics without changing the source chunk text."""
    page_texts = {int(page["page_number"]): str(page.get("text") or "") for page in pages}
    stride = CHUNK_SIZE - CHUNK_OVERLAP

    for chunk in chunks:
        page_number = int(chunk["page_number"])
        match = re.search(r"chunk_(\d+)$", str(chunk.get("chunk_id", "")))
        chunk_number = int(match.group(1)) if match else 1
        start = (chunk_number - 1) * stride
        end = min(len(page_texts.get(page_number, "")), start + CHUNK_SIZE)
        article_ids: list[str] = []
        for interval_start, interval_end, article_id in page_intervals.get(page_number, []):
            if article_id is not None and start < interval_end and end > interval_start:
                if article_id not in article_ids:
                    article_ids.append(article_id)

        chunk["page_numbers"] = [page_number]
        chunk["article_ids"] = article_ids
        chunk["article_id"] = article_ids[0] if len(article_ids) == 1 else None
        chunk["clause_ids"] = list(dict.fromkeys(
            f"({match.group('clause')})"
            for match in CLAUSE_MARKER_RE.finditer(str(chunk.get("text") or ""))
        ))
        chunk["_page_source_span"] = (page_number, start, end)
        # The full article-to-page mapping is attached by the caller below.
        chunk["_article_source_spans"] = {}

    return chunks


def map_page_chunks_to_articles(
    chunks: list[dict[str, Any]],
    article_records: dict[str | None, dict[str, Any]],
) -> None:
    """Translate source-page chunk intervals into offsets within each article."""
    for chunk in chunks:
        page_number, start, end = chunk["_page_source_span"]
        mapped: dict[str, list[tuple[int, int]]] = {}
        for article_id, record in article_records.items():
            if article_id is None:
                continue
            for span in record["page_spans"]:
                if int(span["page_number"]) != page_number:
                    continue
                overlap_start = max(start, int(span["page_start"]))
                overlap_end = min(end, int(span["page_end"]))
                if overlap_start < overlap_end:
                    unit_start = int(span["unit_start"]) + overlap_start - int(span["page_start"])
                    unit_end = int(span["unit_start"]) + overlap_end - int(span["page_start"])
                    mapped.setdefault(article_id, []).append((unit_start, unit_end))
        chunk["_article_source_spans"] = mapped


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
) -> list[dict[str, Any]]:
    """Match HybridRetriever's weighted RRF and its two deduplication stages."""
    combined: dict[tuple[str, ...], dict[str, Any]] = {}
    for rank, result in enumerate(semantic_results, start=1):
        key = result_key(result)
        combined.setdefault(key, {
            "metadata": result["metadata"], "semantic_score": 0.0,
            "keyword_score": 0.0, "semantic_rank": None, "keyword_rank": None,
        })
        combined[key]["semantic_score"] = float(result["score"])
        combined[key]["semantic_rank"] = rank

    for rank, result in enumerate(keyword_results, start=1):
        key = result_key(result)
        combined.setdefault(key, {
            "metadata": result["metadata"], "semantic_score": 0.0,
            "keyword_score": 0.0, "semantic_rank": None, "keyword_rank": None,
        })
        combined[key]["keyword_score"] = float(result["score"])
        combined[key]["keyword_rank"] = rank

    ranked: list[dict[str, Any]] = []
    for item in combined.values():
        semantic_rank = item["semantic_rank"]
        keyword_rank = item["keyword_rank"]
        rrf_score = (
            (SEMANTIC_WEIGHT / (RRF_CONSTANT + semantic_rank) if semantic_rank is not None else 0.0)
            + (KEYWORD_WEIGHT / (RRF_CONSTANT + keyword_rank) if keyword_rank is not None else 0.0)
        )
        ranked.append({**item, "score": rrf_score})
    ranked.sort(key=lambda item: item["score"], reverse=True)

    unique: list[dict[str, Any]] = []
    seen_passages: set[tuple[str, str, str]] = set()
    for result in ranked:
        metadata = result["metadata"]
        text = " ".join(str(metadata.get("text", "")).lower().split())
        passage_key = (
            str(metadata.get("source_file", "unknown")),
            str(metadata.get("page_number", "unknown")),
            text,
        )
        if passage_key in seen_passages:
            continue
        seen_passages.add(passage_key)
        unique.append(result)
        if len(unique) >= TOP_K:
            break
    return unique


def article_clause_spans(record: dict[str, Any]) -> list[tuple[str, int, int]]:
    """Return approximate leaf-clause spans for detecting clause boundary splits."""
    text = str(record.get("text") or "")
    markers = list(CLAUSE_MARKER_RE.finditer(text))
    numbered = [m for m in markers if m.group("clause")[0].isdigit()]
    spans: list[tuple[str, int, int]] = []

    if numbered:
        for index, major in enumerate(numbered):
            section_end = numbered[index + 1].start() if index + 1 < len(numbered) else len(text)
            children = [
                m for m in markers
                if major.end() <= m.start() < section_end and not m.group("clause")[0].isdigit()
            ]
            if children:
                for child_index, child in enumerate(children):
                    child_end = children[child_index + 1].start() if child_index + 1 < len(children) else section_end
                    spans.append((f"({major.group('clause')})({child.group('clause')})", child.start(), child_end))
            else:
                spans.append((f"({major.group('clause')})", major.start(), section_end))
    elif markers:
        for index, marker in enumerate(markers):
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            spans.append((f"({marker.group('clause')})", marker.start(), end))

    return [(label, start, end) for label, start, end in spans if end > start]


def pages_for_article_interval(record: dict[str, Any], start: int, end: int) -> list[int]:
    return sorted(
        {
            int(span["page_number"])
            for span in record.get("page_spans", [])
            if int(span["unit_start"]) < end and int(span["unit_end"]) > start
        }
    )


def chunking_diagnostics(
    strategy_name: str,
    chunks: list[dict[str, Any]],
    article_records: dict[str | None, dict[str, Any]],
) -> list[str]:
    lines = [f"{strategy_name}: {len(chunks)} chunks"]
    mixed = [chunk for chunk in chunks if len(chunk.get("article_ids", [])) > 1]
    if mixed:
        lines.append(f"  Chunks touching multiple article spans: {len(mixed)}")
        for chunk in mixed:
            pages = ",".join(map(str, chunk.get("page_numbers", []))) or "unknown"
            lines.append(
                f"    {chunk.get('chunk_id')} pages=[{pages}] articles={','.join(chunk['article_ids'])}"
            )
    else:
        lines.append("  Chunks touching multiple article spans: none detected")

    split_clauses: list[str] = []
    for article_id, record in article_records.items():
        if article_id is None:
            continue
        for clause_id, clause_start, clause_end in article_clause_spans(record):
            containing = []
            overlapping = []
            for chunk in chunks:
                spans = chunk.get("_article_source_spans", {}).get(article_id, [])
                if any(left < clause_end and right > clause_start for left, right in spans):
                    overlapping.append(str(chunk.get("chunk_id", "unknown")))
                if any(left <= clause_start and right >= clause_end for left, right in spans):
                    containing.append(str(chunk.get("chunk_id", "unknown")))
            if not containing and overlapping:
                pages = ",".join(map(str, pages_for_article_interval(record, clause_start, clause_end)))
                split_clauses.append(
                    f"    Article {article_id} {clause_id}, page(s) [{pages}], touched by chunks: {', '.join(overlapping)}"
                )

    if split_clauses:
        lines.append(f"  Clause spans not fully contained in any one chunk: {len(split_clauses)}")
        lines.extend(split_clauses)
    else:
        lines.append("  Clause spans not fully contained in a single chunk: none detected")
    lines.append("  Split detection is structural (source character spans), not a relevance judgment.")
    return lines


def focus_article_lines(
    strategy_name: str,
    chunks: list[dict[str, Any]],
    article_records: dict[str | None, dict[str, Any]],
) -> list[str]:
    lines = [f"{strategy_name}:"]
    for article_id, expected_pages in (("19", (40, 41)), ("21", (42,))):
        record = article_records.get(article_id)
        hits = [chunk for chunk in chunks if article_id in chunk.get("article_ids", [])]
        actual_pages = sorted({
            int(page)
            for chunk in hits
            for page in chunk.get("page_numbers", [])
            if str(page).isdigit()
        })
        clauses = list(dict.fromkeys(
            clause
            for chunk in hits
            for clause in chunk.get("clause_ids", [])
        ))
        if record is None and not hits:
            lines.append(f"  Article {article_id}: NOT DETECTED by heading parser; expected PDF page(s) {expected_pages}.")
            continue
        lines.append(
            f"  Article {article_id}: {len(hits)} associated chunk(s), page(s) {actual_pages}; "
            f"expected PDF page(s) {list(expected_pages)}; clause markers found {clauses or 'none'}"
        )
        if hits:
            for chunk in hits:
                pages = ",".join(map(str, chunk.get("page_numbers", []))) or "unknown"
                lines.append(
                    f"    {chunk.get('chunk_id')} pages=[{pages}] clauses={','.join(chunk.get('clause_ids', [])) or 'none'}"
                )
    return lines


def retrieve_for_strategy(
    chunks: list[dict[str, Any]],
    query_embeddings: Any,
    queries: tuple[str, ...],
    np: Any,
    BM25Okapi: Any,
    model: Any,
) -> dict[str, list[dict[str, Any]]]:
    tokenized_chunks = [tokenize(str(chunk.get("text") or "")) for chunk in chunks]
    bm25 = BM25Okapi(tokenized_chunks)
    doc_embeddings = np.asarray(
        model.generate_embeddings([str(chunk["text"]) for chunk in chunks]),
        dtype=np.float32,
    )
    if doc_embeddings.ndim != 2 or doc_embeddings.shape[0] != len(chunks):
        raise RuntimeError("Embedding model returned an unexpected document-vector shape.")

    strategy_results: dict[str, list[dict[str, Any]]] = {}
    for query_index, query in enumerate(queries):
        semantic_scores = np.asarray(doc_embeddings @ query_embeddings[query_index], dtype=np.float32)
        semantic_indices = np.argsort(semantic_scores)[::-1][:TOP_K]
        semantic_results = [
            {"score": float(semantic_scores[index]), "metadata": chunks[int(index)]}
            for index in semantic_indices
        ]

        keyword_scores = np.asarray(bm25.get_scores(tokenize(query)), dtype=np.float32)
        keyword_indices = np.argsort(keyword_scores)[::-1][:TOP_K]
        keyword_results = [
            {"score": float(keyword_scores[index]), "metadata": chunks[int(index)]}
            for index in keyword_indices
        ]
        strategy_results[query] = fuse_rankings(semantic_results, keyword_results)
    return strategy_results


def build_report() -> list[str]:
    header = [
        "LEGALMIND AI - CONSTITUTION CHUNKING COMPARISON",
        "=" * 86,
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Input PDF: {PDF_PATH}",
        "Scope: supplied test PDF only; temporary chunks, BM25, and embeddings held in memory.",
        "Current strategy: app.documents.chunker.create_chunks, 1,200 chars, 200 overlap, page-bounded.",
        "Experimental strategy: heading-aware article grouping across pages; target 1,200 source chars, clause/line-preferred splits, approx. 200-char contextual overlap.",
        "Page numbers: physical PDF page positions, one-based; multi-page chunks list every represented page.",
        "Tokenizer: exact HybridRetriever.tokenize regular expression.",
        "Embedding: app EmbeddingModel (all-MiniLM-L6-v2), normalize_embeddings=True; offline model loading required.",
        "Semantic score: dot product of normalized vectors, matching production IndexFlatIP behavior.",
        f"Hybrid fusion: {SEMANTIC_WEIGHT:.2f}/(60 + semantic rank) + {KEYWORD_WEIGHT:.2f}/(60 + BM25 rank); each branch top {TOP_K}, then production-style deduplication.",
        "No relevance labels or effectiveness metrics are assigned by this script.",
        "Production HybridRetriever, FAISS index, metadata, and persisted BM25 inputs are not loaded.",
        "",
    ]
    if not PDF_PATH.is_file():
        return header + [f"BLOCKED: test PDF not found: {PDF_PATH}", ""]

    try:
        import numpy as np
        from rank_bm25 import BM25Okapi
        from app.documents.chunker import create_chunks
        from app.documents.parser import extract_text_from_pdf
    except Exception as exc:
        return header + [
            "BLOCKED: required local project dependencies could not be imported.",
            f"{type(exc).__name__}: {' '.join(str(exc).split())[:500]}",
            "No PDF ranking or comparison was run.",
            "",
        ]

    try:
        pages = extract_text_from_pdf(str(PDF_PATH))
    except Exception as exc:
        return header + [
            "BLOCKED: PDF extraction failed.",
            f"{type(exc).__name__}: {' '.join(str(exc).split())[:500]}",
            "No ranking or comparison was run.",
            "",
        ]

    pdf_hash = hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()
    page_count = max((int(page["page_number"]) for page in pages), default=0)
    header.extend([
        f"PDF SHA-256: {pdf_hash}",
        f"Extracted text pages: {len(pages)}; highest physical page number: {page_count}",
    ])
    if not pages:
        return header + ["BLOCKED: no extractable text pages.", ""]

    source_filename = PDF_PATH.name
    try:
        article_records, page_intervals = parse_article_units(pages)
        current_chunks = create_chunks(
            pages,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
            case_metadata={
                "case_name": "Constitution of India",
                "document_type": "constitution",
                "jurisdiction": "India",
                "source_file": source_filename,
                "acts": [],
                "sections": [],
            },
        )
        current_chunks = enrich_page_chunks(current_chunks, pages, page_intervals)
        map_page_chunks_to_articles(current_chunks, article_records)
        article_chunks = make_article_aware_chunks(article_records, source_filename)
    except Exception as exc:
        return header + [
            "BLOCKED: chunk construction or article diagnostics failed.",
            f"{type(exc).__name__}: {' '.join(str(exc).split())[:500]}",
            "",
        ]

    detected_article_count = sum(article_id is not None for article_id in article_records)
    header.extend([
        f"Temporary chunks: current page-based={len(current_chunks)}; article-aware={len(article_chunks)}.",
        f"Article headings detected: {detected_article_count}; heading rule is anchored to numbered article-title lines.",
        "Article-aware continuation chunks receive an explicit article heading prefix; source text remains unchanged in the PDF.",
        "",
        "ARTICLE / CLAUSE STRUCTURE DIAGNOSTICS",
        "=" * 86,
    ])
    header.extend(chunking_diagnostics("Current page-based", current_chunks, article_records))
    header.extend(chunking_diagnostics("Experimental article-aware", article_chunks, article_records))
    header.extend(["", "FOCUS CHECKS: ARTICLE 19 AND ARTICLE 21", "=" * 86])
    header.extend(focus_article_lines("Current page-based", current_chunks, article_records))
    header.extend(focus_article_lines("Experimental article-aware", article_chunks, article_records))

    if not article_chunks:
        header.extend([
            "",
            "BLOCKED: the heading-aware strategy produced no chunks. Check the heading pattern and extracted PDF text before interpreting the comparison.",
            "",
        ])
        return header

    # Enforce offline behavior before loading the project's model implementation.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        from app.embeddings.embeddings import EmbeddingModel

        model = EmbeddingModel()
        queries = tuple(case["question"] for case in EVALUATION_CASES)
        query_embeddings = np.asarray(model.generate_embeddings(list(queries)), dtype=np.float32)
        if query_embeddings.ndim != 2 or query_embeddings.shape[0] != len(queries):
            raise RuntimeError("Embedding model returned an unexpected query-vector shape.")

        current_results = retrieve_for_strategy(
            current_chunks, query_embeddings, queries, np, BM25Okapi, model
        )
        article_results = retrieve_for_strategy(
            article_chunks, query_embeddings, queries, np, BM25Okapi, model
        )
    except Exception as exc:
        header.extend([
            "",
            "BLOCKED: local semantic model/ranking unavailable; no network fallback was attempted.",
            f"{type(exc).__name__}: {' '.join(str(exc).split())[:500]}",
            "Hybrid rankings are omitted rather than presenting a BM25-only result as hybrid.",
            "",
        ])
        return header

    header.extend([
        "",
        "TOP FIVE RESULTS BY QUERY",
        "=" * 86,
        "No relevance labels are inferred from expected pages. Result order is for manual review only.",
    ])
    for case in EVALUATION_CASES:
        query = case["question"]
        header.extend([
            "",
            f"{case['id']}: {query}",
            f"Expected passage/page guide: PDF page(s) {', '.join(map(str, case['expected_pages']))}; {case['expected_passage']}",
        ])
        for strategy_name, result_map in (
            ("CURRENT PAGE-BASED", current_results),
            ("EXPERIMENTAL ARTICLE-AWARE", article_results),
        ):
            header.append(f"  {strategy_name}")
            results = result_map.get(query, [])
            if not results:
                header.append("    No results.")
                continue
            for hybrid_rank, result in enumerate(results, start=1):
                metadata = result["metadata"]
                pages_text = ",".join(map(str, metadata.get("page_numbers", []))) or str(metadata.get("page_number", "unknown"))
                bm25_rank = result.get("keyword_rank")
                semantic_rank = result.get("semantic_rank")
                header.append(
                    f"    #{hybrid_rank} RRF={result['score']:.8f} | "
                    f"BM25 rank={bm25_rank if bm25_rank is not None else '-'} "
                    f"score={result.get('keyword_score', 0.0):.6f} | "
                    f"semantic rank={semantic_rank if semantic_rank is not None else '-'} "
                    f"score={result.get('semantic_score', 0.0):.6f} | "
                    f"pages=[{pages_text}] | source={metadata.get('source_file', 'unknown')}"
                )
                header.append(f"       Chunk={metadata.get('chunk_id', 'unknown')}; clauses={','.join(metadata.get('clause_ids', [])) or 'none'}")
                header.append(f"       Excerpt: {compact(str(metadata.get('text') or ''))}")

    header.extend([
        "",
        "HUMAN REVIEW",
        "=" * 86,
        "For each query and strategy, reviewers may label each returned passage: direct | partial | related | wrong.",
        "All results remain UNJUDGED. No Recall@5, MRR@5, direct-answer rate, or improvement claim is computed.",
        "",
        "SAFETY / SCOPE",
        "=" * 86,
        "Only data/test_constitutional_pdfs/constitution of india.pdf was used as source text.",
        "No production FAISS/BM25 index, metadata.json, application retriever instance, or other source PDF was loaded.",
        "No production files were written. No model/document downloads, API calls, LLM calls, or persistent index writes were made.",
    ])
    return header


def main() -> None:
    try:
        report_lines = build_report()
    except Exception as exc:
        report_lines = [
            "LEGALMIND AI - CONSTITUTION CHUNKING COMPARISON",
            "=" * 86,
            "BLOCKED: unexpected diagnostic error.",
            f"{type(exc).__name__}: {' '.join(str(exc).split())[:500]}",
            "No production files were accessed or modified.",
        ]
    report = "\n".join(report_lines).rstrip() + "\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"\nReport saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
