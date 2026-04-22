"""
Token Model
Represents authentication tokens in the system
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Token(Base):
    """
    Token model for storing authentication tokens.
    """

    __tablename__ = "tokens"

    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Token fields
    token = Column(String(500), unique=True, nullable=False, index=True)
    token_type = Column(String(50), nullable=False)  # access, refresh, api_key

    # Token status
    is_active = Column(Boolean, default=True, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    # Token metadata
    expires_at = Column(DateTime, nullable=True)
    created_at_ip = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)

    # OAuth refresh tokens
    oauth_provider = Column(String(50), nullable=True)
    oauth_refresh_token = Column(String(500), nullable=True)
    oauth_access_token = Column(String(500), nullable=True)

    # Relationships
    user = relationship("User", back_populates="tokens")

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (active, not revoked, not expired)."""
        return self.is_active and not self.is_revoked and not self.is_expired

    def revoke(self) -> None:
        """Revoke this token."""
        self.is_revoked = True
        self.is_active = False

    def __repr__(self) -> str:
        return f"<Token(id={self.id}, type={self.token_type}, user_id={self.user_id})>"