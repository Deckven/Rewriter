"""Application configuration — merges .env, env vars, and CLI args."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REWRITER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    anthropic_api_key: str = Field(
        default="",
        alias="ANTHROPIC_API_KEY",
        description="Anthropic API key",
    )

    # Model settings
    model: str = "claude-sonnet-4-20250514"
    analysis_model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.7

    # Paths
    data_dir: Path = _PROJECT_ROOT / "data"

    # Import
    min_words: int = 50

    # Analysis
    sample_fraction: float = 0.18
    chunk_max_tokens: int = 90_000
    chunk_articles: int = 12
    n_clusters: int = 25

    # Rewrite
    intensity: Literal["light", "medium", "full"] = "medium"
    n_examples: int = 3
    preserve_structure: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "corpus.db"

    @property
    def style_guide_md_path(self) -> Path:
        return self.data_dir / "style_guide.md"

    @property
    def style_guide_json_path(self) -> Path:
        return self.data_dir / "style_guide.json"

    @property
    def tfidf_model_path(self) -> Path:
        return self.data_dir / "tfidf_model.pkl"

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


def get_settings(**overrides: object) -> Settings:
    """Create settings with optional CLI overrides."""
    return Settings(**overrides)  # type: ignore[arg-type]
