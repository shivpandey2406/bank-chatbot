"""
Embedding Module
Handles text embedding generation for RAG pipeline
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Union
import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingModel(ABC):
    """Abstract base class for embedding models."""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a query text.

        Args:
            text: Query text to embed

        Returns:
            Embedding vector
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimension of the embedding vectors."""
        pass


class SentenceTransformerEmbeddings(EmbeddingModel):
    """
    Embedding model using SentenceTransformers.
    Uses local models for embedding generation.
    """

    def __init__(self, model_name: str = None):
        self.model_name = model_name or "all-MiniLM-L6-v2"
        self._model = None
        self._dim = None

    @property
    def model(self):
        """Lazy load the model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dimension(self) -> int:
        """Return the dimension of the embedding vectors."""
        if self._dim is None:
            # Get dimension from model
            sample = self.model.encode(["test"])
            self._dim = len(sample[0])
        return self._dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for documents."""
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a query."""
        return self.embed([text])[0]


class OpenAIEmbeddings(EmbeddingModel):
    """
    Embedding model using OpenAI API.
    Uses OpenAI's embedding models.
    """

    def __init__(self, model_name: str = None, api_key: str = None):
        self.model_name = model_name or settings.embedding_model
        self.api_key = api_key or settings.openai_api_key
        self._client = None
        self._dim = None

        if not self.api_key:
            raise ValueError("OpenAI API key is required")

    @property
    def client(self):
        """Lazy load the OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    @property
    def dimension(self) -> int:
        """Return the dimension of the embedding vectors."""
        # OpenAI text-embedding-3-small returns 1536 dimensions
        return 1536

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for documents."""
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.model_name,
            input=texts
        )

        # Sort by index to maintain order
        embeddings = sorted(response.data, key=lambda x: x.index)
        return [emb.embedding for emb in embeddings]

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a query."""
        return self.embed([text])[0]


class MockEmbeddings(EmbeddingModel):
    """
    Mock embedding model for testing.
    Generates random embeddings.
    """

    def __init__(self, dimension: int = 384):
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate random embeddings."""
        return np.random.rand(len(texts), self._dim).tolist()

    def embed_query(self, text: str) -> List[float]:
        """Generate random embedding for query."""
        return np.random.rand(self._dim).tolist()


def get_embedding_model(
    provider: str = None,
    model_name: str = None,
    api_key: str = None
) -> EmbeddingModel:
    """
    Factory function to get an embedding model.

    Args:
        provider: Embedding provider (sentencetransformer, openai, mock)
        model_name: Model name
        api_key: API key for OpenAI

    Returns:
        EmbeddingModel instance
    """
    provider = provider or "sentencetransformer"

    if provider == "openai":
        return OpenAIEmbeddings(model_name=model_name, api_key=api_key)
    elif provider == "mock":
        return MockEmbeddings()
    else:
        return SentenceTransformerEmbeddings(model_name=model_name)


# Global embedding model instance
_embedding_model: Optional[EmbeddingModel] = None


def get_global_embedding_model() -> EmbeddingModel:
    """
    Get or create the global embedding model instance.
    Uses settings to determine which model to use.
    """
    global _embedding_model

    if _embedding_model is None:
        # Use remote embeddings only for actual OpenAI credentials.
        # Groq-backed chat still works, but embeddings fall back to the local model.
        if (
            settings.resolved_llm_provider == "openai"
            and settings.openai_api_key
            and settings.openai_api_key != "your_openai_api_key_here"
        ):
            _embedding_model = get_embedding_model("openai")
        else:
            _embedding_model = get_embedding_model("sentencetransformer")

    return _embedding_model


async def initialize_global_embedding_model():
    """Initialize the global embedding model during app startup."""
    get_global_embedding_model()
