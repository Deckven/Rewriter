"""Click CLI — import, analyze, rewrite, corpus commands."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from rewriter.config import get_settings

console = Console()


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Rewriter — style transfer framework for blog content."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# ── Import ────────────────────────────────────────────────────


@cli.command("import")
@click.argument("xml_file", type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True, help="Clear existing articles before import")
@click.option("--dry-run", is_flag=True, help="Parse and show stats without saving")
@click.option("--min-words", type=int, default=None, help="Minimum word count (default: 50)")
@click.pass_context
def import_cmd(
    ctx: click.Context,
    xml_file: Path,
    force: bool,
    dry_run: bool,
    min_words: int | None,
) -> None:
    """Import articles from a WordPress XML export file."""
    from rewriter.corpus.store import CorpusStore
    from rewriter.importer.wordpress import parse_wxr

    overrides = {}
    if min_words is not None:
        overrides["min_words"] = min_words
    settings = get_settings(**overrides)
    settings.ensure_data_dir()

    console.print(f"Parsing [bold]{xml_file.name}[/bold]...")

    articles = list(parse_wxr(xml_file, min_words=settings.min_words))

    if not articles:
        console.print("[red]No articles found matching criteria.[/red]")
        return

    # Stats
    word_counts = [a.word_count for a in articles]
    categories: dict[str, int] = {}
    for a in articles:
        for cat in a.categories:
            categories[cat] = categories.get(cat, 0) + 1

    table = Table(title="Import Summary", show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Articles found", str(len(articles)))
    table.add_row("Total words", f"{sum(word_counts):,}")
    table.add_row("Avg words/article", f"{sum(word_counts)/len(word_counts):.0f}")
    table.add_row("Categories", str(len(categories)))
    console.print(table)

    if dry_run:
        console.print("[yellow]Dry run — no data saved.[/yellow]")

        if ctx.obj.get("verbose"):
            console.print("\n[bold]Sample articles:[/bold]")
            for a in articles[:5]:
                console.print(f"  - {a.title} ({a.word_count} words) [{', '.join(a.categories)}]")
                if a.content:
                    preview = a.content[:200].replace("\n", " ")
                    console.print(f"    [dim]{preview}...[/dim]")
        return

    store = CorpusStore(settings.db_path)
    try:
        if force:
            store.clear_articles()
            console.print("[yellow]Cleared existing articles.[/yellow]")

        count = store.insert_articles_batch(articles)
        console.print(f"[green]Imported {count} articles[/green] (skipped {len(articles) - count} duplicates)")
    finally:
        store.close()


# ── Analyze ───────────────────────────────────────────────────


@cli.command()
@click.option("--cost-estimate", is_flag=True, help="Show cost estimate without running")
@click.option("--resume", is_flag=True, help="Resume from existing chunk analyses")
@click.option("--use-batch/--no-batch", default=True, help="Use Batch API (default: yes)")
@click.pass_context
def analyze(
    ctx: click.Context,
    cost_estimate: bool,
    resume: bool,
    use_batch: bool,
) -> None:
    """Analyze corpus style and generate style guide."""
    from rewriter.analyzer.examples import ExampleSelector
    from rewriter.analyzer.style_extractor import StyleExtractor
    from rewriter.corpus.store import CorpusStore

    settings = get_settings()
    settings.ensure_data_dir()
    store = CorpusStore(settings.db_path)

    try:
        if store.count_articles() == 0:
            console.print("[red]No articles in corpus. Run `rewriter import` first.[/red]")
            return

        extractor = StyleExtractor(settings, store)

        if cost_estimate:
            est = extractor.estimate_cost()
            table = Table(title="Cost Estimate", show_header=False)
            table.add_column("Metric", style="bold")
            table.add_column("Value")
            table.add_row("Sample size", str(est["sample_size"]))
            table.add_row("Chunks", str(est["n_chunks"]))
            table.add_row("Input tokens (est.)", f"{est['total_input_tokens']:,}")
            table.add_row("Output tokens (est.)", f"{est['total_output_tokens']:,}")
            table.add_row("Cost (Batch API)", f"${est['estimated_cost_batch']:.2f}")
            table.add_row("Cost (Direct API)", f"${est['estimated_cost_direct']:.2f}")
            console.print(table)
            return

        # Step 1: Style analysis
        console.print("[bold]Step 1/2: Hierarchical style analysis[/bold]")
        guide = extractor.run(use_batch=use_batch, resume=resume)

        # Step 2: Example selection
        console.print("\n[bold]Step 2/2: Example selection (TF-IDF + K-Means)[/bold]")
        selector = ExampleSelector(settings, store)
        examples = selector.build_clusters()

        console.print(
            f"\n[bold green]Analysis complete![/bold green]\n"
            f"  Style guide: {settings.style_guide_md_path}\n"
            f"  Examples: {len(examples)} representative articles\n"
            f"  Ready for rewriting."
        )
    finally:
        store.close()


# ── Rewrite ───────────────────────────────────────────────────


@cli.command()
@click.argument("input_file", required=False, type=click.Path(exists=True, path_type=Path))
@click.option("--text", "-t", type=str, help="Text to rewrite (alternative to file)")
@click.option(
    "--intensity", "-i",
    type=click.Choice(["light", "medium", "full"]),
    default=None,
    help="Rewrite intensity",
)
@click.option("--preserve-structure", "-p", is_flag=True, help="Preserve original structure")
@click.option("--temperature", type=float, default=None, help="Sampling temperature")
@click.option("--n-examples", "-n", type=int, default=None, help="Number of few-shot examples")
@click.option(
    "--example-file", "-e",
    type=click.Path(exists=True, path_type=Path),
    multiple=True,
    help="Extra example text file (can be repeated)",
)
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file")
@click.pass_context
def rewrite(
    ctx: click.Context,
    input_file: Path | None,
    text: str | None,
    intensity: str | None,
    preserve_structure: bool,
    temperature: float | None,
    n_examples: int | None,
    example_file: tuple[Path, ...],
    output: Path | None,
) -> None:
    """Rewrite text in the blog's style.

    Reads from INPUT_FILE, --text argument, or stdin.
    """
    from rewriter.corpus.store import CorpusStore
    from rewriter.rewrite.engine import RewriteEngine

    # Get input text
    if text:
        input_text = text
    elif input_file:
        input_text = input_file.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        input_text = sys.stdin.read()
    else:
        console.print("[red]Provide text via INPUT_FILE, --text, or stdin.[/red]")
        raise SystemExit(1)

    if not input_text.strip():
        console.print("[red]Empty input text.[/red]")
        raise SystemExit(1)

    verbose = ctx.obj.get("verbose", False)
    settings = get_settings()
    store = CorpusStore(settings.db_path)

    try:
        # Load user-provided example texts
        extra_examples: list[str] | None = None
        if example_file:
            extra_examples = []
            for ef in example_file:
                content = ef.read_text(encoding="utf-8").strip()
                if content:
                    extra_examples.append(content)
                    if verbose:
                        console.print(f"[dim]Loaded example: {ef.name} ({len(content)} chars)[/dim]")

        engine = RewriteEngine(settings, store)
        result = engine.rewrite(
            input_text,
            intensity=intensity,
            n_examples=n_examples,
            extra_examples=extra_examples or None,
            preserve_structure=preserve_structure or None,
            temperature=temperature,
            verbose=verbose,
        )

        if output:
            output.write_text(result, encoding="utf-8")
            console.print(f"[green]Written to {output}[/green]")
        else:
            console.print("\n" + result)
    finally:
        store.close()


# ── Corpus ────────────────────────────────────────────────────


@cli.group()
def corpus() -> None:
    """Corpus management commands."""
    pass


@corpus.command()
def stats() -> None:
    """Show corpus statistics."""
    from rewriter.corpus.stats import compute_stats, print_stats
    from rewriter.corpus.store import CorpusStore

    settings = get_settings()
    if not settings.db_path.exists():
        console.print("[red]No corpus database found. Run `rewriter import` first.[/red]")
        return

    store = CorpusStore(settings.db_path)
    try:
        s = compute_stats(store)
        if s.total_articles == 0:
            console.print("[yellow]Corpus is empty.[/yellow]")
            return
        print_stats(s, console)
    finally:
        store.close()


@corpus.command()
@click.argument("article_id", type=int)
def show(article_id: int) -> None:
    """Show a specific article by ID."""
    from rewriter.corpus.store import CorpusStore

    settings = get_settings()
    store = CorpusStore(settings.db_path)
    try:
        article = store.get_article(article_id)
        if article is None:
            console.print(f"[red]Article {article_id} not found.[/red]")
            return

        console.print(f"[bold]{article.title}[/bold]")
        console.print(f"[dim]ID: {article.id} | WP ID: {article.wp_id} | "
                      f"Words: {article.word_count} | "
                      f"Categories: {', '.join(article.categories)}[/dim]")
        if article.published_at:
            console.print(f"[dim]Published: {article.published_at.strftime('%Y-%m-%d')}[/dim]")
        console.print()
        console.print(article.content)
    finally:
        store.close()


@corpus.command()
def examples() -> None:
    """List selected few-shot examples."""
    from rewriter.corpus.store import CorpusStore

    settings = get_settings()
    store = CorpusStore(settings.db_path)
    try:
        exs = store.get_examples()
        if not exs:
            console.print("[yellow]No examples selected. Run `rewriter analyze` first.[/yellow]")
            return

        table = Table(title=f"Few-Shot Examples ({len(exs)})")
        table.add_column("Cluster", justify="right")
        table.add_column("Article ID", justify="right")
        table.add_column("Title")
        table.add_column("Words", justify="right")
        table.add_column("Distance", justify="right")

        for ex in exs:
            article = store.get_article(ex.article_id)
            if article:
                table.add_row(
                    str(ex.cluster_id),
                    str(ex.article_id),
                    article.title[:60],
                    str(article.word_count),
                    f"{ex.distance_to_centroid:.4f}",
                )
        console.print(table)
    finally:
        store.close()


@corpus.command("style-guide")
def style_guide() -> None:
    """Show the current style guide."""
    settings = get_settings()
    md_path = settings.style_guide_md_path

    if md_path.exists():
        from rich.markdown import Markdown
        content = md_path.read_text(encoding="utf-8")
        console.print(Markdown(content))
    else:
        console.print("[yellow]No style guide found. Run `rewriter analyze` first.[/yellow]")
