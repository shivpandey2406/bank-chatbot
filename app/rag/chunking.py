"""
Chunking Module
Handles document chunking strategies for RAG pipeline
"""

import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import pandas as pd

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChunkingStrategy(ABC):
    """Abstract base class for chunking strategies."""

    @abstractmethod
    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Chunk text into smaller pieces.

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of chunk dictionaries with 'text' and 'metadata' keys
        """
        pass


class FixedSizeChunking(ChunkingStrategy):
    """
    Fixed-size chunking with overlap.
    Splits text into chunks of fixed size with configurable overlap.
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Split text into fixed-size chunks with overlap."""
        if not text:
            return []

        metadata = metadata or {}
        chunks = []
        start = 0
        chunk_id = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_break = max(
                    chunk_text.rfind(". "),
                    chunk_text.rfind("! "),
                    chunk_text.rfind("? "),
                    chunk_text.rfind("\n")
                )
                if last_break > self.chunk_size * 0.5:
                    chunk_text = chunk_text[: last_break + 1]
                    end = start + last_break + 1

            chunk = {
                "text": chunk_text.strip(),
                "metadata": {
                    **metadata,
                    "chunk_id": chunk_id,
                    "start_char": start,
                    "end_char": end,
                    "chunk_size": len(chunk_text)
                }
            }
            chunks.append(chunk)
            chunk_id += 1

            start = end - self.chunk_overlap
            if start <= 0:
                start = end

        return chunks


class SemanticChunking(ChunkingStrategy):
    """
    Semantic chunking based on content structure.
    Splits text at natural boundaries like paragraphs and sections.
    """

    def __init__(self, min_chunk_size: int = 100):
        self.min_chunk_size = min_chunk_size

    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Split text at semantic boundaries."""
        if not text:
            return []

        metadata = metadata or {}

        # Split by paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        current_chunk = ""
        chunk_id = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) > settings.chunk_size and current_chunk:
                # Save current chunk and start new one
                chunks.append({
                    "text": current_chunk.strip(),
                    "metadata": {
                        **metadata,
                        "chunk_id": chunk_id,
                        "chunk_size": len(current_chunk)
                    }
                })
                chunk_id += 1
                current_chunk = para
            else:
                current_chunk += "\n" + para if current_chunk else para

        # Add remaining chunk
        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "metadata": {
                    **metadata,
                    "chunk_id": chunk_id,
                    "chunk_size": len(current_chunk)
                }
            })

        return chunks


class DataFrameChunking(ChunkingStrategy):
    """
    Chunking strategy for structured data (DataFrames).
    Converts rows to text chunks for RAG.
    """

    def __init__(
        self,
        rows_per_chunk: int = 1,
        include_headers: bool = True
    ):
        self.rows_per_chunk = rows_per_chunk
        self.include_headers = include_headers

    def chunk(self, df: pd.DataFrame, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Convert DataFrame rows to text chunks."""
        if df.empty:
            return []

        metadata = metadata or {}
        chunks = []
        chunk_id = 0

        for i in range(0, len(df), self.rows_per_chunk):
            chunk_df = df.iloc[i:i + self.rows_per_chunk]
            chunk_text = chunk_df.to_string(header=self.include_headers, index=False)

            chunks.append({
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "chunk_id": chunk_id,
                    "row_start": i,
                    "row_end": i + len(chunk_df),
                    "chunk_type": "tabular"
                }
            })
            chunk_id += 1

        return chunks


def get_chunker(strategy: str = "fixed", **kwargs) -> ChunkingStrategy:
    """
    Factory function to get a chunking strategy.

    Args:
        strategy: Chunking strategy name (fixed, semantic, dataframe)
        **kwargs: Additional arguments for the chunker

    Returns:
        ChunkingStrategy instance
    """
    strategies = {
        "fixed": FixedSizeChunking,
        "semantic": SemanticChunking,
        "dataframe": DataFrameChunking,
    }

    chunker_class = strategies.get(strategy, FixedSizeChunking)
    return chunker_class(**kwargs)