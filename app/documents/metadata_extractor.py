
import os
import re
import json
from datetime import datetime

from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY) if API_KEY else None

# Stop repeatedly calling Gemini after an API failure in this process.
_gemini_available = True


def empty_metadata():
    return {
        "case_name": None,
        "court": None,
        "judgment_date": None,
        "case_number": None,
        "citation": None,
        "acts": [],
        "sections": [],
        "document_type": None,
        "jurisdiction": "India",
    }


def extract_metadata_locally(text, filename):
    """Extract basic legal metadata without an API call."""
    metadata = empty_metadata()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    searchable_text = "\n".join(lines)

    # Court name
    court_patterns = [
        r"Supreme Court of India",
        r"High Court of [A-Za-z\s]+",
        r"District Court(?: of [A-Za-z\s]+)?",
    ]
    for pattern in court_patterns:
        match = re.search(pattern, searchable_text, re.IGNORECASE)
        if match:
            metadata["court"] = match.group(0).strip()
            break

    # Case number
    case_number_patterns = [
        r"(?:Case|Civil Appeal|Criminal Appeal|Writ Petition|"
        r"Special Leave Petition)\s*(?:No\.?|Number)\s*[:\-]?\s*"
        r"[\w./()\-]+(?:\s+of\s+\d{4})?",
        r"(?:Diary No\.?)\s*[\w./\-]+",
    ]
    for pattern in case_number_patterns:
        match = re.search(pattern, searchable_text, re.IGNORECASE)
        if match:
            metadata["case_number"] = match.group(0).strip()
            break

    # Judgment date: retain the date text found in the document.
    date_patterns = [
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b",
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+"
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December),?\s+\d{4}\b",
        r"\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, searchable_text, re.IGNORECASE)
        if match:
            metadata["judgment_date"] = match.group(0).strip()
            break

    # Document type
    first_text = searchable_text[:5000].lower()
    if re.search(r"\b(judgment|judgement)\b", first_text):
        metadata["document_type"] = "Judgment"
    elif re.search(r"\border\b", first_text):
        metadata["document_type"] = "Order"

    # Acts and sections explicitly mentioned.
    act_matches = re.findall(
        r"\b[A-Z][A-Za-z ,&()'-]{2,80}\bAct,?\s+\d{4}\b",
        searchable_text,
    )
    metadata["acts"] = list(dict.fromkeys(
        item.strip() for item in act_matches
    ))

    section_matches = re.findall(
        r"\b(?:Section|Sections|Sec\.?)\s+\d+[A-Za-z]?"
        r"(?:\s*\(\d+\))?(?:\s*(?:and|,)\s*\d+[A-Za-z]?)?",
        searchable_text,
        re.IGNORECASE,
    )
    metadata["sections"] = list(dict.fromkeys(
        item.strip() for item in section_matches
    ))

    # Conservative case-name fallback: use an early plausible party line.
    for line in lines[:35]:
        if (
            len(line) <= 180
            and re.search(r"\b(v\.?|vs\.?|versus)\b", line, re.IGNORECASE)
            and not re.search(
                r"\b(appeal|petition|section|court|judgment)\b",
                line,
                re.IGNORECASE,
            )
        ):
            metadata["case_name"] = line
            break

    # Use the filename only as a last-resort case-name hint.
    if not metadata["case_name"]:
        name = os.path.splitext(os.path.basename(filename))[0]
        name = re.sub(r"[_-]+", " ", name).strip()
        if name and not re.fullmatch(
            r"(judg?e?ment|order|document)\s*[\d\s]*",
            name,
            re.IGNORECASE,
        ):
            metadata["case_name"] = name

    return metadata


def extract_legal_metadata(text, filename):
    """
    Extract legal metadata with Gemini and fall back to local extraction.
    """
    global _gemini_available

    metadata = None

    if client is not None and _gemini_available and text.strip():
        prompt = f"""
You are a legal document metadata extraction system.

Analyze the following Indian court judgment/order.

Document filename:
{filename}

Document text:
{text[:30000]}

Return ONLY valid JSON with this schema:
{{
    "case_name": null,
    "court": null,
    "judgment_date": null,
    "case_number": null,
    "citation": null,
    "acts": [],
    "sections": [],
    "document_type": null,
    "jurisdiction": "India"
}}

Rules:
- Do not invent information.
- Use null when information is unavailable.
- Acts and sections must be explicitly mentioned.
- document_type must be Judgment, Order, or Unknown.
- Preserve exact case names, numbers, and citations when available.
"""

        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
            )

            result = (response.text or "").strip()
            result = re.sub(
                r"^```(?:json)?\s*|\s*```$",
                "",
                result,
                flags=re.IGNORECASE,
            ).strip()

            parsed = json.loads(result)
            if isinstance(parsed, dict):
                metadata = empty_metadata()
                metadata.update(parsed)

        except Exception as exc:
            # Avoid printing the request, credentials, or document text.
            print(
                "Gemini metadata extraction failed; "
                f"using local fallback ({type(exc).__name__})."
            )
            _gemini_available = False

    if metadata is None:
        metadata = extract_metadata_locally(text, filename)

    metadata.setdefault("source_url", None)
    metadata["source_file"] = filename

    return metadata


if __name__ == "__main__":
    import fitz

    test_file = "data/judgments/Judgement_24-Sep-2026.pdf"

    if not os.path.isfile(test_file):
        raise FileNotFoundError(
            f"Test PDF not found: {test_file}"
        )

    print("Testing legal metadata extraction...")
    print("File:", test_file)

    with fitz.open(test_file) as document:
        text = "\n".join(
            page.get_text("text") for page in document[:5]
        )

    metadata = extract_legal_metadata(
        text,
        os.path.basename(test_file),
    )

    print("\nEXTRACTED LEGAL METADATA")
    print(json.dumps(metadata, indent=4, ensure_ascii=False))
