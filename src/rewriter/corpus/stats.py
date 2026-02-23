"""Corpus statistics utilities."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from rewriter.corpus.models import CorpusStats
from rewriter.corpus.store import CorpusStore


def compute_stats(store: CorpusStore) -> CorpusStats:
    """Compute summary statistics for the corpus."""
    articles = store.get_all_articles()

    if not articles:
        return CorpusStats()

    word_counts = [a.word_count for a in articles]
    categories = store.get_categories_distribution()

    dates = [a.published_at for a in articles if a.published_at]
    date_range = None
    if dates:
        date_range = (
            min(dates).strftime("%Y-%m-%d"),
            max(dates).strftime("%Y-%m-%d"),
        )

    examples = store.get_examples()
    guide = store.get_latest_style_guide()

    return CorpusStats(
        total_articles=len(articles),
        total_words=sum(word_counts),
        avg_words=sum(word_counts) / len(word_counts),
        min_words=min(word_counts),
        max_words=max(word_counts),
        categories=categories,
        date_range=date_range,
        n_examples=len(examples),
        has_style_guide=guide is not None,
    )


def print_stats(stats: CorpusStats, console: Console | None = None) -> None:
    """Pretty-print corpus statistics."""
    console = console or Console()

    table = Table(title="Corpus Statistics", show_header=False, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Total articles", str(stats.total_articles))
    table.add_row("Total words", f"{stats.total_words:,}")
    table.add_row("Avg words/article", f"{stats.avg_words:.0f}")
    table.add_row("Min words", str(stats.min_words))
    table.add_row("Max words", str(stats.max_words))

    if stats.date_range:
        table.add_row("Date range", f"{stats.date_range[0]} → {stats.date_range[1]}")

    table.add_row("Few-shot examples", str(stats.n_examples))
    table.add_row("Style guide", "Yes" if stats.has_style_guide else "No")

    console.print(table)

    if stats.categories:
        cat_table = Table(title="Categories (top 20)", show_header=True, padding=(0, 2))
        cat_table.add_column("Category")
        cat_table.add_column("Articles", justify="right")

        for cat, count in list(stats.categories.items())[:20]:
            cat_table.add_row(cat, str(count))

        console.print(cat_table)
