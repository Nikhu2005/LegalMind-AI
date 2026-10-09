import os

from dotenv import load_dotenv
from google import genai


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(
    api_key=API_KEY
)


# ============================================================
# ANALYZE CURRENT CASE
# ============================================================

def analyze_case(text):
    """
    Analyze an uploaded legal case using Gemini.

    The model extracts legal issues, Acts, sections,
    facts, arguments and important legal concepts.
    """

    if not text or not text.strip():
        return {
            "legal_issues": [],
            "acts": [],
            "sections": [],
            "facts": [],
            "arguments": [],
            "legal_concepts": []
        }

    # Limit extremely large documents for the first version.
    text = text[:30000]

    prompt = f"""
You are LegalMind AI, an AI-powered legal research assistant.

Analyze the following Indian legal document.

IMPORTANT RULES:

1. Use ONLY information contained in the supplied document.
2. Do NOT invent Acts, sections, facts, arguments or legal issues.
3. If something is not clearly available, return an empty list.
4. Do not provide legal advice.
5. Do not decide whether the case will succeed.
6. Extract information for legal research only.

Return ONLY valid JSON using exactly this structure:

{{
    "legal_issues": [],
    "acts": [],
    "sections": [],
    "facts": [],
    "arguments": [],
    "legal_concepts": []
}}

CURRENT LEGAL DOCUMENT:

{text}
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )

        result = response.text.strip()

        # Remove markdown JSON fences if Gemini adds them.
        if result.startswith("```json"):
            result = result[7:]

        if result.startswith("```"):
            result = result[3:]

        if result.endswith("```"):
            result = result[:-3]

        import json

        return json.loads(result.strip())

    except Exception as error:

        return {
            "error": str(error),
            "legal_issues": [],
            "acts": [],
            "sections": [],
            "facts": [],
            "arguments": [],
            "legal_concepts": []
        }