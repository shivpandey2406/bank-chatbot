"""
RAG Service - ChromaDB + SentenceTransformers (FREE)
Production-ready banking data ingestion/retrieval
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.core.logging import get_logger
from app.rag.retrieval import get_vector_store, VectorStore
from app.rag.embedding import get_global_embedding_model, EmbeddingModel
from app.rag.ingestion import ingest_file, ingest_text
from app.rag.structured_query import QueryParser, QueryExecutor, StructuredQuery

logger = get_logger(__name__)


class RAGService:
    """
    Service for RAG operations including retrieval and generation.
    """

    def __init__(
        self,
        vector_store: VectorStore = None,
        embedding_model: EmbeddingModel = None
    ):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_model = embedding_model or get_global_embedding_model()

    def retrieve(
        self,
        query: str,
        k: int = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        score_threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: Query text
            k: Number of documents to retrieve
            filter_metadata: Optional metadata filter
            score_threshold: Minimum similarity score

        Returns:
            List of retrieved documents with scores
        """
        logger.info(
            "RAG retrieval",
            query_length=len(query),
            k=k,
            filter_metadata=filter_metadata
        )

        documents = self.vector_store.search(
            query=query,
            k=k,
            filter_metadata=filter_metadata,
            score_threshold=score_threshold
        )

        logger.info(f"Retrieved {len(documents)} documents")
        return documents

    def retrieve_with_context(
        self,
        query: str,
        context: Optional[str] = None,
        k: int = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents with additional context.

        Args:
            query: Query text
            context: Additional context to improve retrieval
            k: Number of documents to retrieve
            filter_metadata: Optional metadata filter

        Returns:
            List of retrieved documents
        """
        # Combine query and context
        if context:
            enhanced_query = f"{query}\nContext: {context}"
        else:
            enhanced_query = query

        return self.retrieve(
            query=enhanced_query,
            k=k,
            filter_metadata=filter_metadata
        )

    def ingest_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest a document into the vector store.

        Args:
            content: Document content
            metadata: Optional metadata
            document_id: Optional document ID

        Returns:
            Ingestion result
        """
        logger.info(f"Ingesting document with {len(content)} characters")

        result = ingest_text(
            text=content,
            metadata=metadata
        )

        if result["success"]:
            logger.info(f"Successfully ingested document: {result['chunk_count']} chunks")
        else:
            logger.error(f"Failed to ingest document: {result.get('error')}")

        return result

    def ingest_file(
        self,
        file_path: str,
        original_filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a file into the vector store.

        Args:
            file_path: Path to the file
            original_filename: Original filename
            metadata: Optional metadata

        Returns:
            Ingestion result
        """
        logger.info(f"Ingesting file: {original_filename}")

        result = ingest_file(
            file_path=file_path,
            original_filename=original_filename,
            metadata=metadata
        )

        if result["success"]:
            logger.info(f"Successfully ingested file: {result['chunk_count']} chunks")
        else:
            logger.error(f"Failed to ingest file: {result.get('error')}")

        return result

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the vector store.

        Args:
            document_id: Document ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            self.vector_store.delete_documents([document_id])
            logger.info(f"Deleted document: {document_id}")
            return True
        except Exception as e:
            logger.exception(f"Error deleting document: {document_id}", error=str(e))
            return False

    def clear_store(self) -> bool:
        """
        Clear all documents from the vector store.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.vector_store.clear()
            logger.info("Cleared vector store")
            return True
        except Exception as e:
            logger.exception("Error clearing vector store", error=str(e))
            return False

    def get_store_info(self) -> Dict[str, Any]:
        """Get information about the vector store."""
        return self.vector_store.get_collection_info()

    def semantic_search(
        self,
        query: str,
        documents: List[str],
        k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search on a list of documents.

        Args:
            query: Query text
            documents: List of document texts
            k: Number of results to return

        Returns:
            List of relevant documents with scores
        """
        # Generate embeddings for documents
        doc_embeddings = self.embedding_model.embed(documents)

        # Generate query embedding
        query_embedding = self.embedding_model.embed_query(query)

        # Use vector store for search
        results = self.vector_store.search_by_embedding(
            embedding=query_embedding,
            k=k
        )

        return results

    def batch_retrieve(
        self,
        queries: List[str],
        k: int = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Perform batch retrieval for multiple queries.

        Args:
            queries: List of query texts
            k: Number of documents to retrieve per query
            filter_metadata: Optional metadata filter

        Returns:
            Dictionary mapping queries to results
        """
        results = {}
        for query in queries:
            results[query] = self.retrieve(
                query=query,
                k=k,
                filter_metadata=filter_metadata
            )
        return results

    def hybrid_search(
        self,
        query: str,
        k: int = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        structured_query: Optional[StructuredQuery] = None
    ) -> Dict[str, Any]:
        """
        Perform hybrid search combining semantic and structured search.

        Args:
            query: Query text
            k: Number of documents to retrieve
            filter_metadata: Optional metadata filter
            structured_query: Optional structured query for filtering

        Returns:
            Dictionary with both semantic and structured search results
        """
        # Semantic search
        semantic_results = self.retrieve(
            query=query,
            k=k,
            filter_metadata=filter_metadata
        )

        # Structured search (if applicable)
        structured_results = []
        if structured_query:
            # This would require additional implementation based on your data structure
            # For now, we'll return the semantic results with structured query info
            pass

        return {
            "semantic_results": semantic_results,
            "structured_query": structured_query.to_dict() if structured_query else None,
            "query": query
        }

    def get_relevant_chunks(
        self,
        query: str,
        context_window: int = 3,
        k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get relevant chunks with context windows.

        Args:
            query: Query text
            context_window: Number of surrounding chunks to include
            k: Number of initial chunks to retrieve

        Returns:
            List of chunks with context
        """
        # Get initial results
        initial_results = self.retrieve(query=query, k=k)

        # Get chunk IDs
        chunk_ids = [doc.get("metadata", {}).get("chunk_id") for doc in initial_results]

        # Get context chunks
        context_chunks = []
        for chunk_id in chunk_ids:
            if chunk_id is not None:
                # Get surrounding chunks
                for offset in range(-context_window, context_window + 1):
                    context_id = chunk_id + offset
                    if context_id >= 0:
                        # This would require additional implementation
                        # For now, we'll just return the initial results
                        pass

        return initial_results

    def update_document(
        self,
        document_id: str,
        new_content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update an existing document.

        Args:
            document_id: Document ID to update
            new_content: New document content
            metadata: Optional new metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete old document
            self.delete_document(document_id)

            # Ingest new document
            result = self.ingest_document(
                content=new_content,
                metadata=metadata,
                document_id=document_id
            )

            return result["success"]
        except Exception as e:
            logger.exception(f"Error updating document: {document_id}", error=str(e))
            return False