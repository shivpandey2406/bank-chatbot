"""
Application Configuration Module
Centralized configuration management using Pydantic Settings
"""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """
    Main application settings class.
    Loads configuration from environment variables and .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        Prefer the project's .env file over host-level environment variables.
        This keeps local app configuration deterministic during development.
        """
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    # Application Configuration
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    app_name: str = "Banking RAG Chatbot"
    app_version: str = "1.0.0"
    description: str = "Production-grade Banking RAG Chatbot System"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:8501"
    api_prefix: str = "/api/v1"

    # CORS Configuration
    cors_origins: List[str] = [
        "http://localhost:8501",
        "http://localhost:3000",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:3000"
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]

    # Database Configuration
    database_url: str = "sqlite:///./banking_chatbot.db"
    vector_db_path: str = "./vectorstore/chroma"

    # LLM Configuration
    llm_provider: str = "auto"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    embedding_model: str = "text-embedding-3-small"
    llm_temperature: float = 0.1
    max_tokens: int = 2000

    # OAuth Configuration
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/api/oauth/google/callback"
    slack_client_id: Optional[str] = None
    slack_client_secret: Optional[str] = None
    slack_redirect_uri: str = "http://localhost:8000/api/oauth/slack/callback"

    # MCP Configuration
    mcp_server_url: Optional[str] = None
    mcp_api_key: Optional[str] = None

    # File Upload Configuration
    max_file_size: int = 50_000_000  # 50MB
    allowed_extensions: List[str] = ["csv", "xlsx", "xls", "xml"]
    upload_dir: str = "./data/uploads"
    processed_dir: str = "./data/processed"

    # Security Configuration
    secret_key: str = "your_secret_key_here_change_in_production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Redis Configuration (for Celery)
    redis_url: str = "redis://localhost:6379/0"

    # Email Configuration
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None

    # Slack Configuration
    slack_bot_token: Optional[str] = None
    slack_channel_id: Optional[str] = None

    # RAG Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_top_k: int = 5
    similarity_threshold: float = 0.5

    # Agent Configuration
    agent_timeout: int = 60
    max_agent_iterations: int = 10

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"

    @property
    def resolved_llm_provider(self) -> str:
        """Resolve the active LLM provider from config and API key format."""
        provider = (self.llm_provider or "auto").strip().lower()
        if provider in {"openai", "groq"}:
            return provider

        api_key = (self.groq_api_key or self.openai_api_key or "").strip()
        if api_key.startswith("gsk_"):
            return "groq"
        return "openai"

    @property
    def llm_api_key(self) -> Optional[str]:
        """Return the active provider API key."""
        if self.resolved_llm_provider == "groq":
            return self.groq_api_key or self.openai_api_key
        return self.openai_api_key

    @property
    def llm_base_url(self) -> Optional[str]:
        """Return the active provider base URL when needed."""
        if self.resolved_llm_provider == "groq":
            return self.groq_base_url
        return self.openai_base_url

    @property
    def llm_model(self) -> str:
        """Return the configured model for the active provider."""
        if self.resolved_llm_provider == "groq":
            configured_model = (self.groq_model or "").strip()
            if configured_model:
                return configured_model

            openai_model = (self.openai_model or "").strip()
            if openai_model and not openai_model.startswith("gpt-"):
                return openai_model
            return "llama-3.1-8b-instant"

        return self.openai_model


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Global settings instance for easy access
settings = get_settings()
