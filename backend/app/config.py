import os
from typing import List

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    # Project info
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "AGI Judd's Idea Catalog")
    VERSION: str = os.getenv("VERSION", "1.0.0")

    # API settings
    API_TITLE: str = os.getenv("API_TITLE", f"{PROJECT_NAME} API")

    # CORS settings
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]
    CORS_CREDENTIALS: bool = os.getenv("CORS_CREDENTIALS", "true").lower() == "true"
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]

    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    RELOAD: bool = os.getenv("RELOAD", "true").lower() == "true"

    # Production settings
    RAILWAY_ENVIRONMENT_NAME: str = os.getenv("RAILWAY_ENVIRONMENT_NAME", "development")

    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Anthropic settings
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # xAI/Grok settings
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")

    # Linear settings
    LINEAR_ACCESS_KEY: str = os.getenv("LINEAR_ACCESS_KEY", "")

    # Mem0 Memory Search settings
    MEM0_API_URL: str = os.getenv("MEM0_API_URL", "")
    MEM0_USER_ID: str = os.getenv("MEM0_USER_ID", "")

    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Project constraints
    MAX_PROJECT_TITLE_LENGTH: int = 80

    # LLM generation constraints
    PROJECT_DRAFT_MAX_COMPLETION_TOKENS: int = int(
        os.getenv("PROJECT_DRAFT_MAX_COMPLETION_TOKENS", "2048")
    )

    # Database settings (PostgreSQL only)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "ae_scientist")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")

    # Google OAuth settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "")

    # Authentication settings
    SESSION_EXPIRE_HOURS: int = int(os.getenv("SESSION_EXPIRE_HOURS", "24"))

    # Frontend URL for redirects
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    @property
    def is_production(self) -> bool:
        return self.RAILWAY_ENVIRONMENT_NAME == "production"


# Create settings instance
settings = Settings()
