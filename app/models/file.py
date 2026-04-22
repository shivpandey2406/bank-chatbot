"""
File Model
Represents uploaded files in the system
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, String, Integer, Boolean, Float, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class File(Base):
    """
    File model for storing uploaded file metadata and processing status.
    """

    __tablename__ = "files"

    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # File identification
    file_uuid = Column(String(36), unique=True, nullable=False, index=True)
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False)

    # File properties
    file_type = Column(String(50), nullable=False)  # csv, xlsx, xls
    file_size = Column(Integer, nullable=False)  # in bytes
    mime_type = Column(String(100), nullable=True)

    # File content metadata
    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    columns = Column(JSON, nullable=True)  # List of column names
    sample_data = Column(JSON, nullable=True)  # First few rows for preview

    # Processing status
    status = Column(
        String(50),
        default="pending",
        nullable=False
    )  # pending, processing, completed, failed, ingested

    # RAG processing
    chunk_count = Column(Integer, nullable=True)
    vector_collection_id = Column(String(100), nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    processing_log = Column(JSON, nullable=True)

    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True, default=list)
    metadata_ = Column(JSON, nullable=True, default=dict)

    # Relationships
    user = relationship("User", back_populates="files")

    @property
    def is_processed(self) -> bool:
        """Check if file has been processed."""
        return self.status in ["completed", "ingested"]

    @property
    def is_ready_for_query(self) -> bool:
        """Check if file is ready for RAG queries."""
        return self.status == "ingested"

    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return round(self.file_size / (1024 * 1024), 2)

    def to_dict(self) -> dict:
        """Convert file to dictionary representation."""
        return {
            "id": self.id,
            "file_uuid": self.file_uuid,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "file_size_mb": self.file_size_mb,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": self.columns,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<File(id={self.id}, filename={self.original_filename}, status={self.status})>"