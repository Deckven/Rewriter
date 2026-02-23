"""Stratified sampling from corpus — balanced by category and time."""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime
from typing import Callable

from rewriter.config import Settings
from rewriter.corpus.models import Article


def stratified_sample(
    articles: list[Article],
    settings: Settings,
    *,
    seed: int = 42,
) -> list[Article]:
    """Select a stratified sample of articles.

    Balances by category and publication date. Aims for ~18% of corpus
    (configurable via settings.sample_fraction), typically 250-320 articles.

    Args:
        articles: All articles in corpus.
        settings: App settings.
        seed: Random seed for reproducibility.

    Returns:
        Sampled articles list.
    """
    rng = random.Random(seed)
    target_n = max(10, int(len(articles) * settings.sample_fraction))

    # Group by primary category
    by_category: dict[str, list[Article]] = defaultdict(list)
    for a in articles:
        cat = a.categories[0] if a.categories else "_uncategorized"
        by_category[cat].append(a)

    # Sort each group by date
    _epoch = datetime(1970, 1, 1)
    for cat in by_category:
        by_category[cat].sort(key=lambda a: a.published_at or _epoch)

    # Proportional allocation per category
    selected: list[Article] = []
    for cat, cat_articles in by_category.items():
        cat_n = max(1, round(target_n * len(cat_articles) / len(articles)))
        cat_n = min(cat_n, len(cat_articles))

        if cat_n >= len(cat_articles):
            selected.extend(cat_articles)
        else:
            # Time-stratified: split into time slices, sample from each
            n_slices = min(cat_n, 4)
            slice_size = len(cat_articles) // n_slices
            remainder = cat_n

            for s in range(n_slices):
                start = s * slice_size
                end = start + slice_size if s < n_slices - 1 else len(cat_articles)
                time_slice = cat_articles[start:end]

                n_from_slice = remainder // (n_slices - s)
                n_from_slice = min(n_from_slice, len(time_slice))
                selected.extend(rng.sample(time_slice, n_from_slice))
                remainder -= n_from_slice

    # If we overshot or undershot, adjust
    if len(selected) > target_n:
        selected = rng.sample(selected, target_n)

    rng.shuffle(selected)
    return selected


def chunk_articles(
    articles: list[Article],
    settings: Settings,
    token_counter: Callable[[str], int],
) -> list[list[Article]]:
    """Split articles into chunks for batch analysis.

    Greedy bin-packing: add articles to current chunk until token limit.

    Args:
        articles: Articles to chunk.
        settings: App settings.
        token_counter: Function that counts tokens in a string.

    Returns:
        List of article chunks.
    """
    max_tokens = settings.chunk_max_tokens
    max_per_chunk = settings.chunk_articles
    chunks: list[list[Article]] = []
    current_chunk: list[Article] = []
    current_tokens = 0

    for article in articles:
        article_text = f"## {article.title}\n\n{article.content}"
        article_tokens = token_counter(article_text)

        if (
            current_chunk
            and (current_tokens + article_tokens > max_tokens or len(current_chunk) >= max_per_chunk)
        ):
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0

        current_chunk.append(article)
        current_tokens += article_tokens

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
