import json
import os

from dotenv import load_dotenv
from google import genai


load_dotenv()


METADATA_PATH = "data/metadata.json"

GEMINI_MODEL = "gemini-3.5-flash-lite"


# ============================================================
# CASE KEY
# ============================================================

def _case_key(case):
    """
    Create a unique key for a legal case.

    The same format must be used everywhere in LegalMind AI.
    """

    return "|||".join(
        [
            str(case.get("case_name") or ""),
            str(case.get("case_number") or ""),
            str(case.get("judgment_date") or ""),
            str(case.get("citation") or ""),
        ]
    )


# ============================================================
# LOAD CASES
# ============================================================

def _load_cases():
    """
    Load all unique legal cases from metadata.json.

    metadata.json contains individual chunks.
    This function groups chunks belonging to the same case.
    """

    if not os.path.exists(METADATA_PATH):
        raise FileNotFoundError(
            f"Metadata file not found: {METADATA_PATH}"
        )

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        metadata = json.load(file)

    cases = {}

    for chunk in metadata:

        case_name = chunk.get("case_name")

        if not case_name:
            continue

        key = (
            case_name,
            chunk.get("case_number"),
            chunk.get("judgment_date"),
            chunk.get("citation"),
        )

        if key not in cases:

            case_data = {
                "case_name": case_name,

                "court": chunk.get(
                    "court"
                ),

                "judgment_date": chunk.get(
                    "judgment_date"
                ),

                "case_number": chunk.get(
                    "case_number"
                ),

                "citation": chunk.get(
                    "citation"
                ),

                "document_type": chunk.get(
                    "document_type",
                    "judgment"
                ),

                "acts": chunk.get(
                    "acts",
                    []
                ),

                "sections": chunk.get(
                    "sections",
                    []
                ),

                "jurisdiction": chunk.get(
                    "jurisdiction"
                ),

                "source_file": chunk.get(
                    "source_file"
                ),

                "source_url": chunk.get(
                    "source_url"
                ),

                "case_key": _case_key(
                    {
                        "case_name": case_name,

                        "case_number": chunk.get(
                            "case_number"
                        ),

                        "judgment_date": chunk.get(
                            "judgment_date"
                        ),

                        "citation": chunk.get(
                            "citation"
                        ),
                    }
                ),

                "chunks": [],
            }

            cases[key] = case_data

        text = chunk.get(
            "text",
            ""
        )

        if text:

            cases[key]["chunks"].append(
                {
                    "page_number": chunk.get(
                        "page_number"
                    ),

                    "text": text,
                }
            )

    return list(cases.values())


# ============================================================
# FIND CASE
# ============================================================

def _find_case(case_key):
    """
    Find a case using its unique case key.
    """

    if not case_key:
        return None

    cases = _load_cases()

    for case in cases:

        if case.get("case_key") == case_key:
            return case

    return None


# ============================================================
# BUILD CASE CONTEXT
# ============================================================

def _build_context(case, max_characters=18000):
    """
    Build judgment context for Gemini.

    Page numbers are preserved so the generated comparison
    can be grounded in the original judgment.
    """

    chunks = case.get(
        "chunks",
        []
    )

    if not chunks:
        return ""

    passages = []

    for item in chunks:

        page_number = item.get(
            "page_number"
        )

        text = item.get(
            "text",
            ""
        )

        if not text:
            continue

        passages.append(
            f"[Page {page_number}]\n{text}"
        )

    full_text = "\n\n".join(
        passages
    )

    return full_text[:max_characters]


# ============================================================
# CLEAN GEMINI RESPONSE
# ============================================================

def _clean_json_response(raw_response):
    """
    Remove Markdown code fences if Gemini returns JSON
    inside ```json ... ``` blocks.
    """

    raw = (
        raw_response or ""
    ).strip()

    if raw.startswith("```json"):

        raw = raw[
            len("```json"):
        ]

    elif raw.startswith("```JSON"):

        raw = raw[
            len("```JSON"):
        ]

    elif raw.startswith("```"):

        raw = raw[
            len("```"):
        ]

    if raw.endswith("```"):

        raw = raw[
            :-len("```")
        ]

    return raw.strip()


# ============================================================
# COMPARE CASES
# ============================================================

def compare_cases(
    case_a_key,
    case_b_key
):
    """
    Compare two Indian judicial decisions.

    Parameters
    ----------
    case_a_key : str
        Unique key of Case A.

    case_b_key : str
        Unique key of Case B.

    Returns
    -------
    dict
        Case metadata and AI-generated comparison.
    """

    if not case_a_key:
        raise ValueError(
            "Case A key is required."
        )

    if not case_b_key:
        raise ValueError(
            "Case B key is required."
        )

    if case_a_key == case_b_key:

        raise ValueError(
            "Case A and Case B must be different."
        )

    print("\nLoading Case A...")

    case_a = _find_case(
        case_a_key
    )

    print("\nLoading Case B...")

    case_b = _find_case(
        case_b_key
    )

    if not case_a:

        raise ValueError(
            "Case A was not found in the legal knowledge base."
        )

    if not case_b:

        raise ValueError(
            "Case B was not found in the legal knowledge base."
        )

    print(
        "\nCase A:",
        case_a.get("case_name")
    )

    print(
        "Case B:",
        case_b.get("case_name")
    )

    context_a = _build_context(
        case_a
    )

    context_b = _build_context(
        case_b
    )

    if not context_a:

        raise ValueError(
            "No judgment text is available for Case A."
        )

    if not context_b:

        raise ValueError(
            "No judgment text is available for Case B."
        )

    # --------------------------------------------------------
    # Metadata without chunks
    # --------------------------------------------------------

    case_a_metadata = {
        key: value
        for key, value in case_a.items()
        if key != "chunks"
    }

    case_b_metadata = {
        key: value
        for key, value in case_b.items()
        if key != "chunks"
    }

    # --------------------------------------------------------
    # Gemini Prompt
    # --------------------------------------------------------

    prompt = f"""
You are LegalMind AI, an AI-powered legal research assistant
for Indian judicial decisions.

Your task is to compare TWO Indian court judgments.

IMPORTANT RULES:

1. Use ONLY the supplied case metadata and judgment passages.
2. Do NOT invent facts.
3. Do NOT invent arguments.
4. Do NOT invent legal sections.
5. Do NOT invent citations.
6. Do NOT invent court reasoning.
7. Do NOT invent the final decision.
8. If information is not present in the supplied material,
   explicitly say:
   "Not available in the supplied material."
9. Clearly distinguish Case A and Case B.
10. Do not treat similarity as proof that a judgment is binding
    precedent.
11. Do not provide a probability of winning a case.
12. Do not present the output as legal advice.
13. This is a legal research comparison.

============================================================
CASE A - METADATA
============================================================

{json.dumps(
    case_a_metadata,
    ensure_ascii=False,
    indent=2
)}

============================================================
CASE A - JUDGMENT PASSAGES
============================================================

{context_a}

============================================================
CASE B - METADATA
============================================================

{json.dumps(
    case_b_metadata,
    ensure_ascii=False,
    indent=2
)}

============================================================
CASE B - JUDGMENT PASSAGES
============================================================

{context_b}

============================================================
REQUIRED OUTPUT
============================================================

Return ONLY valid JSON.

Return exactly these keys:

case_information
facts
legal_issues
arguments
court_reasoning
decision
acts_sections
similarities
differences
important_observation

For comparison fields, clearly identify:

Case A:
...

Case B:
...

Do not use Markdown.

Do not include ```json.

If the supplied judgment material does not establish
something, say:

"Not available in the supplied material."
"""

    # --------------------------------------------------------
    # Gemini API Key
    # --------------------------------------------------------

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    # --------------------------------------------------------
    # Gemini Client
    # --------------------------------------------------------

    print(
        "\nSending judgment material to Gemini..."
    )

    client = genai.Client(
        api_key=api_key
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    raw = _clean_json_response(
        response.text
    )

    if not raw:

        raise RuntimeError(
            "Gemini returned an empty comparison response."
        )

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:

        comparison = json.loads(
            raw
        )

    except json.JSONDecodeError as error:

        print("\nGemini returned:")

        print(raw)

        raise RuntimeError(
            "Gemini returned invalid comparison JSON: "
            f"{error}"
        )

    # --------------------------------------------------------
    # Validate required fields
    # --------------------------------------------------------

    required_fields = [
        "case_information",
        "facts",
        "legal_issues",
        "arguments",
        "court_reasoning",
        "decision",
        "acts_sections",
        "similarities",
        "differences",
        "important_observation",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in comparison
    ]

    if missing_fields:

        raise RuntimeError(
            "Gemini comparison is missing required fields: "
            + ", ".join(missing_fields)
        )

    # --------------------------------------------------------
    # Final Result
    # --------------------------------------------------------

    return {
        "case_a": case_a_metadata,

        "case_b": case_b_metadata,

        "comparison": comparison,
    }

def compare_uploaded_cases(
    case_a_text,
    case_b_text,
    case_a_metadata=None,
    case_b_metadata=None,
):
    """
    Compare two user-uploaded legal documents.

    Unlike compare_cases(), this function does not require
    the documents to exist in metadata.json.
    """

    if not case_a_text or not case_a_text.strip():
        raise ValueError("Case A PDF contains no readable text.")

    if not case_b_text or not case_b_text.strip():
        raise ValueError("Case B PDF contains no readable text.")

    case_a_metadata = case_a_metadata or {}
    case_b_metadata = case_b_metadata or {}

    # Keep the Gemini context reasonably sized.
    max_characters = 18000

    context_a = case_a_text[:max_characters]
    context_b = case_b_text[:max_characters]

    prompt = f"""
You are LegalMind AI, an AI-powered legal research assistant
for Indian judicial decisions.

Your task is to compare TWO user-uploaded legal documents.

IMPORTANT RULES:

1. Use ONLY the supplied document text and metadata.
2. Do NOT invent facts.
3. Do NOT invent arguments.
4. Do NOT invent legal sections.
5. Do NOT invent citations.
6. Do NOT invent court reasoning.
7. Do NOT invent the final decision.
8. If information is not available, say:
   "Not available in the supplied material."
9. Clearly distinguish Case A and Case B.
10. Do not treat similarity as proof that a judgment is binding precedent.
11. Do not provide a probability of winning a case.
12. Do not present the output as legal advice.
13. This is a legal research comparison.

============================================================
CASE A - METADATA
============================================================

{json.dumps(
    case_a_metadata,
    ensure_ascii=False,
    indent=2
)}

============================================================
CASE A - DOCUMENT
============================================================

{context_a}

============================================================
CASE B - METADATA
============================================================

{json.dumps(
    case_b_metadata,
    ensure_ascii=False,
    indent=2
)}

============================================================
CASE B - DOCUMENT
============================================================

{context_b}

============================================================
REQUIRED OUTPUT
============================================================

Return ONLY valid JSON.

Return exactly these keys:

case_information
facts
legal_issues
arguments
court_reasoning
decision
acts_sections
similarities
differences
important_observation

For comparison fields, clearly identify:

Case A:
...

Case B:
...

Do not use Markdown.

Do not include ```json.

If the supplied material does not establish something, say:

"Not available in the supplied material."
"""

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    print("\nSending uploaded cases to Gemini...")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    raw = _clean_json_response(response.text)

    if not raw:
        raise RuntimeError(
            "Gemini returned an empty comparison response."
        )

    try:
        comparison = json.loads(raw)

    except json.JSONDecodeError as error:

        print("\nGemini returned invalid JSON:")
        print(raw)

        raise RuntimeError(
            "Gemini returned invalid comparison JSON: "
            f"{error}"
        )

    required_fields = [
        "case_information",
        "facts",
        "legal_issues",
        "arguments",
        "court_reasoning",
        "decision",
        "acts_sections",
        "similarities",
        "differences",
        "important_observation",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in comparison
    ]

    if missing_fields:
        raise RuntimeError(
            "Gemini comparison is missing required fields: "
            + ", ".join(missing_fields)
        )

    return {
        "case_a": case_a_metadata,
        "case_b": case_b_metadata,
        "comparison": comparison,
    }
# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print("\n========================================")
    print("        LEGALMIND AI")
    print("    CASE COMPARATOR TEST")
    print("========================================")

    try:

        cases = _load_cases()

        print(
            "\nAvailable cases:",
            len(cases)
        )

        if len(cases) < 2:

            print(
                "\nAt least two cases are required."
            )

        else:

            case_a = cases[0]
            case_b = cases[1]

            print(
                "\nCase A:",
                case_a.get("case_name")
            )

            print(
                "Case B:",
                case_b.get("case_name")
            )

            result = compare_cases(
                case_a.get("case_key"),
                case_b.get("case_key")
            )

            print(
                "\n========================================"
            )

            print(
                "COMPARISON RESULT"
            )

            print(
                "========================================"
            )

            print(
                json.dumps(
                    result,
                    indent=2,
                    ensure_ascii=False
                )
            )

    except Exception as error:

        print(
            "\n========================================"
        )

        print(
            "COMPARISON ERROR"
        )

        print(
            "========================================"
        )

        print(
            type(error).__name__
        )

        print(
            str(error)
        )