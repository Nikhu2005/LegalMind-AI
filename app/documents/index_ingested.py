import os

from app.documents.parser import extract_text_from_pdf
from app.documents.chunker import create_chunks
from app.embeddings.embeddings import EmbeddingModel
from app.embeddings.vector_store import FAISSVectorStore


INDEX_PATH = "data/legal_index.faiss"
METADATA_PATH = "data/metadata.json"


def index_document(
    pdf_path,
    metadata
):
    """
    Process a newly downloaded legal PDF
    and add it to the existing FAISS database.
    """

    print("\n========================================")
    print("      LEGALMIND AI")
    print("     DOCUMENT INDEXING")
    print("========================================")

    # ======================================
    # 1. Extract PDF text
    # ======================================

    print("\n1. Extracting PDF text...")

    pages = extract_text_from_pdf(
        pdf_path
    )

    print(
        "Pages extracted:",
        len(pages)
    )

    if not pages:

        print(
            "ERROR: No text extracted."
        )

        return False

    # ======================================
    # 2. Add source information
    # ======================================

    metadata["source_file"] = os.path.basename(
        pdf_path
    )

    metadata["source_url"] = metadata.get(
        "source_url"
    )

    # ======================================
    # 3. Create chunks
    # ======================================

    print("\n2. Creating legal chunks...")

    chunks = create_chunks(
        pages,
        case_metadata=metadata
    )

    print(
        "Chunks created:",
        len(chunks)
    )

    if not chunks:

        print(
            "ERROR: No chunks created."
        )

        return False

    # ======================================
    # 4. Generate embeddings
    # ======================================

    print(
        "\n3. Loading embedding model..."
    )

    embedding_model = EmbeddingModel()

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    print(
        "\n4. Generating embeddings..."
    )

    embeddings = (
        embedding_model.generate_embeddings(
            texts
        )
    )

    print(
        "Embedding shape:",
        embeddings.shape
    )

    # ======================================
    # 5. Load existing FAISS database
    # ======================================

    print(
        "\n5. Loading existing FAISS database..."
    )

    vector_store = FAISSVectorStore(
        dimension=embeddings.shape[1]
    )

    if os.path.exists(
        INDEX_PATH
    ):

        vector_store.load(
            INDEX_PATH,
            METADATA_PATH
        )

        print(
            "Existing index loaded."
        )

    else:

        print(
            "No existing index found."
        )

    # ======================================
    # 6. Add new chunks
    # ======================================

    print(
        "\n6. Adding new chunks to FAISS..."
    )

    vector_store.add_embeddings(
        embeddings,
        chunks
    )

    # ======================================
    # 7. Save updated database
    # ======================================

    print(
        "\n7. Saving updated database..."
    )

    vector_store.save(
        INDEX_PATH,
        METADATA_PATH
    )

    # ======================================
    # COMPLETE
    # ======================================

    print(
        "\n========================================"
    )

    print(
        "DOCUMENT INDEXING COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        "Case:",
        metadata.get(
            "case_name",
            "Unknown"
        )
    )

    print(
        "Pages:",
        len(pages)
    )

    print(
        "Chunks:",
        len(chunks)
    )

    print(
        "\nDocument is now searchable."
    )

    return True


# ==========================================
# TEST
# ==========================================

if __name__ == "__main__":

    print(
        "Document indexing module loaded successfully."
    )