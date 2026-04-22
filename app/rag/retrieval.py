"""
Retrieval Module
Handles document retrieval from vector store for RAG pipeline
"""

import os
from typing import List, Dict, Any, Optional, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.embedding import get_global_embedding_model, EmbeddingModel

logger = get_logger(__name__)


class VectorStore:
    """
    Vector store wrapper for document storage and retrieval.
    Uses ChromaDB as the underlying vector database.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        persist_directory: str = None,
        embedding_model: EmbeddingModel = None
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory or settings.vector_db_path
        self.embedding_model = embedding_model or get_global_embedding_model()
        self._client = None
        self._collection = None

    @property
    def client(self) -> chromadb.Client:
        """Get or create ChromaDB client."""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        """Get or create the collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def add_documents(
        self,
        documents: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of document texts
            embeddings: Optional pre-computed embeddings
            metadatas: Optional metadata for each document
            ids: Optional IDs for each document

        Returns:
            List of document IDs
        """
        if not documents:
            return []

        # Generate embeddings if not provided
        if embeddings is None:
            embeddings = self.embedding_model.embed(documents)

        # Generate IDs if not provided
        if ids is None:
            ids = [f"doc_{i}_{self.collection.count() + i}" for i in range(len(documents))]

        # Add to collection
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Added {len(documents)} documents to vector store")
        return ids

    def search(
        self,
        query: str,
        k: int = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        score_threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents.

        Args:
            query: Search query text
            k: Number of results to return
            filter_metadata: Optional metadata filter
            score_threshold: Minimum similarity score threshold

        Returns:
            List of relevant documents with scores
        """
        k = k or settings.retrieval_top_k

        # Generate query embedding
        query_embedding = self.embedding_model.embed_query(query)

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"]
        )

        # Process results
        documents = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                score = 1 - results["distances"][0][i]  # Convert distance to similarity

                if score_threshold and score < score_threshold:
                    continue

                documents.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": round(score, 4)
                })

        return documents

    def search_by_embedding(
        self,
        embedding: List[float],
        k: int = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using a pre-computed embedding.

        Args:
            embedding: Query embedding vector
            k: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            List of relevant documents with scores
        """
        k = k or settings.retrieval_top_k

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"]
        )

        documents = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                score = 1 - results["distances"][0][i]
                documents.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": round(score, 4)
                })

        return documents

    def delete_documents(self, ids: List[str]) -> None:
        """
        Delete documents from the vector store.

        Args:
            ids: List of document IDs to delete
        """
        if ids:
            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents from vector store")

    def clear(self) -> None:
        """Clear all documents from the collection."""
        self.client.delete_collection(self.collection_name)
        self._collection = None
        logger.info("Cleared vector store")

    def get_document_count(self) -> int:
        """Get the total number of documents in the store."""
        return self.collection.count()

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        return {
            "name": self.collection.name,
            "count": self.collection.count(),
            "metadata": self.collection.metadata
        }


# Global vector store instance
_vector_store: Optional[VectorStore] = None


def get_vector_store(
    collection_name: str = None,
    persist_directory: str = None
) -> VectorStore:
    """
    Get or create the global vector store instance.
    """
    global _vector_store

    if _vector_store is None:
        _vector_store = VectorStore(
            collection_name=collection_name or "documents",
            persist_directory=persist_directory or settings.vector_db_path
        )

    return _vector_store


def create_vector_store(
    collection_name: str = "documents",
    persist_directory: str = None
) -> VectorStore:
    """
    Create a new vector store instance.
    """
    return VectorStore(
        collection_name=collection_name,
        persist_directory=persist_directory
    )


async def initialize_vector_store():
    """Initialize the global vector store during app startup."""
    get_vector_store()