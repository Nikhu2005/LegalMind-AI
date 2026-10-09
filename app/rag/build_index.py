from app.documents.parser import extract_text_from_pdf
from app.documents.chunker import create_chunks
from app.embeddings.embeddings import EmbeddingModel
from app.embeddings.vector_store import FAISSVectorStore

import os


PDF_PATH = "data/sample.pdf"

INDEX_PATH = "data/legal_index.faiss"
METADATA_PATH = "data/metadata.json"


def build_index():

    print("\n1. Extracting PDF text...")

    pages = extract_text_from_pdf(PDF_PATH)

    print(f"Pages extracted: {len(pages)}")

    print("\n2. Creating chunks...")

    document_name = os.path.basename(PDF_PATH)

    chunks = create_chunks(
        pages,
        document_name=document_name
    )

    print(f"Chunks created: {len(chunks)}")

    print("\n3. Loading embedding model...")

    embedding_model = EmbeddingModel()

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    print("\n4. Creating embeddings...")

    embeddings = embedding_model.generate_embeddings(texts)

    print(
        f"Embedding shape: {embeddings.shape}"
    )

    print("\n5. Creating FAISS index...")

    vector_store = FAISSVectorStore(
        dimension=embeddings.shape[1]
    )

    vector_store.add_embeddings(
        embeddings,
        chunks
    )

    print("\n6. Saving vector database...")

    vector_store.save(
        INDEX_PATH,
        METADATA_PATH
    )

    print("\n================================")
    print("LEGAL DOCUMENT INDEX CREATED")
    print("================================")

    print(f"Pages: {len(pages)}")
    print(f"Chunks: {len(chunks)}")
    print(f"Index: {INDEX_PATH}")
    print(f"Metadata: {METADATA_PATH}")


if __name__ == "__main__":
    build_index()