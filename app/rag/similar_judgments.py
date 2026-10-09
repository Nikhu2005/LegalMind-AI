from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import LegalReranker


def build_case_query(case_analysis):
    """
    Convert extracted case analysis into a search query.
    """

    parts = []

    for key in [
        "legal_issues",
        "acts",
        "sections",
        "facts",
        "arguments",
        "legal_concepts"
    ]:

        values = case_analysis.get(key, [])

        if values:

            for value in values:
                parts.append(str(value))

    return " ".join(parts)


def find_similar_judgments(case_analysis, top_k=5):
    """
    Find previous judgments that are semantically and
    legally relevant to the uploaded case.
    """

    query = build_case_query(case_analysis)

    if not query.strip():
        return []

    # --------------------------------------------------------
    # STEP 1: HYBRID RETRIEVAL
    # --------------------------------------------------------

    retriever = HybridRetriever()

    candidates = retriever.search(
        query,
        top_k=20
    )

    if not candidates:
        return []

    # --------------------------------------------------------
    # STEP 2: RERANK RESULTS
    # --------------------------------------------------------

    reranker = LegalReranker()

    reranked = reranker.rerank(
        query,
        candidates,
        top_k=15
    )

    # --------------------------------------------------------
    # STEP 3: GROUP RESULTS BY CASE
    # --------------------------------------------------------

    cases = {}

    for result in reranked:

        metadata = result.get(
            "metadata",
            {}
        )

        case_name = metadata.get("case_name")

        if not case_name:
            continue

        case_key = (
            case_name,
            metadata.get("case_number"),
            metadata.get("judgment_date"),
            metadata.get("citation")
        )

        score = result.get(
            "reranker_score",
            0
        )

        page = metadata.get(
            "page_number"
        )

        # ----------------------------------------------------
        # NEW CASE
        # ----------------------------------------------------

        if case_key not in cases:

            cases[case_key] = {

                "case_name": case_name,

                "court": metadata.get(
                    "court"
                ),

                "judgment_date": metadata.get(
                    "judgment_date"
                ),

                "case_number": metadata.get(
                    "case_number"
                ),

                "citation": metadata.get(
                    "citation"
                ),

                "document_type": metadata.get(
                    "document_type"
                ),

                "acts": metadata.get(
                    "acts",
                    []
                ),

                "sections": metadata.get(
                    "sections",
                    []
                ),

                "jurisdiction": metadata.get(
                    "jurisdiction"
                ),

                "source_file": metadata.get(
                    "source_file"
                ),

                "source_url": metadata.get(
                    "source_url"
                ),

                "relevance_score": float(
                    score
                ),

                "relevant_pages": []
            }

        # ----------------------------------------------------
        # UPDATE BEST SCORE
        # ----------------------------------------------------

        else:

            if score > cases[case_key]["relevance_score"]:

                cases[case_key]["relevance_score"] = float(
                    score
                )

        # ----------------------------------------------------
        # STORE RELEVANT PAGE
        # ----------------------------------------------------

        if (
            page is not None
            and page not in cases[case_key]["relevant_pages"]
        ):

            cases[case_key]["relevant_pages"].append(
                page
            )

    # --------------------------------------------------------
    # STEP 4: SORT BY RELEVANCE
    # --------------------------------------------------------

    results = list(
        cases.values()
    )

    results.sort(
        key=lambda x: x["relevance_score"],
        reverse=True
    )

    return results[:top_k]


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_analysis = {

        "legal_issues": [
            "appeal against judgment"
        ],

        "acts": [],

        "sections": [],

        "facts": [
            "dispute regarding the decision of the lower court"
        ],

        "arguments": [],

        "legal_concepts": [
            "appeal",
            "judicial decision"
        ]
    }

    print("\nSearching for similar judgments...")

    results = find_similar_judgments(
        test_analysis,
        top_k=5
    )

    print(
        f"\nFound {len(results)} similar judgments.\n"
    )

    for index, result in enumerate(
        results,
        start=1
    ):

        print("=" * 70)

        print(
            f"RESULT {index}"
        )

        print(
            "Case:",
            result.get(
                "case_name"
            )
        )

        print(
            "Court:",
            result.get(
                "court"
            )
        )

        print(
            "Date:",
            result.get(
                "judgment_date"
            )
        )

        print(
            "Citation:",
            result.get(
                "citation"
            )
        )

        print(
            "Relevance Score:",
            result.get(
                "relevance_score"
            )
        )

        print(
            "Relevant Pages:",
            result.get(
                "relevant_pages"
            )
        )