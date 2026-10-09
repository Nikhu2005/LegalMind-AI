from app.embeddings.embeddings import EmbeddingModel
from app.embeddings.vector_store import FAISSVectorStore


INDEX_PATH = "data/legal_index.faiss"
METADATA_PATH = "data/metadata.json"


class LegalRetriever:

    def __init__(self):

        print("Loading embedding model...")
        self.embedding_model = EmbeddingModel()

        print("Loading FAISS database...")
        self.vector_store = FAISSVectorStore(
            dimension=384
        )

        self.vector_store.load(
            INDEX_PATH,
            METADATA_PATH
        )

    def search(self, question, top_k=5):

        query_embedding = (
            self.embedding_model
            .generate_embeddings([question])[0]
        )

        results = self.vector_store.search(
            query_embedding,
            top_k=top_k
        )

        return results


if __name__ == "__main__":

    retriever = LegalRetriever()

    question = input(
        "\nAsk a question about Indian case law: "
    )

    print("\nSearching legal knowledge base...")

    results = retriever.search(
        question,
        top_k=5
    )

    print("\n")
    print("=" * 60)
    print("LEGAL SEARCH RESULTS")
    print("=" * 60)

    for i, result in enumerate(
        results,
        start=1
    ):

        metadata = result["metadata"]

        print(f"\nRESULT {i}")
        print("-" * 60)

        print(
            "Similarity:",
            f"{result['score']:.4f}"
        )

        print(
            "Case:",
            metadata.get(
                "case_name",
                "Not available"
            )
        )

        print(
            "Court:",
            metadata.get(
                "court",
                "Not available"
            )
        )

        print(
            "Judgment Date:",
            metadata.get(
                "judgment_date",
                "Not available"
            )
        )

        print(
            "Case Number:",
            metadata.get(
                "case_number",
                "Not available"
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
            "Document Type:",
            metadata.get(
                "document_type",
                "Not available"
            )
        )

        print(
            "Acts:",
            metadata.get(
                "acts",
                []
            )
        )

        print(
            "Sections:",
            metadata.get(
                "sections",
                []
            )
        )

        print(
            "Page:",
            metadata.get(
                "page_number",
                "Not available"
            )
        )

        print("\nText:")
        print(
            metadata.get(
                "text",
                ""
            )[:800]
        )