from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import LegalReranker
from app.rag.generator import generate_answer
from app.rag.citation_verifier import print_verified_sources


def run_rag():

    print("\n========================================")
    print("           LEGALMIND AI")
    print("    AI-Powered Legal Research System")
    print("========================================")

    # --------------------------------------
    # Load systems
    # --------------------------------------

    print("\nLoading LegalMind AI...")

    retriever = HybridRetriever()
    reranker = LegalReranker()

    # --------------------------------------
    # User question
    # --------------------------------------

    question = input(
        "\nAsk your legal question: "
    )

    # --------------------------------------
    # Optional filters
    # --------------------------------------

    print("\nSearch Filters")
    print("----------------------------------------")

    court = input(
        "Court (press Enter for all): "
    ).strip()

    document_type = input(
        "Document type (Judgment/Order, press Enter for all): "
    ).strip()

    court = court if court else None
    document_type = document_type if document_type else None

    # --------------------------------------
    # Hybrid retrieval
    # --------------------------------------

    print("\nSearching legal knowledge base...")

    candidate_results = retriever.search(
        question,
        top_k=10,
        court=court,
        document_type=document_type
    )

    print(
        f"Retrieved {len(candidate_results)} candidates."
    )

    if not candidate_results:

        print(
            "\nNo relevant legal documents were found."
        )

        return

    # --------------------------------------
    # Reranking
    # --------------------------------------

    print("\nReranking legal passages...")

    results = reranker.rerank(
        question,
        candidate_results,
        top_k=5
    )

    print(
        f"Selected {len(results)} best passages."
    )

    # --------------------------------------
    # Generate grounded answer
    # --------------------------------------

    print(
        "\nGenerating grounded legal answer..."
    )

    answer = generate_answer(
        question,
        results
    )

    # --------------------------------------
    # Display answer
    # --------------------------------------

    print("\n")
    print("=" * 70)
    print("                 LEGALMIND AI ANSWER")
    print("=" * 70)

    print(answer)

    # --------------------------------------
    # Citation verification
    # --------------------------------------

    print_verified_sources(
        results
    )


if __name__ == "__main__":

    run_rag()