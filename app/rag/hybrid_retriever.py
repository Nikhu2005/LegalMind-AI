import json
import numpy as np

from rank_bm25 import BM25Okapi

from app.embeddings.embeddings import EmbeddingModel
from app.embeddings.vector_store import FAISSVectorStore


INDEX_PATH = "data/legal_index.faiss"
METADATA_PATH = "data/metadata.json"


class HybridRetriever:

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

        print("Loading BM25 index...")

        with open(
            METADATA_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            self.documents = json.load(file)

        tokenized_documents = [
            self.tokenize(
                document.get("text", "")
            )
            for document in self.documents
        ]

        self.bm25 = BM25Okapi(
            tokenized_documents
        )

        print("Hybrid retrieval system loaded.")

    # ==========================================
    # TOKENIZER
    # ==========================================

    def tokenize(self, text):

        return text.lower().split()

    # ==========================================
    # SEMANTIC SEARCH
    # ==========================================

    def semantic_search(
        self,
        question,
        top_k=5
    ):

        query_embedding = (
            self.embedding_model
            .generate_embeddings(
                [question]
            )[0]
        )

        results = self.vector_store.search(
            query_embedding,
            top_k=top_k
        )

        return results

    # ==========================================
    # KEYWORD SEARCH
    # ==========================================

    def keyword_search(
        self,
        question,
        top_k=5
    ):

        query_tokens = self.tokenize(
            question
        )

        scores = self.bm25.get_scores(
            query_tokens
        )

        top_indices = np.argsort(
            scores
        )[::-1][:top_k]

        results = []

        for index in top_indices:

            results.append({
                "score": float(
                    scores[index]
                ),
                "metadata":
                    self.documents[index]
            })

        return results

    # ==========================================
    # METADATA FILTERING
    # ==========================================

    def filter_documents(
        self,
        court=None,
        case_name=None,
        act=None,
        section=None,
        document_type=None
    ):

        filtered = []

        for document in self.documents:

            # Court
            if court:

                document_court = document.get(
                    "court",
                    ""
                )

                if court.lower() not in document_court.lower():
                    continue

            # Case name
            if case_name:

                document_case = document.get(
                    "case_name",
                    ""
                )

                if case_name.lower() not in document_case.lower():
                    continue

            # Act
            if act:

                acts = document.get(
                    "acts",
                    []
                )

                if not any(
                    act.lower() in str(item).lower()
                    for item in acts
                ):
                    continue

            # Section
            if section:

                sections = document.get(
                    "sections",
                    []
                )

                if not any(
                    section.lower() in str(item).lower()
                    for item in sections
                ):
                    continue

            # Document type
            if document_type:

                doc_type = document.get(
                    "document_type",
                    ""
                )

                if document_type.lower() != doc_type.lower():
                    continue

            filtered.append(document)

        return filtered

    # ==========================================
    # FILTERED SEMANTIC SEARCH
    # ==========================================

    def filtered_semantic_search(
        self,
        question,
        documents,
        top_k=5
    ):

        if not documents:
            return []

        texts = [
            document.get("text", "")
            for document in documents
        ]

        query_embedding = (
            self.embedding_model
            .generate_embeddings(
                [question]
            )[0]
        )

        document_embeddings = (
            self.embedding_model
            .generate_embeddings(
                texts
            )
        )

        scores = np.dot(
            document_embeddings,
            query_embedding
        )

        top_indices = np.argsort(
            scores
        )[::-1][:top_k]

        results = []

        for index in top_indices:

            results.append({
                "score": float(
                    scores[index]
                ),
                "metadata":
                    documents[index]
            })

        return results

    # ==========================================
    # FILTERED KEYWORD SEARCH
    # ==========================================

    def filtered_keyword_search(
        self,
        question,
        documents,
        top_k=5
    ):

        if not documents:
            return []

        tokenized_documents = [
            self.tokenize(
                document.get("text", "")
            )
            for document in documents
        ]

        bm25 = BM25Okapi(
            tokenized_documents
        )

        query_tokens = self.tokenize(
            question
        )

        scores = bm25.get_scores(
            query_tokens
        )

        top_indices = np.argsort(
            scores
        )[::-1][:top_k]

        results = []

        for index in top_indices:

            results.append({
                "score": float(
                    scores[index]
                ),
                "metadata":
                    documents[index]
            })

        return results

    # ==========================================
    # HYBRID SEARCH
    # ==========================================

    def search(
        self,
        question,
        top_k=5,
        court=None,
        case_name=None,
        act=None,
        section=None,
        document_type=None
    ):

        # --------------------------------------
        # Check whether filters are provided
        # --------------------------------------

        filters_used = any([
            court,
            case_name,
            act,
            section,
            document_type
        ])

        # --------------------------------------
        # Normal Hybrid Search
        # --------------------------------------

        if not filters_used:

            semantic_results = self.semantic_search(
                question,
                top_k
            )

            keyword_results = self.keyword_search(
                question,
                top_k
            )

        # --------------------------------------
        # Filtered Hybrid Search
        # --------------------------------------

        else:

            filtered_documents = self.filter_documents(
                court=court,
                case_name=case_name,
                act=act,
                section=section,
                document_type=document_type
            )

            if not filtered_documents:
                return []

            semantic_results = (
                self.filtered_semantic_search(
                    question,
                    filtered_documents,
                    top_k
                )
            )

            keyword_results = (
                self.filtered_keyword_search(
                    question,
                    filtered_documents,
                    top_k
                )
            )

        # ======================================
        # COMBINE RESULTS
        # ======================================

        combined = {}

        # Semantic results
        for result in semantic_results:

            chunk_id = result["metadata"].get(
                "chunk_id"
            )

            combined[chunk_id] = {
                "metadata":
                    result["metadata"],

                "semantic_score":
                    result["score"],

                "keyword_score":
                    0.0
            }

        # Keyword results
        for result in keyword_results:

            chunk_id = result["metadata"].get(
                "chunk_id"
            )

            if chunk_id not in combined:

                combined[chunk_id] = {
                    "metadata":
                        result["metadata"],

                    "semantic_score":
                        0.0,

                    "keyword_score":
                        result["score"]
                }

            else:

                combined[chunk_id][
                    "keyword_score"
                ] = result["score"]

        # ======================================
        # SCORE NORMALIZATION
        # ======================================

        results = []

        semantic_scores = [
            item["semantic_score"]
            for item in combined.values()
        ]

        keyword_scores = [
            item["keyword_score"]
            for item in combined.values()
        ]

        max_semantic = max(
            semantic_scores,
            default=1.0
        )

        max_keyword = max(
            keyword_scores,
            default=1.0
        )

        for item in combined.values():

            # Semantic normalization
            if max_semantic != 0:

                semantic_score = (
                    item["semantic_score"]
                    / max_semantic
                )

            else:

                semantic_score = 0

            # Keyword normalization
            if max_keyword != 0:

                keyword_score = (
                    item["keyword_score"]
                    / max_keyword
                )

            else:

                keyword_score = 0

            # 70% Semantic + 30% Keyword
            hybrid_score = (
                0.70 * semantic_score
                +
                0.30 * keyword_score
            )

            results.append({

                "score":
                    hybrid_score,

                "semantic_score":
                    item["semantic_score"],

                "keyword_score":
                    item["keyword_score"],

                "metadata":
                    item["metadata"]
            })

        # ======================================
        # SORT RESULTS
        # ======================================

        results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

      
        # Return distinct judgments, not repeated chunks
        unique_results = []
        seen_cases = set()

        for result in results:
            metadata = result["metadata"]

            case_key = (
                metadata.get("source_file")
                or metadata.get("case_number")
                or metadata.get("case_name")
                or metadata.get("chunk_id")
            )

            if case_key in seen_cases:
                continue

            seen_cases.add(case_key)
            unique_results.append(result)

            if len(unique_results) >= top_k:
                break

        return unique_results



# ==========================================
# TEST
# ==========================================

if __name__ == "__main__":

    retriever = HybridRetriever()

    print("\n========================================")
    print("LEGALMIND AI - FILTERED HYBRID SEARCH")
    print("========================================")

    question = input(
        "\nEnter your legal question: "
    )

    print(
        "\nSearching Supreme Court judgments..."
    )

    results = retriever.search(
        question,
        top_k=5,
        court="Supreme Court of India",
        document_type="Judgment"
    )

    print(
        "\nResults found:",
        len(results)
    )

    print("\n========================================")

    for i, result in enumerate(
        results,
        start=1
    ):

        metadata = result["metadata"]

        print(
            f"\nRESULT {i}"
        )

        print(
            "Hybrid Score:",
            round(
                result["score"],
                4
            )
        )

        print(
            "Semantic Score:",
            round(
                result["semantic_score"],
                4
            )
        )

        print(
            "Keyword Score:",
            round(
                result["keyword_score"],
                4
            )
        )

        print(
            "Case:",
            metadata.get(
                "case_name",
                "Unknown"
            )
        )

        print(
            "Court:",
            metadata.get(
                "court",
                "Unknown"
            )
        )

        print(
            "Date:",
            metadata.get(
                "judgment_date",
                "Unknown"
            )
        )

        print(
            "Citation:",
            metadata.get(
                "citation",
                "Unknown"
            )
        )

        print(
            "Page:",
            metadata.get(
                "page_number",
                "Unknown"
            )
        )

        print(
            "Type:",
            metadata.get(
                "document_type",
                "Unknown"
            )
        )

        print(
            "\nText:"
        )

        print(
            metadata.get(
                "text",
                ""
            )[:600]
        )

        print(
            "\n----------------------------------------"
        )