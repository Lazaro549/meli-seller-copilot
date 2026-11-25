"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Mercado Libre
    meli_client_id: str = Field(default="", description="Application Client ID")
    meli_client_secret: str = Field(default="", description="Application Client Secret")
    meli_redirect_uri: str = Field(
        default="http://localhost:8000/auth/callback",
        description="OAuth redirect URI registered in DevCenter",
    )
    meli_access_token: str = Field(default="", description="Current access token (optional)")
    meli_refresh_token: str = Field(default="", description="Current refresh token (optional)")
    meli_site_id: Literal["MLA", "MLB", "MLM", "MLC", "MCO", "MLU", "MPE"] = Field(
        default="MLA",
        description="Default site (Argentina = MLA)",
    )

    # LLM provider: anthropic | openai | groq | mock
    llm_provider: Literal["anthropic", "openai", "groq", "mock"] = Field(
        default="anthropic",
        description="Which LLM backend to use. 'mock' skips the LLM and builds a template report.",
    )

    # Anthropic / Claude
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use for agents",
    )

    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model",
    )

    # Groq (OpenAI-compatible)
    groq_api_key: str = Field(default="", description="Groq API key")
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model",
    )
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Groq OpenAI-compatible base URL",
    )

    # App
    app_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
