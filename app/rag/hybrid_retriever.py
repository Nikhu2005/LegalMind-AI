import faiss
import numpy as np

from app.embeddings.embeddings import EmbeddingModel
from app.rag.metadata_store import MetadataStore


INDEX_PATH = "data/legal_index.faiss"
METADATA_DB_PATH = "data/metadata.db"

# Filtered searches take this many candidates from each method, then keep matches.
FILTER_CANDIDATE_POOL = 1000
RANK_CONSTANT = 60
SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30


def matches_filters(
    document,
    court=None,
    case_name=None,
    act=None,
    section=None,
    document_type=None
):
    """Return True when a chunk's metadata satisfies every filter that is set."""

    if court and court.lower() not in str(document.get("court") or "").lower():
        return False

    if case_name and case_name.lower() not in str(document.get("case_name") or "").lower():
        return False

    if act and not any(act.lower() in str(item).lower() for item in document.get("acts", [])):
        return False

    if section and not any(section.lower() in str(item).lower() for item in document.get("sections", [])):
        return False

    if document_type and document_type.lower() != str(document.get("document_type") or "").lower():
        return False

    return True


def result_key(result):
    metadata = result["metadata"]
    source_file = metadata.get("source_file", "unknown")
    chunk_id = metadata.get("chunk_id")
    if chunk_id is not None:
        return source_file, str(chunk_id)

    text = " ".join(str(metadata.get("text") or "").lower().split())
    return (
        source_file,
        str(metadata.get("page_number", "unknown")),
        text
    )


def passage_key(metadata):
    text = " ".join(str(metadata.get("text") or "").lower().split())
    return (
        metadata.get("source_file", "unknown"),
        metadata.get("page_number", "unknown"),
        text
    )


class HybridRetriever:

    def __init__(self):

        print("Loading embedding model...")
        self.embedding_model = EmbeddingModel()

        print("Loading FAISS database...")
        self.faiss_index = faiss.read_index(INDEX_PATH)

        print("Loading metadata store...")
        self.store = MetadataStore(METADATA_DB_PATH)

        print("Hybrid retrieval system loaded.")

    # ==========================================
    # SEMANTIC SEARCH
    # ==========================================

    def semantic_search(self, question, top_k=5):

        query_embedding = (
            self.embedding_model
            .generate_embeddings([question])[0]
        )

        scores, indices = self.faiss_index.search(
            np.asarray([query_embedding], dtype="float32"),
            top_k
        )

        results = []

        for score, index in zip(scores[0], indices[0]):

            if index < 0:
                continue

            metadata = self.store.get(int(index))

            if metadata is None:
                continue

            results.append({
                "score": float(score),
                "metadata": metadata
            })

        return results

    # ==========================================
    # KEYWORD SEARCH
    # ==========================================

    def keyword_search(self, question, top_k=5):

        return self.store.keyword_search(
            question,
            top_k=top_k
        )

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
        filters = {
            "court": court,
            "case_name": case_name,
            "act": act,
            "section": section,
            "document_type": document_type,
        }
        filters_used = any(filters.values())

        pool_size = FILTER_CANDIDATE_POOL if filters_used else top_k
        semantic_results = self.semantic_search(question, pool_size)
        keyword_results = self.keyword_search(question, pool_size)

        if filters_used:
            semantic_results = _keep_matching(semantic_results, filters)
            keyword_results = _keep_matching(keyword_results, filters)

        combined = _fuse_rankings(semantic_results, keyword_results)
        return _drop_duplicate_passages(combined, top_k)


def _keep_matching(results, filters):
    return [
        result for result in results
        if matches_filters(result["metadata"], **filters)
    ]


def _fuse_rankings(semantic_results, keyword_results):
    """Reciprocal-rank fusion of the semantic and keyword result lists."""

    combined = {}

    for rank, result in enumerate(semantic_results, start=1):
        entry = combined.setdefault(result_key(result), _new_entry(result))
        entry["semantic_score"] = float(result["score"])
        entry["semantic_rank"] = rank

    for rank, result in enumerate(keyword_results, start=1):
        entry = combined.setdefault(result_key(result), _new_entry(result))
        entry["keyword_score"] = float(result["score"])
        entry["keyword_rank"] = rank

    fused = []
    for entry in combined.values():
        fused.append({
            "score": _fused_score(entry),
            "semantic_score": entry["semantic_score"],
            "keyword_score": entry["keyword_score"],
            "metadata": entry["metadata"]
        })

    fused.sort(key=lambda item: item["score"], reverse=True)
    return fused


def _new_entry(result):
    return {
        "metadata": result["metadata"],
        "semantic_score": 0.0,
        "keyword_score": 0.0,
        "semantic_rank": None,
        "keyword_rank": None
    }


def _fused_score(entry):
    score = 0.0
    if entry["semantic_rank"] is not None:
        score += SEMANTIC_WEIGHT / (RANK_CONSTANT + entry["semantic_rank"])
    if entry["keyword_rank"] is not None:
        score += KEYWORD_WEIGHT / (RANK_CONSTANT + entry["keyword_rank"])
    return score


def _drop_duplicate_passages(results, top_k):
    unique_results = []
    seen_passages = set()

    for result in results:
        key = passage_key(result["metadata"])
        if key in seen_passages:
            continue

        seen_passages.add(key)
        unique_results.append(result)
        if len(unique_results) >= top_k:
            break

    return unique_results


# ==========================================
# TEST
# ==========================================

if __name__ == "__main__":

    retriever = HybridRetriever()

    question = input("\nEnter your legal question: ")

    results = retriever.search(question, top_k=5)

    print("\nResults found:", len(results))

    for i, result in enumerate(results, start=1):
        metadata = result["metadata"]

        print(f"\nRESULT {i}")
        print("Hybrid Score:", round(result["score"], 4))
        print("Semantic Score:", round(result["semantic_score"], 4))
        print("Keyword Score:", round(result["keyword_score"], 4))
        print("Case:", metadata.get("case_name") or "Unknown")
        print("Court:", metadata.get("court") or "Unknown")
        print("Page:", metadata.get("page_number", "Unknown"))
        print("\nText:")
        print(str(metadata.get("text", ""))[:600])
        print("\n----------------------------------------")
