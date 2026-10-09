from sentence_transformers import SentenceTransformer


class EmbeddingModel:

    def __init__(self):
        print("Loading embedding model...")

        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

        print("Embedding model loaded successfully.")

    def generate_embeddings(self, texts):
        """
        Convert text into numerical embeddings.
        """

        embeddings = self.model.encode(
            texts,
            show_progress_bar=True,
            normalize_embeddings=True
        )

        return embeddings


if __name__ == "__main__":

    model = EmbeddingModel()

    test_texts = [
        "The court dismissed the appeal.",
        "The accused filed an appeal against the judgment.",
        "The weather is sunny today."
    ]

    embeddings = model.generate_embeddings(test_texts)

    print("\nNumber of texts:", len(test_texts))
    print("Embedding shape:", embeddings.shape)

    print("\nFirst embedding:")
    print(embeddings[0][:10])