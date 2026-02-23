"""HTML → structured plaintext (markdown-like) conversion."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag


# WordPress shortcode pattern: [shortcode ...] ... [/shortcode] or [shortcode ... /]
_SHORTCODE_RE = re.compile(r"\[/?[a-zA-Z_][\w-]*(?:\s[^\]]*)?/?\]")

# Consecutive blank lines
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

# Leading/trailing whitespace per line (preserve intentional indentation for lists)
_TRAILING_SPACE_RE = re.compile(r"[ \t]+$", re.MULTILINE)


def clean_html(html: str) -> str:
    """Convert HTML content to structured plaintext (markdown-like).

    Preserves semantic structure: headings, lists, emphasis, paragraphs.
    Strips scripts, styles, shortcodes, and extraneous markup.
    """
    if not html or not html.strip():
        return ""

    # Strip shortcodes before parsing
    html = _SHORTCODE_RE.sub("", html)

    soup = BeautifulSoup(html, "lxml")

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "iframe", "noscript", "svg"]):
        tag.decompose()

    # Convert to markdown-like text
    lines = _convert_element(soup)
    text = "\n".join(lines)

    # Normalize whitespace
    text = _TRAILING_SPACE_RE.sub("", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    text = text.strip()

    return text


def _convert_element(element: Tag | NavigableString) -> list[str]:
    """Recursively convert an element to lines of text."""
    if isinstance(element, NavigableString):
        text = str(element)
        # Collapse internal whitespace but preserve meaningful content
        text = re.sub(r"[ \t]+", " ", text)
        text = text.replace("\n", " ")
        if text.strip():
            return [text.strip()]
        return []

    if not isinstance(element, Tag):
        return []

    tag_name = element.name

    # Headings → markdown-style
    if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag_name[1])
        inner = _inline_text(element)
        if inner:
            return ["", "#" * level + " " + inner, ""]
        return []

    # Paragraphs
    if tag_name == "p":
        inner = _inline_text(element)
        if inner:
            return ["", inner, ""]
        return []

    # Block quotes
    if tag_name == "blockquote":
        children_lines = _collect_children(element)
        return [""] + ["> " + line if line else ">" for line in children_lines] + [""]

    # Unordered lists
    if tag_name in ("ul", "ol"):
        items: list[str] = []
        items.append("")
        for i, li in enumerate(element.find_all("li", recursive=False)):
            inner = _inline_text(li)
            if inner:
                if tag_name == "ol":
                    items.append(f"{i + 1}. {inner}")
                else:
                    items.append(f"- {inner}")
        items.append("")
        return items

    # List items (if not nested inside ul/ol)
    if tag_name == "li":
        inner = _inline_text(element)
        if inner:
            return [f"- {inner}"]
        return []

    # Line breaks
    if tag_name == "br":
        return [""]

    # Horizontal rules
    if tag_name == "hr":
        return ["", "---", ""]

    # Pre/code blocks
    if tag_name == "pre":
        code = element.get_text()
        return ["", "```", code.strip(), "```", ""]

    # Images — preserve alt text
    if tag_name == "img":
        alt = element.get("alt", "")
        if alt:
            return [f"[{alt}]"]
        return []

    # Links — preserve text
    if tag_name == "a":
        inner = _inline_text(element)
        return [inner] if inner else []

    # Divs, sections, articles — just recurse
    if tag_name in ("div", "section", "article", "main", "figure", "figcaption", "span"):
        return _collect_children(element)

    # Table → simplified text
    if tag_name == "table":
        return _convert_table(element)

    # Default: recurse into children
    return _collect_children(element)


def _inline_text(element: Tag) -> str:
    """Extract inline text with emphasis markers."""
    parts: list[str] = []

    for child in element.children:
        if isinstance(child, NavigableString):
            text = re.sub(r"[ \t]+", " ", str(child))
            parts.append(text)
        elif isinstance(child, Tag):
            if child.name in ("strong", "b"):
                inner = _inline_text(child)
                if inner:
                    parts.append(f"**{inner.strip()}**")
            elif child.name in ("em", "i"):
                inner = _inline_text(child)
                if inner:
                    parts.append(f"*{inner.strip()}*")
            elif child.name == "code":
                inner = child.get_text()
                if inner:
                    parts.append(f"`{inner.strip()}`")
            elif child.name == "br":
                parts.append("\n")
            elif child.name == "a":
                inner = _inline_text(child)
                parts.append(inner)
            elif child.name == "img":
                alt = child.get("alt", "")
                if alt:
                    parts.append(f"[{alt}]")
            else:
                parts.append(_inline_text(child))

    result = "".join(parts)
    # Collapse whitespace but preserve newlines
    result = re.sub(r"[ \t]+", " ", result)
    return result.strip()


def _collect_children(element: Tag) -> list[str]:
    """Collect lines from all children."""
    lines: list[str] = []
    for child in element.children:
        lines.extend(_convert_element(child))
    return lines


def _convert_table(table: Tag) -> list[str]:
    """Convert a table to simplified text rows."""
    lines: list[str] = [""]
    for row in table.find_all("tr"):
        cells = []
        for cell in row.find_all(["td", "th"]):
            cells.append(_inline_text(cell))
        if cells:
            lines.append(" | ".join(cells))
    lines.append("")
    return lines
