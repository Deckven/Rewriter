"""Rewrite engine: prompt assembly + API call + postprocessing."""

from __future__ import annotations

import re

from rich.console import Console

from rewriter.analyzer.examples import ExampleSelector
from rewriter.config import Settings
from rewriter.corpus.store import CorpusStore
from rewriter.llm.client import LLMClient
from rewriter.rewrite.prompts import build_system_prompt, build_user_prompt

console = Console()


class RewriteEngine:
    """Orchestrates the style-transfer rewriting process."""

    def __init__(self, settings: Settings, store: CorpusStore) -> None:
        self.settings = settings
        self.store = store
        self.llm = LLMClient(settings)
        self.selector = ExampleSelector(settings, store)

    def rewrite(
        self,
        text: str,
        *,
        intensity: str | None = None,
        n_examples: int | None = None,
        extra_examples: list[str] | None = None,
        preserve_structure: bool | None = None,
        temperature: float | None = None,
        verbose: bool = False,
    ) -> str:
        """Rewrite text in the blog's style.

        Args:
            text: Input text to rewrite.
            intensity: Rewrite depth (light/medium/full).
            n_examples: Number of few-shot examples.
            extra_examples: Additional example texts provided by the user.
            preserve_structure: Keep original structure.
            temperature: Sampling temperature.
            verbose: Print debug info.

        Returns:
            Rewritten text.
        """
        intensity = intensity or self.settings.intensity
        n_examples = n_examples if n_examples is not None else self.settings.n_examples
        preserve_structure = (
            preserve_structure if preserve_structure is not None
            else self.settings.preserve_structure
        )
        temperature = temperature if temperature is not None else self.settings.temperature

        # Load style guide
        style_guide_md = self._load_style_guide()
        if verbose:
            console.print(f"[dim]Style guide loaded ({len(style_guide_md)} chars)[/dim]")

        # Select examples
        examples = self._select_examples(text, n_examples, verbose=verbose)

        # Prepend user-provided examples
        if extra_examples:
            if verbose:
                console.print(f"[dim]Adding {len(extra_examples)} user-provided example(s)[/dim]")
            examples = extra_examples + examples

        # Build prompts
        system_prompt = build_system_prompt(style_guide_md, intensity)
        user_prompt = build_user_prompt(
            text,
            examples,
            preserve_structure=preserve_structure,
        )

        if verbose:
            sys_tokens = self.llm.count_tokens(system_prompt)
            usr_tokens = self.llm.count_tokens(user_prompt)
            console.print(
                f"[dim]Prompt: system={sys_tokens} tokens, user={usr_tokens} tokens[/dim]"
            )

        # Call API with prompt caching on system prompt
        if verbose:
            console.print("[dim]Calling Claude API...[/dim]")

        result = self.llm.complete_cached(
            system_text=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=temperature,
        )

        # Postprocess
        result = self._postprocess(result)

        if verbose:
            usage = self.llm.usage_summary
            console.print(
                f"[dim]Usage: input={usage['input_tokens']}, "
                f"output={usage['output_tokens']}, "
                f"cache_read={usage['cache_read_tokens']}[/dim]"
            )

        return result

    def _load_style_guide(self) -> str:
        """Load style guide from file or database."""
        md_path = self.settings.style_guide_md_path
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")

        guide = self.store.get_latest_style_guide()
        if guide:
            return guide.markdown

        raise RuntimeError(
            "Style guide not found. Run `rewriter analyze` first."
        )

    def _select_examples(
        self,
        text: str,
        n: int,
        *,
        verbose: bool = False,
    ) -> list[str]:
        """Select the most relevant few-shot examples."""
        articles = self.selector.find_similar(text, n=n)

        if verbose:
            console.print(f"[dim]Selected {len(articles)} examples:[/dim]")
            for a in articles:
                console.print(f"[dim]  - {a.title} ({a.word_count} words)[/dim]")

        return [
            f"**{a.title}**\n\n{a.content}"
            for a in articles
        ]

    @staticmethod
    def _postprocess(text: str) -> str:
        """Clean up the LLM output."""
        text = text.strip()

        # Remove potential wrapper commentary
        # Sometimes LLM adds "Here's the rewritten text:" etc.
        lines = text.split("\n")
        if lines and re.match(
            r"^(Вот|Here|Переписанный|Готово|Результат)",
            lines[0],
            re.IGNORECASE,
        ):
            text = "\n".join(lines[1:]).strip()

        # Remove trailing commentary
        for marker in ["\n---\n", "\n***\n"]:
            if marker in text:
                idx = text.rfind(marker)
                after = text[idx + len(marker):].strip()
                # If text after marker is short, it's likely commentary
                if len(after) < 200:
                    text = text[:idx].strip()

        # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text
