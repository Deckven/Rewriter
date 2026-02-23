"""Anthropic API wrapper with retry, rate-limit handling, and prompt caching."""

from __future__ import annotations

import time
from typing import Any

import anthropic
from rich.console import Console

from rewriter.config import Settings

console = Console()

# Retry config
MAX_RETRIES = 10
BASE_DELAY = 2.0
MAX_DELAY = 120.0


class LLMClient:
    """Wrapper around Anthropic SDK with retry and caching support."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            max_retries=0,  # we handle retries ourselves
        )
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cache_read_tokens = 0
        self._total_cache_creation_tokens = 0

    def complete(
        self,
        *,
        system: str | list[dict[str, Any]],
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send a completion request with retry logic.

        Args:
            system: System prompt (string or structured blocks with cache_control).
            messages: Conversation messages.
            model: Override model.
            max_tokens: Override max tokens.
            temperature: Override temperature.

        Returns:
            The assistant's text response.
        """
        model = model or self.settings.model
        max_tokens = max_tokens or self.settings.max_tokens
        temperature = temperature if temperature is not None else self.settings.temperature

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.messages.create(**kwargs)
                self._track_usage(response.usage)
                return self._extract_text(response)
            except anthropic.RateLimitError as e:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                # Check for retry-after header
                retry_after = getattr(e, 'response', None)
                if retry_after and hasattr(retry_after, 'headers'):
                    ra = retry_after.headers.get('retry-after')
                    if ra:
                        delay = max(delay, float(ra))
                console.print(
                    f"[yellow]Rate limited. Retrying in {delay:.0f}s "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})...[/yellow]"
                )
                time.sleep(delay)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500 or e.status_code == 529:
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    console.print(
                        f"[yellow]Server error {e.status_code}. Retrying in {delay:.0f}s...[/yellow]"
                    )
                    time.sleep(delay)
                else:
                    raise

        raise RuntimeError(f"Failed after {MAX_RETRIES} retries")

    def complete_cached(
        self,
        *,
        system_text: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send a request with prompt caching on the system prompt."""
        system = [
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        return self.complete(
            system=system,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def count_tokens(self, text: str) -> int:
        """Estimate token count using tiktoken (cl100k_base as approximation)."""
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))

    def _track_usage(self, usage: Any) -> None:
        self._total_input_tokens += getattr(usage, "input_tokens", 0)
        self._total_output_tokens += getattr(usage, "output_tokens", 0)
        self._total_cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0)
        self._total_cache_creation_tokens += getattr(usage, "cache_creation_input_tokens", 0)

    @staticmethod
    def _extract_text(response: Any) -> str:
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    @property
    def usage_summary(self) -> dict[str, int]:
        return {
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "cache_read_tokens": self._total_cache_read_tokens,
            "cache_creation_tokens": self._total_cache_creation_tokens,
        }

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        *,
        batch: bool = False,
    ) -> float:
        """Rough cost estimate in USD (Sonnet pricing)."""
        input_price = 3.0 / 1_000_000   # $3 per 1M input
        output_price = 15.0 / 1_000_000  # $15 per 1M output
        multiplier = 0.5 if batch else 1.0
        return (input_tokens * input_price + output_tokens * output_price) * multiplier
