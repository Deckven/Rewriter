"""SQLite storage for articles, analyses, style guide, and examples."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from rewriter.corpus.models import Article, ChunkAnalysis, FewShotExample, StyleGuide

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    wp_id       INTEGER UNIQUE,
    title       TEXT NOT NULL DEFAULT '',
    slug        TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    raw_html    TEXT NOT NULL DEFAULT '',
    excerpt     TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    categories  TEXT NOT NULL DEFAULT '[]',
    tags        TEXT NOT NULL DEFAULT '[]',
    word_count  INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'publish'
);

CREATE TABLE IF NOT EXISTS chunk_analyses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id     INTEGER NOT NULL,
    article_ids  TEXT NOT NULL DEFAULT '[]',
    analysis_text TEXT NOT NULL DEFAULT '',
    token_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS style_guide (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version     INTEGER NOT NULL DEFAULT 1,
    markdown    TEXT NOT NULL DEFAULT '',
    structured  TEXT NOT NULL DEFAULT '{}',
    sample_size INTEGER NOT NULL DEFAULT 0,
    n_chunks    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS examples (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id          INTEGER NOT NULL REFERENCES articles(id),
    cluster_id          INTEGER NOT NULL DEFAULT -1,
    distance_to_centroid REAL NOT NULL DEFAULT 0.0,
    UNIQUE(article_id)
);

CREATE INDEX IF NOT EXISTS idx_articles_wp_id ON articles(wp_id);
CREATE INDEX IF NOT EXISTS idx_articles_word_count ON articles(word_count);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
"""


class CorpusStore:
    """SQLite-backed storage for the corpus."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ── Articles ──────────────────────────────────────────────

    def insert_article(self, article: Article) -> int:
        """Insert an article, returning its row id. Skips duplicates by wp_id."""
        try:
            cur = self.conn.execute(
                """INSERT INTO articles
                   (wp_id, title, slug, content, raw_html, excerpt,
                    published_at, categories, tags, word_count, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article.wp_id,
                    article.title,
                    article.slug,
                    article.content,
                    article.raw_html,
                    article.excerpt,
                    article.published_at.isoformat() if article.published_at else None,
                    json.dumps(article.categories, ensure_ascii=False),
                    json.dumps(article.tags, ensure_ascii=False),
                    article.word_count,
                    article.status,
                ),
            )
            self.conn.commit()
            return cur.lastrowid  # type: ignore[return-value]
        except sqlite3.IntegrityError:
            # Duplicate wp_id — skip
            return -1

    def insert_articles_batch(self, articles: list[Article]) -> int:
        """Insert multiple articles in a transaction. Returns count of inserted."""
        count = 0
        with self.conn:
            for article in articles:
                try:
                    self.conn.execute(
                        """INSERT INTO articles
                           (wp_id, title, slug, content, raw_html, excerpt,
                            published_at, categories, tags, word_count, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            article.wp_id,
                            article.title,
                            article.slug,
                            article.content,
                            article.raw_html,
                            article.excerpt,
                            article.published_at.isoformat() if article.published_at else None,
                            json.dumps(article.categories, ensure_ascii=False),
                            json.dumps(article.tags, ensure_ascii=False),
                            article.word_count,
                            article.status,
                        ),
                    )
                    count += 1
                except sqlite3.IntegrityError:
                    continue
        return count

    def get_article(self, article_id: int) -> Article | None:
        row = self.conn.execute(
            "SELECT * FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_article(row)

    def get_all_articles(self) -> list[Article]:
        rows = self.conn.execute(
            "SELECT * FROM articles ORDER BY published_at"
        ).fetchall()
        return [self._row_to_article(r) for r in rows]

    def get_article_ids(self) -> list[int]:
        rows = self.conn.execute("SELECT id FROM articles ORDER BY id").fetchall()
        return [r["id"] for r in rows]

    def get_articles_by_ids(self, ids: list[int]) -> list[Article]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.conn.execute(
            f"SELECT * FROM articles WHERE id IN ({placeholders}) ORDER BY id",
            ids,
        ).fetchall()
        return [self._row_to_article(r) for r in rows]

    def count_articles(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM articles").fetchone()
        return row["cnt"]

    def clear_articles(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM articles")
            self.conn.execute("DELETE FROM examples")

    @staticmethod
    def _row_to_article(row: sqlite3.Row) -> Article:
        pub = row["published_at"]
        published_at = None
        if pub:
            try:
                published_at = datetime.fromisoformat(pub)
            except ValueError:
                pass
        return Article(
            id=row["id"],
            wp_id=row["wp_id"],
            title=row["title"],
            slug=row["slug"],
            content=row["content"],
            raw_html=row["raw_html"],
            excerpt=row["excerpt"],
            published_at=published_at,
            categories=json.loads(row["categories"]),
            tags=json.loads(row["tags"]),
            word_count=row["word_count"],
            status=row["status"],
        )

    # ── Chunk Analyses ────────────────────────────────────────

    def save_chunk_analysis(self, analysis: ChunkAnalysis) -> int:
        cur = self.conn.execute(
            """INSERT INTO chunk_analyses
               (chunk_id, article_ids, analysis_text, token_count, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                analysis.chunk_id,
                json.dumps(analysis.article_ids),
                analysis.analysis_text,
                analysis.token_count,
                analysis.created_at.isoformat(),
            ),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_chunk_analyses(self) -> list[ChunkAnalysis]:
        rows = self.conn.execute(
            "SELECT * FROM chunk_analyses ORDER BY chunk_id"
        ).fetchall()
        return [
            ChunkAnalysis(
                chunk_id=r["chunk_id"],
                article_ids=json.loads(r["article_ids"]),
                analysis_text=r["analysis_text"],
                token_count=r["token_count"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def clear_analyses(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM chunk_analyses")

    # ── Style Guide ───────────────────────────────────────────

    def save_style_guide(self, guide: StyleGuide) -> int:
        cur = self.conn.execute(
            """INSERT INTO style_guide
               (version, markdown, structured, sample_size, n_chunks, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                guide.version,
                guide.markdown,
                json.dumps(guide.structured, ensure_ascii=False),
                guide.sample_size,
                guide.n_chunks,
                guide.created_at.isoformat(),
            ),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_latest_style_guide(self) -> StyleGuide | None:
        row = self.conn.execute(
            "SELECT * FROM style_guide ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return StyleGuide(
            version=row["version"],
            markdown=row["markdown"],
            structured=json.loads(row["structured"]),
            sample_size=row["sample_size"],
            n_chunks=row["n_chunks"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ── Examples ──────────────────────────────────────────────

    def save_examples(self, examples: list[FewShotExample]) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM examples")
            for ex in examples:
                self.conn.execute(
                    """INSERT INTO examples (article_id, cluster_id, distance_to_centroid)
                       VALUES (?, ?, ?)""",
                    (ex.article_id, ex.cluster_id, ex.distance_to_centroid),
                )

    def get_examples(self) -> list[FewShotExample]:
        rows = self.conn.execute(
            "SELECT * FROM examples ORDER BY cluster_id"
        ).fetchall()
        return [
            FewShotExample(
                article_id=r["article_id"],
                cluster_id=r["cluster_id"],
                distance_to_centroid=r["distance_to_centroid"],
            )
            for r in rows
        ]

    def get_example_article_ids(self) -> list[int]:
        rows = self.conn.execute(
            "SELECT article_id FROM examples ORDER BY cluster_id"
        ).fetchall()
        return [r["article_id"] for r in rows]

    # ── Utilities ─────────────────────────────────────────────

    def get_categories_distribution(self) -> dict[str, int]:
        """Get article count per category."""
        articles = self.get_all_articles()
        dist: dict[str, int] = {}
        for a in articles:
            for cat in a.categories:
                dist[cat] = dist.get(cat, 0) + 1
        return dict(sorted(dist.items(), key=lambda x: -x[1]))
