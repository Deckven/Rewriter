"""WordPress WXR (WordPress eXtended RSS) XML parser."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterator

from bs4 import BeautifulSoup
from rich.console import Console

from rewriter.corpus.models import Article
from rewriter.importer.cleaner import clean_html

console = Console()

# WXR XML namespaces
WP_NS = "http://wordpress.org/export/"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
EXCERPT_NS = "http://wordpress.org/export/"
DC_NS = "http://purl.org/dc/elements/1.1/"

# Namespace prefixes used in WXR
_NS_MAP = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def parse_wxr(xml_path: Path, *, min_words: int = 50) -> Iterator[Article]:
    """Parse a WordPress WXR XML export file.

    Args:
        xml_path: Path to the XML file.
        min_words: Minimum word count to include an article.

    Yields:
        Article objects for each published post meeting the word threshold.
    """
    console.print(f"[dim]Parsing {xml_path.name}...[/dim]")

    with open(xml_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml-xml")

    items = soup.find_all("item")
    console.print(f"[dim]Found {len(items)} items in export[/dim]")

    for item in items:
        article = _parse_item(item)
        if article is None:
            continue
        if article.word_count < min_words:
            continue
        yield article


def _parse_item(item: BeautifulSoup) -> Article | None:
    """Parse a single <item> element into an Article."""
    # Only process posts (not pages, attachments, etc.)
    post_type = _get_wp_text(item, "post_type")
    if post_type != "post":
        return None

    status = _get_wp_text(item, "status")
    if status != "publish":
        return None

    # Basic fields
    title = _get_text(item, "title")
    slug = _get_wp_text(item, "post_name")

    # Content
    raw_html = _get_ns_text(item, "encoded", "content") or ""

    # Clean HTML to markdown-like text
    content = clean_html(raw_html)
    if not content:
        return None

    # Excerpt
    excerpt_html = _get_ns_text(item, "encoded", "excerpt") or ""
    excerpt = clean_html(excerpt_html) if excerpt_html else ""

    # WordPress post ID
    wp_id = int(_get_wp_text(item, "post_id") or "0")

    # Date
    pub_date_str = _get_wp_text(item, "post_date")
    published_at = None
    if pub_date_str and pub_date_str != "0000-00-00 00:00:00":
        try:
            published_at = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    # Categories and tags
    categories: list[str] = []
    tags: list[str] = []
    for cat_elem in item.find_all("category"):
        domain = cat_elem.get("domain", "")
        name = cat_elem.get_text(strip=True)
        if domain == "category" and name:
            categories.append(name)
        elif domain == "post_tag" and name:
            tags.append(name)

    article = Article(
        wp_id=wp_id,
        title=title,
        slug=slug,
        content=content,
        raw_html=raw_html,
        excerpt=excerpt,
        published_at=published_at,
        categories=categories,
        tags=tags,
        status=status,
    )
    article.compute_word_count()
    return article


def _get_text(element: BeautifulSoup, tag: str) -> str:
    """Get text content of a direct child tag."""
    found = element.find(tag, recursive=False)
    if found:
        return found.get_text(strip=True)
    return ""


def _get_wp_text(element: BeautifulSoup, local_name: str) -> str:
    """Get text from a wp: namespaced tag.

    Tries multiple namespace variations since WXR versions differ.
    """
    # Try with explicit namespace
    for ns_uri in [
        "http://wordpress.org/export/1.2/",
        "http://wordpress.org/export/1.1/",
        "http://wordpress.org/export/1.0/",
        "http://wordpress.org/export/",
    ]:
        found = element.find(f"{local_name}", attrs={}, recursive=False)
        if found and found.prefix == "wp":
            return found.get_text(strip=True)

    # Fallback: find by local name with wp prefix pattern
    for child in element.children:
        if hasattr(child, "name") and child.name and ":" in str(child.name):
            prefix, name = str(child.name).split(":", 1)
            if name == local_name and prefix == "wp":
                return child.get_text(strip=True)

    # Last resort: find by local name matching
    found = element.find(local_name, recursive=False)
    if found:
        return found.get_text(strip=True)

    return ""


def _get_ns_text(element: BeautifulSoup, local_name: str, prefix: str) -> str:
    """Get text from a namespaced tag by prefix (content:encoded, excerpt:encoded)."""
    # Try prefixed name
    for child in element.children:
        if hasattr(child, "name") and child.name and ":" in str(child.name):
            p, n = str(child.name).split(":", 1)
            if n == local_name and p == prefix:
                return child.get_text(strip=True)

    # Try with just the local name and check prefix attribute
    found = element.find(local_name, recursive=False)
    if found and getattr(found, "prefix", "") == prefix:
        return found.get_text(strip=True)

    return ""
