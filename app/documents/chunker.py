def create_chunks(
    pages,
    chunk_size=1200,
    overlap=200,
    case_metadata=None
):
    """
    Create text chunks while preserving legal case metadata.
    """

    chunks = []

    if case_metadata is None:
        case_metadata = {}

    for page in pages:

        text = page["text"]
        page_number = page["page_number"]

        start = 0
        chunk_number = 1

        while start < len(text):

            end = start + chunk_size

            chunk_text = text[start:end].strip()

            if chunk_text:

                chunk = {
                    "chunk_id": (
                        f"{case_metadata.get('case_name', 'document')}_"
                        f"page_{page_number}_"
                        f"chunk_{chunk_number}"
                    ),

                    "page_number": page_number,

                    "text": chunk_text,

                    # Legal metadata
                    "case_name": case_metadata.get("case_name"),
                    "court": case_metadata.get("court"),
                    "judgment_date": case_metadata.get(
                        "judgment_date"
                    ),
                    "case_number": case_metadata.get(
                        "case_number"
                    ),
                    "citation": case_metadata.get(
                        "citation"
                    ),
                    "acts": case_metadata.get(
                        "acts", []
                    ),
                    "sections": case_metadata.get(
                        "sections", []
                    ),
                    "document_type": case_metadata.get(
                        "document_type",
                        "judgment"
                    ),
                    "source_url": case_metadata.get(
                        "source_url"
                    ),

                    "jurisdiction": case_metadata.get(
                        "jurisdiction",
                        "India"
                    ),

                    "source_file": case_metadata.get(
                        "source_file"
                    )
                }

                chunks.append(chunk)

            start += chunk_size - overlap
            chunk_number += 1

    return chunks