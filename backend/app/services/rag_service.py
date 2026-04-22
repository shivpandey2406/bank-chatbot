
from sentence_transformers import SentenceTransformer
import chromadb

class RAGService:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection("documents")

    def ingest(self, docs):
        embeddings = self.model.encode(docs).tolist()
        for i, doc in enumerate(docs):
            self.collection.add(
                documents=[doc],
                embeddings=[embeddings[i]],
                ids=[str(i)]
            )

    def query(self, text):
        embedding = self.model.encode([text]).tolist()[0]
        results = self.collection.query(query_embeddings=[embedding], n_results=3)
        return results
