import os
import uuid

from app.documents.parser import extract_text_from_pdf


CURRENT_CASE_DIR = "data/current_cases"


def save_current_case(file_bytes, original_filename):
    """
    Save an uploaded current legal case PDF.
    """

    os.makedirs(CURRENT_CASE_DIR, exist_ok=True)

    file_id = str(uuid.uuid4())

    safe_filename = os.path.basename(original_filename)

    filename = f"{file_id}_{safe_filename}"

    file_path = os.path.join(
        CURRENT_CASE_DIR,
        filename
    )

    with open(file_path, "wb") as file:
        file.write(file_bytes)

    return {
        "file_id": file_id,
        "filename": safe_filename,
        "file_path": file_path
    }


def analyze_current_case(file_path):
    """
    Extract text from the uploaded current case.
    """

    pages = extract_text_from_pdf(file_path)

    if not pages:
        return {
            "total_pages": 0,
            "text": "",
            "pages": []
        }

    full_text = "\n\n".join(
        page["text"]
        for page in pages
    )

    return {
        "total_pages": len(pages),
        "text": full_text,
        "pages": pages
    }