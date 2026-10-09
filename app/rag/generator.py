import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)


def generate_answer(question, retrieved_chunks):

    if not retrieved_chunks:
        return (
            "I could not find relevant information "
            "in the available legal documents."
        )

    context_parts = []

    for i, result in enumerate(
        retrieved_chunks,
        start=1
    ):

        metadata = result["metadata"]

        context_parts.append(
            f"""
SOURCE {i}

Case Name:
{metadata.get("case_name", "Not available")}

Court:
{metadata.get("court", "Not available")}

Judgment Date:
{metadata.get("judgment_date", "Not available")}

Case Number:
{metadata.get("case_number", "Not available")}

Citation:
{metadata.get("citation", "Not available")}

Document Type:
{metadata.get("document_type", "Not available")}

Acts:
{metadata.get("acts", [])}

Sections:
{metadata.get("sections", [])}

Page:
{metadata.get("page_number", "Not available")}

Source File:
{metadata.get("source_file", "Not available")}

Text:
{metadata.get("text", "")}
"""
        )

    context = "\n".join(context_parts)

    prompt = f"""
You are LegalMind AI, an AI-powered legal document
research assistant.

Your job is to answer questions ONLY using the
provided legal document sources.

STRICT GROUNDING RULES:

1. Use ONLY the supplied sources.

2. Do NOT invent:
   - facts
   - cases
   - citations
   - sections
   - Acts
   - dates
   - quotations
   - legal principles

3. Every important factual statement must be supported
   by one or more supplied sources.

4. Always identify the relevant case and page.

5. If the supplied sources do not contain enough
   information, say:

   "The available legal documents do not contain
   enough information to answer this question."

6. Do not use your general knowledge to fill missing
   information.

7. Do not claim that a judgment is binding precedent
   unless the supplied sources explicitly establish it.

8. Distinguish between:
   - what the court stated
   - what the document describes
   - your explanation of the retrieved text

9. Do not provide personalized legal advice.

10. Do not present the answer as a substitute for
    professional legal advice.

USER QUESTION:
{question}

LEGAL DOCUMENT SOURCES:
{context}

Return the answer in exactly this structure:

Answer:
[Concise grounded answer]

Sources:
1. [Case name] — Page [number]
2. [Case name] — Page [number]

Evidence:
[Brief explanation of which retrieved passages support
the answer.]

Confidence:
[High / Medium / Low]

If the sources are insufficient, use the required
insufficient-information statement instead of guessing.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    return response.text