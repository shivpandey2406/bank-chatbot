"""
Log Models
Chat logs and audit logs for the system
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, JSON, Text, Boolean
from sqlalchemy.orm import relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ChatLog(Base):
    """
    ChatLog model for storing chat conversation history.
    """

    __tablename__ = "chat_logs"

    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Session tracking
    session_id = Column(String(36), nullable=True, index=True)
    conversation_id = Column(String(36), nullable=True, index=True)

    # Message content
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)

    # Query context
    query_type = Column(String(50), nullable=True)  # rag, aggregation, tool, general
    source = Column(String(100), nullable=True)  # web, api, streamlit

    # RAG context
    retrieved_documents = Column(JSON, nullable=True)
    retrieval_scores = Column(JSON, nullable=True)
    context_used = Column(Text, nullable=True)

    # Aggregation context
    aggregation_query = Column(JSON, nullable=True)
    aggregation_result = Column(JSON, nullable=True)

    # Tool usage
    tools_used = Column(JSON, nullable=True)
    tool_results = Column(JSON, nullable=True)

    # Performance metrics
    response_time_ms = Column(Float, nullable=True)
    token_count = Column(Integer, nullable=True)
    model_used = Column(String(100), nullable=True)

    # Feedback
    feedback_score = Column(Integer, nullable=True)  # 1-5 rating
    feedback_text = Column(Text, nullable=True)

    # Metadata
    metadata_ = Column(JSON, nullable=True, default=dict)

    # Relationships
    user = relationship("User", back_populates="chat_logs")

    @property
    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == "user"

    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == "assistant"

    def to_dict(self) -> dict:
        """Convert chat log to dictionary representation."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "query_type": self.query_type,
            "source": self.source,
            "response_time_ms": self.response_time_ms,
            "token_count": self.token_count,
            "model_used": self.model_used,
            "feedback_score": self.feedback_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ChatLog(id={self.id}, role={self.role}, user_id={self.user_id})>"


class AuditLog(Base):
    """
    AuditLog model for tracking system events and user actions.
    """

    __tablename__ = "audit_logs"

    # Actor information
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_email = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)

    # Event information
    event_type = Column(String(100), nullable=False, index=True)  # login, upload, query, etc.
    event_category = Column(String(50), nullable=True)  # auth, file, chat, system

    # Action details
    action = Column(String(200), nullable=False)
    resource_type = Column(String(100), nullable=True)  # user, file, chat, etc.
    resource_id = Column(String(100), nullable=True)

    # Request/Response details
    request_method = Column(String(10), nullable=True)
    request_path = Column(String(500), nullable=True)
    request_body = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=True)
    response_body = Column(JSON, nullable=True)

    # Additional context
    details = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Severity level
    severity = Column(String(20), default="info")  # debug, info, warning, error, critical

    @property
    def is_error(self) -> bool:
        """Check if this is an error event."""
        return self.severity in ["error", "critical"]

    def to_dict(self) -> dict:
        """Convert audit log to dictionary representation."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "event_type": self.event_type,
            "event_category": self.event_category,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "request_method": self.request_method,
            "request_path": self.request_path,
            "response_status": self.response_status,
            "severity": self.severity,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, event_type={self.event_type}, action={self.action})>"