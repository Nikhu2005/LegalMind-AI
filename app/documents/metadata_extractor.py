import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)


def extract_legal_metadata(text, filename):
    """
    Extract legal metadata from the beginning of a judgment/order.
    """

    prompt = f"""
You are a legal document metadata extraction system.

Analyze the following Indian court judgment/order.

Document filename:
{filename}

Document text:
{text}

Extract the following information.

Return ONLY valid JSON.
Do not add markdown or explanations.

Required JSON format:

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

1. Do not invent information.
2. If information is not available, use null.
3. Acts should contain names of Acts/laws mentioned in the document.
4. Sections should contain important legal sections explicitly mentioned.
5. document_type should be either:
   - Judgment
   - Order
   - Unknown
6. Preserve the exact case name when available.
7. Preserve the exact case number when available.
8. Preserve the exact citation when available.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    result = response.text.strip()

    # Remove markdown JSON fences if Gemini adds them
    if result.startswith("```"):
        result = result.replace("```json", "")
        result = result.replace("```", "")
        result = result.strip()

    try:
        metadata = json.loads(result)
    except json.JSONDecodeError:
        print("Could not parse Gemini response as JSON.")
        print(result)

        metadata = {
            "case_name": None,
            "court": None,
            "judgment_date": None,
            "case_number": None,
            "citation": None,
            "acts": [],
            "sections": [],
            "document_type": None,
            "jurisdiction": "India"
        }

    metadata["source_url"] = None
    metadata["source_file"] = filename

    return metadata


if __name__ == "__main__":

    test_file = "data/judgments/Judgement_24-Sep-2026.pdf"

    print("Testing legal metadata extraction...")
    print("File:", test_file)

    import fitz

    document = fitz.open(test_file)

    # Read first 5 pages
    text = ""

    for page in document[:5]:
        text += page.get_text("text") + "\n"

    document.close()

    metadata = extract_legal_metadata(
        text,
        os.path.basename(test_file)
    )

    print("\n==============================")
    print("EXTRACTED LEGAL METADATA")
    print("==============================")

    print(json.dumps(
        metadata,
        indent=4,
        ensure_ascii=False
    ))