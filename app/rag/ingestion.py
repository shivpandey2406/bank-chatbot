"""
Ingestion Module
Handles document ingestion pipeline for RAG
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.chunking import get_chunker, ChunkingStrategy
from app.rag.embedding import get_embedding_model, EmbeddingModel
from app.rag.retrieval import VectorStore, get_vector_store
from app.utils.file_validator import FileValidator, ValidationResult

logger = get_logger(__name__)


class DocumentIngestor:
    """
    Handles the ingestion of documents into the RAG system.
    Supports CSV, Excel, and XML files.
    """

    def __init__(
        self,
        vector_store: VectorStore = None,
        embedding_model: EmbeddingModel = None,
        chunking_strategy: str = "fixed"
    ):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_model = embedding_model or get_embedding_model()
        self.chunking_strategy = chunking_strategy
        self.chunker = get_chunker(chunking_strategy)

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
            metadata: Optional metadata to attach to chunks

        Returns:
            Ingestion result with statistics
        """
        logger.info(f"Starting ingestion of {original_filename}")

        # Validate file
        validation = FileValidator.validate_file(file_path, original_filename)
        if not validation.is_valid:
            return {
                "success": False,
                "error": "; ".join(validation.errors),
                "warnings": validation.warnings
            }

        metadata = {
            **(metadata or {}),
            "source_file": original_filename,
            "file_type": validation.file_type,
        }

        # Read file based on type
        content = self._read_file(file_path, validation.file_type)
        if content is None:
            return {
                "success": False,
                "error": "File contains no data"
            }

        if validation.file_type == "xml":
            xml_payload = content
            if not xml_payload["text"].strip():
                return {
                    "success": False,
                    "error": "File contains no data"
                }
            chunks = self._process_xml(xml_payload, original_filename, metadata)
            row_count = xml_payload["row_count"]
            column_count = len(xml_payload["columns"])
        else:
            df = content
            if df.empty:
                return {
                    "success": False,
                    "error": "File contains no data"
                }
            chunks = self._process_dataframe(df, metadata)
            row_count = len(df)
            column_count = len(df.columns)

        # Generate embeddings and store
        document_ids = self._store_chunks(chunks)

        result = {
            "success": True,
            "file_type": validation.file_type,
            "row_count": row_count,
            "column_count": column_count,
            "columns": validation.columns,
            "chunk_count": len(chunks),
            "document_ids": document_ids,
            "sample_data": validation.sample_data,
            "warnings": validation.warnings
        }

        logger.info(f"Successfully ingested {original_filename}: {len(chunks)} chunks created")
        return result

    def _read_file(self, file_path: str, file_type: str):
        """Read file based on type."""
        try:
            if file_type == "csv":
                return pd.read_csv(file_path)
            elif file_type in ["xlsx", "xls"]:
                return pd.read_excel(file_path)
            elif file_type == "xml":
                return self._read_xml(file_path)
            else:
                logger.error(f"Unsupported file type: {file_type}")
                return None
        except Exception as e:
            logger.exception(f"Error reading file: {file_path}", error=str(e))
            return None

    def _read_xml(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Read XML and convert it into rich text plus row-like structures."""
        tree = ET.parse(file_path)
        root = tree.getroot()

        row_elements = self._find_repeated_record_elements(root)
        rows = [self._xml_element_to_record(element) for element in row_elements]
        rows = [row for row in rows if row]
        columns = sorted({key for row in rows for key in row.keys()})

        summary_lines = [
            f"XML document name: {Path(file_path).name}",
            f"Root tag: {root.tag}",
            f"Detected records: {len(rows)}",
        ]
        if columns:
            summary_lines.append(f"Detected fields: {', '.join(columns)}")

        record_sections = []
        for idx, row in enumerate(rows):
            pairs = [f"{key}: {value}" for key, value in row.items() if value not in (None, "")]
            if pairs:
                record_sections.append(f"Record {idx + 1}\n" + "\n".join(pairs))

        xml_text = "\n\n".join(summary_lines + record_sections)
        if not record_sections:
            xml_text = self._xml_tree_to_text(root)

        return {
            "text": xml_text,
            "rows": rows,
            "columns": columns,
            "row_count": len(rows)
        }

    def _find_repeated_record_elements(self, root: ET.Element) -> List[ET.Element]:
        """Find repeated child elements that likely represent records."""
        parent_map: Dict[ET.Element, Dict[str, int]] = {}
        for parent in root.iter():
            counts: Dict[str, int] = {}
            for child in list(parent):
                counts[child.tag] = counts.get(child.tag, 0) + 1
            if counts:
                parent_map[parent] = counts

        candidate_parent = None
        candidate_tag = None
        candidate_count = 0
        for parent, counts in parent_map.items():
            for tag, count in counts.items():
                if count > candidate_count and count > 1:
                    candidate_parent = parent
                    candidate_tag = tag
                    candidate_count = count

        if candidate_parent is None or candidate_tag is None:
            return []

        return [child for child in list(candidate_parent) if child.tag == candidate_tag]

    def _xml_element_to_record(self, element: ET.Element) -> Dict[str, Any]:
        """Flatten one XML element into a searchable record dict."""
        record: Dict[str, Any] = {}
        for key, value in element.attrib.items():
            record[f"@{key}"] = value

        for child in list(element):
            if list(child):
                nested = self._flatten_xml(child, prefix=child.tag)
                record.update(nested)
                continue

            text = (child.text or "").strip()
            if text:
                record[child.tag] = text
            for key, value in child.attrib.items():
                record[f"{child.tag}.@{key}"] = value

        return record

    def _flatten_xml(self, element: ET.Element, prefix: str = "") -> Dict[str, Any]:
        """Flatten nested XML nodes into dotted key paths."""
        data: Dict[str, Any] = {}
        current_prefix = prefix or element.tag

        text = (element.text or "").strip()
        if text:
            data[current_prefix] = text

        for key, value in element.attrib.items():
            data[f"{current_prefix}.@{key}"] = value

        for child in list(element):
            child_prefix = f"{current_prefix}.{child.tag}"
            data.update(self._flatten_xml(child, child_prefix))

        return data

    def _xml_tree_to_text(self, root: ET.Element) -> str:
        """Render XML into readable text when row extraction is not available."""
        lines: List[str] = [f"XML root: {root.tag}"]
        for element in root.iter():
            text = (element.text or "").strip()
            attrs = ", ".join(f"{k}={v}" for k, v in element.attrib.items())
            if text or attrs:
                prefix = element.tag
                if attrs:
                    lines.append(f"{prefix} [{attrs}]")
                if text:
                    lines.append(f"{prefix}: {text}")
        return "\n".join(lines)

    def _process_dataframe(
        self,
        df: pd.DataFrame,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Process a DataFrame into text chunks.

        Args:
            df: Pandas DataFrame
            metadata: Optional metadata

        Returns:
            List of chunk dictionaries
        """
        metadata = metadata or {}
        chunks = []

        # Add column information to metadata
        metadata["columns"] = list(df.columns)
        metadata["row_count"] = len(df)

        # Strategy 1: Convert each row to a text description
        for idx, row in df.iterrows():
            row_text = self._row_to_text(row, df.columns)
            row_metadata = {**metadata, "row_index": idx}

            # Chunk the row text
            row_chunks = self.chunker.chunk(row_text, row_metadata)
            chunks.extend(row_chunks)

        # Strategy 2: Create summary chunks for the entire dataset
        summary_text = self._create_summary(df)
        summary_metadata = {**metadata, "chunk_type": "summary"}
        summary_chunks = self.chunker.chunk(summary_text, summary_metadata)
        chunks.extend(summary_chunks)

        # Strategy 3: Create column-level chunks for schema understanding
        for col in df.columns:
            col_text = self._column_to_text(col, df[col])
            col_metadata = {**metadata, "column": col, "chunk_type": "column_schema"}
            col_chunks = self.chunker.chunk(col_text, col_metadata)
            chunks.extend(col_chunks)

        return chunks

    def _process_xml(
        self,
        xml_payload: Dict[str, Any],
        original_filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Process XML content into searchable chunks."""
        metadata = metadata or {}
        base_metadata = {
            **metadata,
            "source_file": original_filename,
            "file_type": "xml",
            "columns": xml_payload["columns"],
            "row_count": xml_payload["row_count"],
        }

        chunks: List[Dict[str, Any]] = []
        text_chunks = self.chunker.chunk(
            xml_payload["text"],
            {**base_metadata, "chunk_type": "xml_document"}
        )
        chunks.extend(text_chunks)

        for idx, row in enumerate(xml_payload["rows"]):
            row_text = "\n".join(f"{key}: {value}" for key, value in row.items())
            row_chunks = self.chunker.chunk(
                row_text,
                {**base_metadata, "row_index": idx, "chunk_type": "xml_record"}
            )
            chunks.extend(row_chunks)

        return chunks

    def _row_to_text(self, row: pd.Series, columns: pd.Index) -> str:
        """Convert a DataFrame row to text description."""
        parts = []
        for col in columns:
            value = row[col]
            if pd.notna(value):
                parts.append(f"{col}: {value}")
        return " | ".join(parts)

    def _create_summary(self, df: pd.DataFrame) -> str:
        """Create a summary text for the entire DataFrame."""
        summary_parts = [
            f"Dataset Summary",
            f"Total rows: {len(df)}",
            f"Total columns: {len(df.columns)}",
            f"Columns: {', '.join(df.columns)}",
            "",
            "Column Statistics:"
        ]

        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                summary_parts.append(
                    f"- {col}: min={df[col].min()}, max={df[col].max()}, "
                    f"mean={df[col].mean():.2f}, sum={df[col].sum():.2f}"
                )
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                summary_parts.append(
                    f"- {col}: earliest={df[col].min()}, latest={df[col].max()}"
                )
            else:
                unique_count = df[col].nunique()
                summary_parts.append(
                    f"- {col}: {unique_count} unique values, "
                    f"top values: {df[col].value_counts().head(3).to_dict()}"
                )

        return "\n".join(summary_parts)

    def _column_to_text(self, col_name: str, column: pd.Series) -> str:
        """Create text description for a column."""
        parts = [
            f"Column: {col_name}",
            f"Data type: {column.dtype}",
            f"Non-null values: {column.notna().sum()}",
            f"Null values: {column.isna().sum()}"
        ]

        if pd.api.types.is_numeric_dtype(column):
            parts.extend([
                f"Min: {column.min()}",
                f"Max: {column.max()}",
                f"Mean: {column.mean():.2f}",
                f"Median: {column.median()}",
                f"Std Dev: {column.std():.2f}"
            ])
        else:
            top_values = column.value_counts().head(5)
            parts.append(f"Top values: {top_values.to_dict()}")

        return "\n".join(parts)

    def _store_chunks(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Store chunks in the vector store.

        Args:
            chunks: List of chunk dictionaries

        Returns:
            List of document IDs
        """
        if not chunks:
            return []

        documents = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]

        # Generate embeddings
        embeddings = self.embedding_model.embed(documents)

        # Store in vector store
        document_ids = self.vector_store.add_documents(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        return document_ids

    def ingest_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = None
    ) -> Dict[str, Any]:
        """
        Ingest raw text into the vector store.

        Args:
            text: Text content to ingest
            metadata: Optional metadata
            chunk_size: Optional custom chunk size

        Returns:
            Ingestion result
        """
        if not text:
            return {"success": False, "error": "No text provided"}

        # Chunk the text
        chunker = get_chunker(self.chunking_strategy)
        if chunk_size:
            chunker.chunk_size = chunk_size

        chunks = chunker.chunk(text, metadata)

        # Store chunks
        document_ids = self._store_chunks(chunks)

        return {
            "success": True,
            "chunk_count": len(chunks),
            "document_ids": document_ids,
            "text_length": len(text)
        }


class IngestionPipeline:
    """
    Pipeline for batch ingestion of multiple files.
    """

    def __init__(self, ingestor: DocumentIngestor = None):
        self.ingestor = ingestor or DocumentIngestor()

    def run(
        self,
        file_paths: List[Tuple[str, str]],
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Run ingestion pipeline on multiple files.

        Args:
            file_paths: List of (file_path, original_filename) tuples
            batch_size: Number of files to process in each batch

        Returns:
            List of ingestion results
        """
        results = []

        for i in range(0, len(file_paths), batch_size):
            batch = file_paths[i:i + batch_size]
            for file_path, original_filename in batch:
                try:
                    result = self.ingestor.ingest_file(file_path, original_filename)
                    results.append(result)
                except Exception as e:
                    logger.exception(
                        f"Error ingesting {original_filename}",
                        error=str(e)
                    )
                    results.append({
                        "success": False,
                        "error": str(e),
                        "filename": original_filename
                    })

        return results


def ingest_file(
    file_path: str,
    original_filename: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to ingest a single file.

    Args:
        file_path: Path to the file
        original_filename: Original filename
        metadata: Optional metadata

    Returns:
        Ingestion result
    """
    ingestor = DocumentIngestor()
    return ingestor.ingest_file(file_path, original_filename, metadata)


def ingest_text(
    text: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to ingest raw text.

    Args:
        text: Text content to ingest
        metadata: Optional metadata

    Returns:
        Ingestion result
    """
    ingestor = DocumentIngestor()
    return ingestor.ingest_text(text, metadata)
