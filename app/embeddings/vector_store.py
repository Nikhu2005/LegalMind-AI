import faiss
import json
import numpy as np


class FAISSVectorStore:

    def __init__(self, dimension):
        self.dimension = dimension

        # Inner Product works with normalized embeddings
        self.index = faiss.IndexFlatIP(dimension)

        self.metadata = []

    def add_embeddings(self, embeddings, metadata):
        """
        Add embeddings and their metadata to FAISS.
        """

        embeddings = np.asarray(
            embeddings,
            dtype="float32"
        )

        self.index.add(embeddings)
        self.metadata.extend(metadata)

    def search(self, query_embedding, top_k=5):
        """
        Search for the most similar chunks.
        """

        query_embedding = np.asarray(
            [query_embedding],
            dtype="float32"
        )

        scores, indices = self.index.search(
            query_embedding,
            top_k
        )

        results = []

        for score, index in zip(scores[0], indices[0]):

            if index == -1:
                continue

            results.append({
                "score": float(score),
                "metadata": self.metadata[index]
            })

        return results

    def save(self, index_path, metadata_path):

        faiss.write_index(
            self.index,
            index_path
        )

        with open(metadata_path, "w", encoding="utf-8") as file:
            json.dump(
                self.metadata,
                file,
                ensure_ascii=False,
                indent=2
            )

        print("Vector database saved successfully.")

    def load(self, index_path, metadata_path):

        self.index = faiss.read_index(index_path)

        with open(metadata_path, "r", encoding="utf-8") as file:
            self.metadata = json.load(file)

        print("Vector database loaded successfully.")


# --------------------------------------------------
# TEST FAISS
# --------------------------------------------------

if __name__ == "__main__":

    # all-MiniLM-L6-v2 produces 384-dimensional embeddings
    store = FAISSVectorStore(dimension=384)

    embeddings = np.array([
        [1.0] + [0.0] * 383,
        [0.9] + [0.1] + [0.0] * 382,
        [0.0] + [1.0] + [0.0] * 382
    ], dtype="float32")

    metadata = [
        {
            "chunk_id": "chunk_1",
            "page_number": 1,
            "text": "The court dismissed the appeal."
        },
        {
            "chunk_id": "chunk_2",
            "page_number": 2,
            "text": "The accused filed an appeal."
        },
        {
            "chunk_id": "chunk_3",
            "page_number": 3,
            "text": "The court discussed the evidence."
        }
    ]

    store.add_embeddings(
        embeddings,
        metadata
    )

    query = np.array(
        [1.0] + [0.0] * 383,
        dtype="float32"
    )

    results = store.search(
        query,
        top_k=2
    )

    print("\nSearch Results:")

    for result in results:

        print("\nScore:", result["score"])
        print("Chunk:", result["metadata"]["chunk_id"])
        print("Page:", result["metadata"]["page_number"])
        print("Text:", result["metadata"]["text"])