from sentence_transformers import CrossEncoder


class LegalReranker:

    def __init__(self):

        print("Loading legal reranker...")

        self.model = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )

        print("Reranker loaded successfully.")

    def rerank(
        self,
        question,
        results,
        top_k=5
    ):

        if not results:
            return []

        pairs = []

        for result in results:

            text = result["metadata"].get(
                "text",
                ""
            )

            pairs.append(
                [question, text]
            )

        scores = self.model.predict(
            pairs
        )

        reranked_results = []

        for result, score in zip(
            results,
            scores
        ):

            result_copy = result.copy()

            result_copy[
                "reranker_score"
            ] = float(score)

            reranked_results.append(
                result_copy
            )

        reranked_results.sort(
            key=lambda x: x["reranker_score"],
            reverse=True
        )

        return reranked_results[:top_k]


if __name__ == "__main__":

    reranker = LegalReranker()

    print(
        "\nReranker test completed successfully."
    )