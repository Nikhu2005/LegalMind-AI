import os

from app.documents.auto_ingest import (
    discover_pdf_links,
    download_judgment,
    extract_case_metadata
)

from app.documents.ingestion_tracker import (
    IngestionTracker
)

from app.documents.index_ingested import (
    index_document
)


DOWNLOAD_DIR = "data/ingestion/downloaded"


class IngestionManager:

    def __init__(self):

        print("\n========================================")
        print("          LEGALMIND AI")
        print("       AUTO-INGESTION MANAGER")
        print("========================================")

        self.tracker = IngestionTracker()

    # ==========================================
    # CREATE SAFE FILENAME
    # ==========================================

    def create_filename(
        self,
        index,
        judgment
    ):

        title = judgment.get(
            "title",
            "judgment"
        )

        safe_title = "".join(
            character
            if character.isalnum()
            or character in (
                " ",
                "-",
                "_"
            )
            else "_"
            for character in title
        )

        safe_title = "_".join(
            safe_title.split()
        )

        if not safe_title:

            safe_title = "judgment"

        return (
            f"{index:04d}_"
            f"{safe_title[:100]}.pdf"
        )

    # ==========================================
    # PROCESS ONE JUDGMENT
    # ==========================================

    def process_judgment(
        self,
        judgment,
        index
    ):

        print("\n========================================")
        print(
            f"PROCESSING JUDGMENT #{index}"
        )
        print("========================================")

        # --------------------------------------
        # Create filename
        # --------------------------------------

        filename = self.create_filename(
            index,
            judgment
        )

        # --------------------------------------
        # Download
        # --------------------------------------

        pdf_path = download_judgment(
            judgment,
            filename
        )

        if not pdf_path:

            print(
                "\nDownload failed."
            )

            return False

        # --------------------------------------
        # Extract metadata
        # --------------------------------------

        metadata = extract_case_metadata(
            pdf_path,
            source_title=judgment.get(
                "title"
            )
        )

        # --------------------------------------
        # Add source URL
        # --------------------------------------

        metadata["source_url"] = (
            judgment.get("url")
        )

        # --------------------------------------
        # Add source file
        # --------------------------------------

        metadata["source_file"] = (
            os.path.basename(pdf_path)
        )

        # --------------------------------------
        # Validate case name
        # --------------------------------------

        if not metadata.get(
            "case_name"
        ):

            print(
                "\nWARNING:"
            )

            print(
                "Could not identify case name."
            )

            print(
                "Document will not be indexed."
            )

            return False

        # --------------------------------------
        # Duplicate check
        # --------------------------------------

        if self.tracker.is_processed(
            metadata
        ):

            print(
                "\nDOCUMENT ALREADY PROCESSED"
            )

            print(
                "Skipping duplicate."
            )

            return False

        # --------------------------------------
        # Index into FAISS
        # --------------------------------------

        print(
            "\nIndexing document into "
            "LegalMind knowledge base..."
        )

        success = index_document(
            pdf_path,
            metadata
        )

        if not success:

            print(
                "\nIndexing failed."
            )

            print(
                "Document will NOT be added "
                "to ingestion tracker."
            )

            return False

        # --------------------------------------
        # Register AFTER successful indexing
        # --------------------------------------

        document_id = (
            self.tracker.add_record(
                metadata,
                pdf_path
            )
        )

        print(
            "\n========================================"
        )

        print(
            "NEW JUDGMENT SUCCESSFULLY INGESTED"
        )

        print(
            "========================================"
        )

        print(
            "Case:",
            metadata.get(
                "case_name"
            )
        )

        print(
            "Citation:",
            metadata.get(
                "citation",
                "Not available"
            )
        )

        print(
            "Document ID:",
            document_id
        )

        print(
            "File:",
            pdf_path
        )

        return True

    # ==========================================
    # RUN AUTO INGESTION
    # ==========================================

    def run(
        self,
        max_documents=1
    ):

        print(
            "\nStarting automatic discovery..."
        )

        judgments = discover_pdf_links()

        if not judgments:

            print(
                "\nNo PDF links discovered."
            )

            return

        print(
            "\nTotal discovered:",
            len(judgments)
        )

        processed = 0
        skipped = 0
        failed = 0

        # --------------------------------------
        # Process documents
        # --------------------------------------

        for index, judgment in enumerate(
            judgments[:max_documents],
            start=1
        ):

            try:

                success = self.process_judgment(
                    judgment,
                    index
                )

                if success:

                    processed += 1

                else:

                    skipped += 1

            except Exception as error:

                failed += 1

                print(
                    "\nERROR processing document:"
                )

                print(
                    error
                )

        # ======================================
        # SUMMARY
        # ======================================

        print(
            "\n========================================"
        )

        print(
            "     AUTO-INGESTION COMPLETE"
        )

        print(
            "========================================"
        )

        print(
            "Discovered:",
            len(judgments)
        )

        print(
            "Checked:",
            min(
                len(judgments),
                max_documents
            )
        )

        print(
            "Successfully indexed:",
            processed
        )

        print(
            "Skipped:",
            skipped
        )

        print(
            "Failed:",
            failed
        )

        print(
            "Tracked documents:",
            self.tracker.count()
        )


# ==========================================
# TEST
# ==========================================

if __name__ == "__main__":

    manager = IngestionManager()

    manager.run(
        max_documents=10
    )