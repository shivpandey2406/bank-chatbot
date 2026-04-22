"""
User Model
Represents a user in the system
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.logs import ChatLog


class User(Base):
    """
    User model for storing user account information.
    """

    __tablename__ = "users"

    # Unique identifier (UUID or email-based)
    user_id = Column(String(36), unique=True, nullable=False, index=True)

    # Authentication fields
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # Profile fields
    full_name = Column(String(255), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # OAuth fields
    oauth_provider = Column(String(50), nullable=True)  # google, slack, etc.
    oauth_id = Column(String(255), nullable=True)

    # Metadata
    metadata_ = Column(JSON, nullable=True, default=dict)
    last_login = Column(DateTime, nullable=True)
    login_count = Column(Integer, default=0, nullable=False)

    # Relationships
    files = relationship("File", back_populates="user", cascade="all, delete-orphan")
    chat_logs = relationship("ChatLog", back_populates="user", cascade="all, delete-orphan")
    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")

    def __init__(
        self,
        email: str,
        hashed_password: str,
        user_id: Optional[str] = None,
        full_name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_active: bool = True,
        is_verified: bool = False,
        is_superuser: bool = False,
        oauth_provider: Optional[str] = None,
        oauth_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.email = email
        self.hashed_password = hashed_password
        self.user_id = user_id or f"user_{datetime.utcnow().timestamp()}"
        self.full_name = full_name
        self.first_name = first_name
        self.last_name = last_name
        self.is_active = is_active
        self.is_verified = is_verified
        self.is_superuser = is_superuser
        self.oauth_provider = oauth_provider
        self.oauth_id = oauth_id

    @property
    def display_name(self) -> str:
        """Get user's display name."""
        if self.full_name:
            return self.full_name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email.split("@")[0]

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert user to dictionary representation."""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "email": self.email,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "oauth_provider": self.oauth_provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        if include_sensitive:
            data["metadata"] = self.metadata_
        return data

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"