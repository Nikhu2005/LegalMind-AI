import os
import json
import hashlib


TRACKER_PATH = "data/ingestion/ingestion_log.json"


class IngestionTracker:

    def __init__(self):

        os.makedirs(
            os.path.dirname(TRACKER_PATH),
            exist_ok=True
        )

        if os.path.exists(TRACKER_PATH):

            with open(
                TRACKER_PATH,
                "r",
                encoding="utf-8"
            ) as file:

                self.records = json.load(file)

        else:

            self.records = {}

    # ==========================================
    # GENERATE DOCUMENT ID
    # ==========================================

    def generate_document_id(
        self,
        metadata
    ):

        """
        Create a stable ID using legal metadata.
        """

        identifier = "|".join([
            str(metadata.get(
                "case_name",
                ""
            )),

            str(metadata.get(
                "case_number",
                ""
            )),

            str(metadata.get(
                "judgment_date",
                ""
            )),

            str(metadata.get(
                "citation",
                ""
            ))
        ])

        document_id = hashlib.sha256(
            identifier.encode(
                "utf-8"
            )
        ).hexdigest()

        return document_id

    # ==========================================
    # CHECK IF PROCESSED
    # ==========================================

    def is_processed(
        self,
        metadata
    ):

        document_id = (
            self.generate_document_id(
                metadata
            )
        )

        return document_id in self.records

    # ==========================================
    # ADD RECORD
    # ==========================================

    def add_record(
        self,
        metadata,
        file_path
    ):

        document_id = (
            self.generate_document_id(
                metadata
            )
        )

        self.records[document_id] = {

            "case_name":
                metadata.get(
                    "case_name"
                ),

            "case_number":
                metadata.get(
                    "case_number"
                ),

            "judgment_date":
                metadata.get(
                    "judgment_date"
                ),

            "citation":
                metadata.get(
                    "citation"
                ),

            "court":
                metadata.get(
                    "court"
                ),

            "document_type":
                metadata.get(
                    "document_type"
                ),

            "file_path":
                file_path
        }

        self.save()

        return document_id

    # ==========================================
    # SAVE
    # ==========================================

    def save(self):

        with open(
            TRACKER_PATH,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                self.records,
                file,
                ensure_ascii=False,
                indent=2
            )

    # ==========================================
    # COUNT
    # ==========================================

    def count(self):

        return len(
            self.records
        )


# ==========================================
# TEST
# ==========================================

if __name__ == "__main__":

    tracker = IngestionTracker()

    print(
        "\n========================================"
    )

    print(
        "LEGALMIND AI"
    )

    print(
        "INGESTION TRACKER TEST"
    )

    print(
        "========================================"
    )

    test_metadata = {

        "case_name":
            "Test Case v. Test Respondent",

        "case_number":
            "Civil Appeal No. 123 of 2026",

        "judgment_date":
            "2026-10-02",

        "citation":
            "2026 INSC TEST",

        "court":
            "Supreme Court of India",

        "document_type":
            "Judgment"
    }

    document_id = (
        tracker.generate_document_id(
            test_metadata
        )
    )

    print(
        "\nGenerated Document ID:"
    )

    print(
        document_id
    )

    print(
        "\nAlready processed:",
        tracker.is_processed(
            test_metadata
        )
    )

    print(
        "\nCurrent tracked documents:",
        tracker.count()
    )