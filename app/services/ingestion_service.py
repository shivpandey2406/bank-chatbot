"""
Ingestion Service
High-level file ingestion orchestration.
"""

import os
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.rag.ingestion import DocumentIngestor

logger = get_logger(__name__)


class IngestionService:
    """Orchestrates file ingestion into the RAG pipeline."""

    def __init__(self):
        self.ingestor = DocumentIngestor()

    def ingest(self, file_path: str, filename: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"IngestionService: ingesting {filename}")
        return self.ingestor.ingest_file(file_path, filename, metadata)

    def ingest_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.ingestor.ingest_text(text, metadata)

    def list_ingested_files(self) -> list:
        upload_dir = os.path.join(settings.upload_dir, "raw")
        if not os.path.exists(upload_dir):
            return []
        return [f for f in os.listdir(upload_dir) if f.endswith((".csv", ".xlsx", ".xls"))]
