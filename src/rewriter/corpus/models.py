"""Pydantic models for corpus data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Article(BaseModel):
    """A single blog article."""

    id: int | None = None
    wp_id: int = 0
    title: str = ""
    slug: str = ""
    content: str = ""  # cleaned plaintext (markdown-like)
    raw_html: str = ""
    excerpt: str = ""
    published_at: datetime | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    word_count: int = 0
    status: str = "publish"  # publish, draft, etc.

    def compute_word_count(self) -> int:
        self.word_count = len(self.content.split())
        return self.word_count


class ChunkAnalysis(BaseModel):
    """Analysis result for a chunk of articles."""

    chunk_id: int = 0
    article_ids: list[int] = Field(default_factory=list)
    analysis_text: str = ""
    token_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


class StyleGuide(BaseModel):
    """Synthesized style guide."""

    version: int = 1
    markdown: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)
    sample_size: int = 0
    n_chunks: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


class FewShotExample(BaseModel):
    """A selected few-shot example article."""

    article_id: int
    cluster_id: int = -1
    distance_to_centroid: float = 0.0


class CorpusStats(BaseModel):
    """Summary statistics for the corpus."""

    total_articles: int = 0
    total_words: int = 0
    avg_words: float = 0.0
    min_words: int = 0
    max_words: int = 0
    categories: dict[str, int] = Field(default_factory=dict)
    date_range: tuple[str, str] | None = None
    n_examples: int = 0
    has_style_guide: bool = False
