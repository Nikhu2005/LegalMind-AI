import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.documents.chunker import create_chunks
from app.documents.current_case import (
    analyze_current_case,
    save_current_case,
)
from app.documents.parser import extract_text_from_pdf
from app.rag.case_analyzer import analyze_case
from app.rag.case_comparison_engine import CaseComparisonEngine
from app.rag.case_comparator import compare_uploaded_cases
from app.rag.generator import generate_answer
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import LegalReranker
from app.rag.similar_judgments import find_similar_judgments
from app.ingestion.sci_web_search import search_recent_sci_judgments



# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="LegalMind AI",
    description="AI-Powered Legal Document Intelligence & Case Law Research System",
    version="1.0.0",
)

# ============================================================
# LOAD RAG MODELS ONCE AT STARTUP
# ============================================================

print("Initializing LegalMind AI models...")

retriever = HybridRetriever()
reranker = LegalReranker()

print("LegalMind AI models ready.")

METADATA_PATH = "data/metadata.json"
DOCUMENT_DIR = Path("data/ingestion/downloaded")


# ============================================================
# REQUEST MODELS
# ============================================================

class SearchRequest(BaseModel):
    question: str
    top_k: int = 5
    court: str | None = None
    document_type: str | None = None


class WebSearchRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)


class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    court: str | None = None
    document_type: str | None = None


class CompareCasesRequest(BaseModel):
    case1_key: str
    case2_key: str


class TranslateRequest(BaseModel):
    text: str
    target_language: str


# ============================================================
# HELPERS
# ============================================================

def make_case_key(case_name, case_number, judgment_date, citation) -> str:
    return "|||".join(
        [
            str(case_name or ""),
            str(case_number or ""),
            str(judgment_date or ""),
            str(citation or ""),
        ]
    )


def validate_pdf_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was provided.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are currently supported.",
        )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "project": "LegalMind AI",
        "status": "running",
        "message": "AI-Powered Legal Research System",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "LegalMind AI API",
    }


# ============================================================
# GET ALL CASES
# ============================================================

@app.get("/cases")
def get_cases():

    if not os.path.exists(METADATA_PATH):
        raise HTTPException(
            status_code=404,
            detail="Legal knowledge base metadata not found.",
        )

    try:
        with open(METADATA_PATH, "r", encoding="utf-8") as file:
            metadata = json.load(file)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load legal metadata: {error}",
        )

    cases = {}

    for chunk in metadata:
        case_name = chunk.get("case_name")

        if not case_name:
            continue

        case_identifier = (
            case_name,
            chunk.get("case_number"),
            chunk.get("judgment_date"),
            chunk.get("citation"),
        )

        if case_identifier not in cases:
            cases[case_identifier] = {
                "case_name": case_name,
                "court": chunk.get("court"),
                "judgment_date": chunk.get("judgment_date"),
                "case_number": chunk.get("case_number"),
                "citation": chunk.get("citation"),
                "document_type": chunk.get("document_type"),
                "acts": chunk.get("acts", []),
                "sections": chunk.get("sections", []),
                "jurisdiction": chunk.get("jurisdiction"),
                "source_file": chunk.get("source_file"),
                "source_url": chunk.get("source_url"),
                "case_key": make_case_key(*case_identifier),
            }

    return {
        "total_cases": len(cases),
        "cases": list(cases.values()),
    }


@app.get("/analytics/overview")
def get_analytics_overview():
    """Return analytics derived from the indexed legal metadata."""
    from collections import Counter
    from pathlib import Path

    metadata_path = Path(METADATA_PATH)

    if not metadata_path.exists():
        return {
            "status": "empty",
            "total_cases": 0,
            "indexed_passages": 0,
            "court_distribution": [],
            "document_type_distribution": [],
            "message": "Legal knowledge-base metadata is not available.",
        }

    try:
        with metadata_path.open("r", encoding="utf-8") as file:
            metadata = json.load(file)

        if not isinstance(metadata, list):
            raise ValueError("Expected metadata.json to contain a list.")

        unique_cases = {}

        for item in metadata:
            if not isinstance(item, dict):
                continue

            case_name = item.get("case_name")
            if not case_name:
                continue

            case_key = (
                str(case_name).strip(),
                str(item.get("case_number") or "").strip(),
                str(item.get("judgment_date") or "").strip(),
                str(item.get("citation") or "").strip(),
            )

            if case_key not in unique_cases:
                unique_cases[case_key] = item

        court_counts = Counter()
        document_type_counts = Counter()

        for item in unique_cases.values():
            court = str(item.get("court") or "").strip()
            document_type = str(item.get("document_type") or "").strip()

            if court:
                court_counts[court] += 1

            if document_type:
                document_type_counts[document_type] += 1

        return {
            "status": "success",
            "total_cases": len(unique_cases),
            "indexed_passages": len(metadata),
            "court_distribution": [
                {"label": label, "count": count}
                for label, count in court_counts.most_common()
            ],
            "document_type_distribution": [
                {"label": label, "count": count}
                for label, count in document_type_counts.most_common()
            ],
            "message": None,
        }

    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not calculate analytics: {error}",
        )

# ============================================================
# COMPARE CASES
# ============================================================

@app.post("/compare-cases")
def compare_cases_endpoint(request: CompareCasesRequest):

    case1_key = request.case1_key.strip()
    case2_key = request.case2_key.strip()

    if not case1_key:
        raise HTTPException(status_code=400, detail="Case 1 key cannot be empty.")

    if not case2_key:
        raise HTTPException(status_code=400, detail="Case 2 key cannot be empty.")

    if case1_key == case2_key:
        raise HTTPException(
            status_code=400,
            detail="Please select two different cases.",
        )

    try:
        print("\n========================================")
        print("LEGALMIND AI - CASE COMPARISON API")
        print("========================================")

        engine = CaseComparisonEngine()
        result = engine.compare(case1_key, case2_key)

        return {
            "status": "success",
            "message": "Case comparison completed successfully.",
            "result": result,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        print("\nCase comparison error:", str(error))
        raise HTTPException(
            status_code=500,
            detail=f"Case comparison failed: {error}",
        )
# ============================================================
# COMPARE USER-UPLOADED CASES
# ============================================================

@app.post("/compare-uploaded-cases")
async def compare_uploaded_cases_endpoint(
    case_a: UploadFile = File(...),
    case_b: UploadFile = File(...),
):
    """
    Compare two legal PDFs uploaded directly by the user.

    This does NOT add the uploaded cases to the permanent
    legal knowledge base.
    """

    validate_pdf_upload(case_a)
    validate_pdf_upload(case_b)

    try:
        print("\n========================================")
        print("LEGALMIND AI - UPLOADED CASE COMPARISON")
        print("========================================")

        # ----------------------------------------------------
        # CASE A
        # ----------------------------------------------------

        case_a_bytes = await case_a.read()

        if not case_a_bytes:
            raise HTTPException(
                status_code=400,
                detail="Case A PDF is empty.",
            )

        # ----------------------------------------------------
        # CASE B
        # ----------------------------------------------------

        case_b_bytes = await case_b.read()

        if not case_b_bytes:
            raise HTTPException(
                status_code=400,
                detail="Case B PDF is empty.",
            )

        # ----------------------------------------------------
        # SAVE TEMPORARY/PERSISTED FILES
        # ----------------------------------------------------

        saved_case_a = save_current_case(
            case_a_bytes,
            case_a.filename,
        )

        saved_case_b = save_current_case(
            case_b_bytes,
            case_b.filename,
        )

        # ----------------------------------------------------
        # EXTRACT CASE A TEXT
        # ----------------------------------------------------

        analysis_a = analyze_current_case(
            saved_case_a["file_path"]
        )

        if analysis_a["total_pages"] == 0:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from Case A PDF.",
            )

        # ----------------------------------------------------
        # EXTRACT CASE B TEXT
        # ----------------------------------------------------

        analysis_b = analyze_current_case(
            saved_case_b["file_path"]
        )

        if analysis_b["total_pages"] == 0:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from Case B PDF.",
            )

        # ----------------------------------------------------
        # BASIC METADATA
        # ----------------------------------------------------

        case_a_metadata = {
            "filename": case_a.filename,
            "total_pages": analysis_a["total_pages"],
        }

        case_b_metadata = {
            "filename": case_b.filename,
            "total_pages": analysis_b["total_pages"],
        }

        # ----------------------------------------------------
        # AI COMPARISON
        # ----------------------------------------------------

        result = compare_uploaded_cases(
            analysis_a["text"],
            analysis_b["text"],
            case_a_metadata,
            case_b_metadata,
        )

        return {
            "status": "success",
            "message": "Uploaded cases compared successfully.",
            "result": result,
        }

    except HTTPException:
        raise

    except Exception as error:

        print(
            "\nUploaded case comparison error:",
            str(error),
        )

        raise HTTPException(
            status_code=500,
            detail=f"Uploaded case comparison failed: {error}",
        )

# ============================================================
# LEGAL SEARCH
# ============================================================

@app.post("/web-search")
def search_web_cases(request: WebSearchRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=400,
            detail="Search question cannot be empty.",
        )
    if len(question) > 500:
        raise HTTPException(
            status_code=400,
            detail="Search question must be 500 characters or fewer.",
        )

    try:
        search_result = search_recent_sci_judgments(
            question,
            max_results=request.top_k,
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Official Supreme Court web search failed: {error}",
        )

    return {
        "question": question,
        "mode": "official_web",
        "source_scope": "Supreme Court of India judgments currently linked from the official homepage",
        "coverage_note": (
            "This performs a bounded live scan of up to 10 homepage-linked judgment PDFs. "
            "It is not a search of the full historical court database. CAPTCHA-protected search forms are not automated."
        ),
        "source_pages_scanned": search_result["source_pages_scanned"],
        "pdfs_examined": search_result["pdfs_examined"],
        "warnings": search_result["warnings"],
        "total_results": len(search_result["results"]),
        "results": search_result["results"],
    }

@app.post("/search")
def search_cases(request: SearchRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Search question cannot be empty.",
        )

    try:
        # ----------------------------------------------------
        # STEP 1: RETRIEVE MORE PASSAGES
        # ----------------------------------------------------
        # Retrieve extra passages because several passages may
        # belong to the same judgment.
        #
        # Example:
        # top_k = 5
        # retrieve 15 passages
        # then keep the best 5 UNIQUE judgments.

        search_limit = max(request.top_k * 3, 15)

        results = retriever.search(
            question,
            top_k=search_limit,
            court=request.court,
            document_type=request.document_type,
        )

        # ----------------------------------------------------
        # STEP 2: REMOVE DUPLICATE JUDGMENTS
        # ----------------------------------------------------

        unique_results = {}
        
        for result in results:

            metadata = result.get("metadata", {})

            # Prefer source_file because all chunks/pages from
            # the same PDF normally share the same source file.
            source_file = metadata.get("source_file")

            # Fallback identifiers in case source_file is missing.
            case_number = metadata.get("case_number")
            case_name = metadata.get("case_name")

            if source_file:
                unique_key = f"file:{source_file}"

            elif case_number:
                unique_key = f"case:{case_number}"

            elif case_name:
                unique_key = f"name:{case_name}"

            else:
                # Last-resort unique key
                unique_key = f"result:{len(unique_results)}"

            # ------------------------------------------------
            # Keep only the BEST matching passage for a judgment
            # ------------------------------------------------

            if unique_key not in unique_results:
                unique_results[unique_key] = result

            else:
                existing_score = unique_results[unique_key].get(
                    "score", 0
                )

                current_score = result.get("score", 0)

                if current_score > existing_score:
                    unique_results[unique_key] = result

        # ----------------------------------------------------
        # STEP 3: SORT UNIQUE JUDGMENTS BY RELEVANCE
        # ----------------------------------------------------

        unique_results = list(unique_results.values())

        unique_results.sort(
            key=lambda result: result.get("score", 0),
            reverse=True,
        )

        # Return only requested number of UNIQUE judgments
        unique_results = unique_results[:request.top_k]

        # ----------------------------------------------------
        # STEP 4: FORMAT RESULTS FOR FRONTEND
        # ----------------------------------------------------

        formatted_results = []

        for result in unique_results:

            metadata = result.get("metadata", {})

            formatted_results.append(
                {
                    "score": result.get("score"),
                    "case_name": metadata.get("case_name"),
                    "court": metadata.get("court"),
                    "judgment_date": metadata.get("judgment_date"),
                    "case_number": metadata.get("case_number"),
                    "citation": metadata.get("citation"),
                    "document_type": metadata.get("document_type"),
                    "acts": metadata.get("acts", []),
                    "sections": metadata.get("sections", []),
                    "page_number": metadata.get("page_number"),
                    "jurisdiction": metadata.get("jurisdiction"),
                    "source_file": metadata.get("source_file"),
                    "text": metadata.get("text", ""),
                }
            )

        # ----------------------------------------------------
        # STEP 5: RETURN UNIQUE SEARCH RESULTS
        # ----------------------------------------------------

        return {
            "question": question,
            "total_results": len(formatted_results),
            "results": formatted_results,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Legal search failed: {error}",
        )


# ============================================================
# ASK LEGAL QUESTION
# ============================================================

@app.post("/ask")
def ask_legal_question(request: AskRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:
        # ----------------------------------------------------
        # STEP 1: RETRIEVE CANDIDATE PASSAGES
        # ----------------------------------------------------

        retrieval_start = time.time()

        candidates = retriever.search(
            question,
            top_k=max(10, request.top_k),
            court=request.court,
            document_type=request.document_type,
        )

        retrieval_time = time.time() - retrieval_start

        print(f"[ASK] Retrieval time: {retrieval_time:.2f}s")
        print(f"[ASK] Candidates: {len(candidates)}")

        if not candidates:
            return {
                "question": question,
                "answer": (
                    "The available legal documents do not contain "
                    "enough information to answer this question."
                ),
                "sources": [],
            }

        # ----------------------------------------------------
        # STEP 2: RERANK
        # ----------------------------------------------------

        rerank_start = time.time()

        results = reranker.rerank(
            question,
            candidates,
            top_k=request.top_k,
        )

        rerank_time = time.time() - rerank_start

        print(f"[ASK] Reranking time: {rerank_time:.2f}s")
        print(f"[ASK] Results: {len(results)}")

        # ----------------------------------------------------
        # STEP 3: GENERATE GROUNDED ANSWER
        # ----------------------------------------------------

        generation_start = time.time()

        answer = generate_answer(question, results)

        generation_time = time.time() - generation_start

        print(f"[ASK] Generation time: {generation_time:.2f}s")

        total_time = retrieval_time + rerank_time + generation_time

        print(f"[ASK] TOTAL TIME: {total_time:.2f}s")
        print("========================================")

        # ----------------------------------------------------
        # STEP 4: PREPARE SOURCES
        # ----------------------------------------------------

        sources = []

        for result in results:
            metadata = result.get("metadata", {})

            sources.append(
                {
                    "case_name": metadata.get("case_name"),
                    "court": metadata.get("court"),
                    "judgment_date": metadata.get("judgment_date"),
                    "case_number": metadata.get("case_number"),
                    "citation": metadata.get("citation"),
                    "document_type": metadata.get("document_type"),
                    "page_number": metadata.get("page_number"),
                    "source_file": metadata.get("source_file"),
                    "reranker_score": result.get("reranker_score"),
                }
            )

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Legal AI processing failed: {error}",
        )


# ============================================================
# UPLOAD CURRENT CASE + ANALYZE
# ============================================================

@app.post("/upload-current-case")
async def upload_current_case(file: UploadFile = File(...)):

    validate_pdf_upload(file)

    try:
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        saved_case = save_current_case(file_bytes, file.filename)

        analysis = analyze_current_case(saved_case["file_path"])

        if analysis["total_pages"] == 0:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from the PDF.",
            )

        legal_analysis = analyze_case(analysis["text"])

        return {
            "status": "success",
            "message": "Current case analyzed successfully.",
            "file_id": saved_case["file_id"],
            "filename": saved_case["filename"],
            "total_pages": analysis["total_pages"],
            "analysis": legal_analysis,
            "text_preview": analysis["text"][:1000],
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Current case processing failed: {error}",
        )


# ============================================================
# FIND SIMILAR JUDGMENTS
# ============================================================

@app.post("/find-similar-judgments")
async def find_similar_cases(file: UploadFile = File(...)):

    validate_pdf_upload(file)

    try:
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        saved_case = save_current_case(file_bytes, file.filename)

        analysis = analyze_current_case(saved_case["file_path"])

        if analysis["total_pages"] == 0:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from the PDF.",
            )

        legal_analysis = analyze_case(analysis["text"])

        if legal_analysis.get("error"):
            raise HTTPException(status_code=500, detail=legal_analysis["error"])

        similar_cases = find_similar_judgments(legal_analysis, top_k=5)

        return {
            "status": "success",
            "message": "Similar judgments found successfully.",
            "current_case": {
                "file_id": saved_case["file_id"],
                "filename": saved_case["filename"],
                "total_pages": analysis["total_pages"],
            },
            "case_analysis": legal_analysis,
            "total_similar_cases": len(similar_cases),
            "similar_judgments": similar_cases,
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Similar judgment search failed: {error}",
        )


# ============================================================
# UPLOAD CASE FOR COMPARISON
# ============================================================

@app.post("/upload-case-for-comparison")
async def upload_case_for_comparison(file: UploadFile = File(...)):
    """
    Upload a user's own judgment PDF and add it to the
    comparison knowledge base.
    """

    validate_pdf_upload(file)

    file_path = None

    try:
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # STEP 1: SAVE UPLOADED JUDGMENT
        DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)

        original_name = Path(file.filename).name

        safe_stem = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            Path(original_name).stem,
        ).strip("_")

        if not safe_stem:
            safe_stem = "uploaded_case"

        unique_name = (
            f"user_case_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}_{safe_stem}.pdf"
        )

        file_path = DOCUMENT_DIR / unique_name
        file_path.write_bytes(file_bytes)

        # STEP 2: EXTRACT TEXT WITH PAGE NUMBERS
        pages = extract_text_from_pdf(str(file_path))

        if not pages:
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from the PDF.",
            )

        full_text = "\n\n".join(page["text"] for page in pages)

        # STEP 3: EXTRACT LEGAL METADATA
        legal_analysis = analyze_case(full_text)

        if not isinstance(legal_analysis, dict):
            legal_analysis = {}

        case_name = (
            legal_analysis.get("case_name")
            or legal_analysis.get("case_title")
            or legal_analysis.get("title")
            or safe_stem.replace("_", " ")
        )

        court = legal_analysis.get("court") or "User Uploaded Case"

        judgment_date = (
            legal_analysis.get("judgment_date")
            or legal_analysis.get("date")
        )

        case_number = (
            legal_analysis.get("case_number")
            or legal_analysis.get("case_no")
        )

        citation = legal_analysis.get("citation")

        acts = (
            legal_analysis.get("acts")
            or legal_analysis.get("acts_involved")
            or []
        )

        sections = (
            legal_analysis.get("sections")
            or legal_analysis.get("legal_sections")
            or []
        )

        if isinstance(acts, str):
            acts = [acts]

        if isinstance(sections, str):
            sections = [sections]

        # STEP 4: CREATE COMPARISON CHUNKS
        case_metadata = {
            "case_name": case_name,
            "court": court,
            "judgment_date": judgment_date,
            "case_number": case_number,
            "citation": citation,
            "acts": acts,
            "sections": sections,
            "document_type": "user_uploaded_judgment",
            "source_url": None,
            "jurisdiction": legal_analysis.get("jurisdiction") or "India",
            "source_file": unique_name,
        }

        chunks = create_chunks(
            pages,
            chunk_size=1200,
            overlap=200,
            case_metadata=case_metadata,
        )

        if not chunks:
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="The PDF did not produce usable judgment passages.",
            )

        # STEP 5: ADD CASE TO METADATA
        metadata_path = Path(METADATA_PATH)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        if metadata_path.exists():
            with metadata_path.open("r", encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)
        else:
            metadata = []

        metadata.extend(chunks)

        with metadata_path.open("w", encoding="utf-8") as metadata_file:
            json.dump(metadata, metadata_file, ensure_ascii=False, indent=2)

        case_key = make_case_key(case_name, case_number, judgment_date, citation)

        return {
            "status": "success",
            "message": "Your case was uploaded and added for comparison.",
            "case": {
                "case_name": case_name,
                "court": court,
                "judgment_date": judgment_date,
                "case_number": case_number,
                "citation": citation,
                "document_type": "user_uploaded_judgment",
                "acts": acts,
                "sections": sections,
                "jurisdiction": case_metadata["jurisdiction"],
                "source_file": unique_name,
                "case_key": case_key,
            },
            "total_pages": len(pages),
            "total_chunks": len(chunks),
        }

    except HTTPException:
        raise

    except Exception as error:
        print("\nUser case comparison upload error:", str(error))

        if file_path is not None:
            file_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail=f"Could not add case for comparison: {error}",
        )


# ============================================================
# OPEN JUDGMENT PDF
# ============================================================

@app.get("/documents/{filename}")
async def open_document(filename: str):

    safe_filename = Path(filename).name
    file_path = DOCUMENT_DIR / safe_filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Judgment document not found.",
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=safe_filename,
        content_disposition_type="inline",
    )


# ============================================================
# TRANSLATE AI ANSWER
# ============================================================

LANGUAGE_CODES = {
    "English": "en",
    "Hindi": "hi",
    "Marathi": "mr",
    "Gujarati": "gu",
    "Bengali": "bn",
    "Tamil": "ta",
    "Telugu": "te",
    "Kannada": "kn",
    "Punjabi": "pa",
}


def split_text(text: str, limit: int = 4500) -> list[str]:
    """Split text into pieces under `limit` characters, on paragraph/line breaks."""
    parts, current = [], ""

    for paragraph in text.split("\n"):
        # Hard-split any single line that is itself too long
        while len(paragraph) > limit:
            if current:
                parts.append(current)
                current = ""
            parts.append(paragraph[:limit])
            paragraph = paragraph[limit:]

        if len(current) + len(paragraph) + 1 > limit:
            parts.append(current)
            current = paragraph
        else:
            current = f"{current}\n{paragraph}" if current else paragraph

    if current:
        parts.append(current)

    return parts


@app.post("/translate")
def translate_answer(request: TranslateRequest):

    text = request.text.strip()
    target_language = request.target_language.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Text to translate cannot be empty.",
        )

    if not target_language:
        raise HTTPException(
            status_code=400,
            detail="Target language is required.",
        )

    if target_language not in LANGUAGE_CODES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported target language.",
        )

    if target_language == "English":
        return {
            "translated_text": text,
            "target_language": "English",
        }

    try:
        # pip install deep-translator
        from deep_translator import GoogleTranslator
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Translation library not installed. Run: pip install deep-translator",
        )

    try:
        translator = GoogleTranslator(
            source="auto",
            target=LANGUAGE_CODES[target_language],
        )

        translated_parts = [translator.translate(part) for part in split_text(text)]

        return {
            "translated_text": "\n".join(translated_parts),
            "target_language": target_language,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {error}",
        )
