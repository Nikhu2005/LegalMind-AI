import json
import os

from app.documents.ingestion_tracker import IngestionTracker


METADATA_PATH = "data/metadata.json"


def sync_tracker():

    print("\n========================================")
    print("       LEGALMIND AI")
    print("   TRACKER SYNCHRONIZATION")
    print("========================================")

    # --------------------------------------
    # Check metadata database
    # --------------------------------------

    if not os.path.exists(METADATA_PATH):

        print(
            "\nERROR: metadata.json not found."
        )

        return

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        chunks = json.load(file)

    print(
        "\nKnowledge-base chunks:",
        len(chunks)
    )

    # --------------------------------------
    # Group chunks by document
    # --------------------------------------

    documents = {}

    for chunk in chunks:

        case_name = chunk.get(
            "case_name"
        )

        case_number = chunk.get(
            "case_number"
        )

        judgment_date = chunk.get(
            "judgment_date"
        )

        citation = chunk.get(
            "citation"
        )

        source_file = chunk.get(
            "source_file"
        )

        # Create a document identity
        identity = (
            str(case_name),
            str(case_number),
            str(judgment_date),
            str(citation)
        )

        if identity not in documents:

            documents[identity] = {
                "case_name": case_name,
                "case_number": case_number,
                "judgment_date": judgment_date,
                "citation": citation,
                "court": chunk.get(
                    "court"
                ),
                "document_type": chunk.get(
                    "document_type"
                ),
                "source_file": source_file
            }

    print(
        "Unique documents found:",
        len(documents)
    )

    # --------------------------------------
    # Create fresh tracker
    # --------------------------------------

    tracker = IngestionTracker()

    # Clear old records
    tracker.records = {}

    # --------------------------------------
    # Add actual indexed documents
    # --------------------------------------

    for metadata in documents.values():

        source_file = metadata.get(
            "source_file"
        )

        if source_file:

            file_path = os.path.join(
                "data",
                "ingestion",
                "downloaded",
                source_file
            )

        else:

            file_path = ""

        tracker.add_record(
            metadata,
            file_path
        )

    print(
        "\nTracker synchronized successfully."
    )

    print(
        "Tracked documents:",
        tracker.count()
    )


if __name__ == "__main__":

    sync_tracker()