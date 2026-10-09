import os

from app.documents.parser import extract_text_from_pdf
from app.documents.chunker import create_chunks
from app.documents.metadata_extractor import extract_legal_metadata
from app.embeddings.embeddings import EmbeddingModel
from app.embeddings.vector_store import FAISSVectorStore


JUDGMENTS_FOLDER = "data/ingestion/downloaded"
INDEX_PATH = "data/legal_index.faiss"
METADATA_PATH = "data/metadata.json"


def get_pdf_files():
    pdf_files = []

    for filename in os.listdir(JUDGMENTS_FOLDER):
        if filename.lower().endswith(".pdf"):
            pdf_files.append(
                os.path.join(JUDGMENTS_FOLDER, filename)
            )

    return sorted(pdf_files)


def build_multi_document_index():

    pdf_files = get_pdf_files()

    if not pdf_files:
        print("No PDF judgments found.")
        return

    print(f"\nFound {len(pdf_files)} PDF(s).")

    all_chunks = []

    for pdf_path in pdf_files:

        print("\n================================")
        print("Processing:", pdf_path)
        print("================================")

        # 1. Extract pages
        pages = extract_text_from_pdf(pdf_path)

        print(f"Pages extracted: {len(pages)}")

        document_name = os.path.basename(pdf_path)

        # 2. Extract metadata from first pages
        first_pages_text = "\n".join(
            page["text"]
            for page in pages[:5]
        )

        print("\nExtracting legal metadata...")

        metadata = extract_legal_metadata(
            first_pages_text,
            document_name
        )

        print("\nMetadata:")
        print("Case:", metadata.get("case_name"))
        print("Court:", metadata.get("court"))
        print("Date:", metadata.get("judgment_date"))
        print("Case Number:", metadata.get("case_number"))
        print("Citation:", metadata.get("citation"))
        print("Type:", metadata.get("document_type"))

        # 3. Create chunks with metadata
        chunks = create_chunks(
            pages,
            case_metadata=metadata
        )

        print(f"\nChunks created: {len(chunks)}")

        all_chunks.extend(chunks)

    # --------------------------------
    # Create embeddings
    # --------------------------------

    print("\n================================")
    print("LOADING EMBEDDING MODEL")
    print("================================")

    embedding_model = EmbeddingModel()

    texts = [
        chunk["text"]
        for chunk in all_chunks
    ]

    print(
        f"\nCreating embeddings for "
        f"{len(texts)} chunks..."
    )

    embeddings = embedding_model.generate_embeddings(
        texts
    )

    print(
        "Embedding shape:",
        embeddings.shape
    )

    # --------------------------------
    # Create FAISS index
    # --------------------------------

    print("\nCreating FAISS index...")

    vector_store = FAISSVectorStore(
        dimension=embeddings.shape[1]
    )

    vector_store.add_embeddings(
        embeddings,
        all_chunks
    )

    # --------------------------------
    # Save
    # --------------------------------

    print("\nSaving vector database...")

    vector_store.save(
        INDEX_PATH,
        METADATA_PATH
    )

    print("\n================================")
    print("LEGAL KNOWLEDGE BASE CREATED")
    print("================================")

    print(f"Documents: {len(pdf_files)}")
    print(f"Total chunks: {len(all_chunks)}")

    print(f"FAISS index: {INDEX_PATH}")
    print(f"Metadata: {METADATA_PATH}")


if __name__ == "__main__":
    build_multi_document_index()