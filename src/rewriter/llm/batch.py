"""Batch API for mass analysis — 50% cost savings."""

from __future__ import annotations

import time
from typing import Any

import anthropic
from anthropic.types.messages import batch_create_params
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from rewriter.config import Settings

console = Console()

POLL_INTERVAL = 30  # seconds


class BatchProcessor:
    """Process multiple requests through the Anthropic Batch API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def submit_batch(
        self,
        requests: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Submit a batch of requests.

        Args:
            requests: List of dicts with 'custom_id', 'system', 'messages' keys.
            model: Override model.
            max_tokens: Override max tokens.
            temperature: Override temperature.

        Returns:
            Batch ID for polling.
        """
        model = model or self.settings.analysis_model
        max_tokens = max_tokens or self.settings.max_tokens
        temperature = temperature if temperature is not None else 0.5

        batch_requests = []
        for req in requests:
            params: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": req["messages"],
            }
            if req.get("system"):
                params["system"] = req["system"]

            batch_requests.append(
                batch_create_params.Request(
                    custom_id=req["custom_id"],
                    params=params,
                )
            )

        batch = self.client.messages.batches.create(requests=batch_requests)
        console.print(f"[green]Batch submitted: {batch.id} ({len(requests)} requests)[/green]")
        return batch.id

    def wait_for_batch(self, batch_id: str) -> dict[str, str]:
        """Poll until batch completes, then retrieve results.

        Returns:
            Mapping of custom_id → response text.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Waiting for batch...", total=None)

            while True:
                batch = self.client.messages.batches.retrieve(batch_id)
                status = batch.processing_status

                progress.update(
                    task,
                    description=f"Batch {batch_id[:12]}… status={status}"
                )

                if status == "ended":
                    break

                time.sleep(POLL_INTERVAL)

        return self._collect_results(batch_id)

    def submit_and_wait(
        self,
        requests: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, str]:
        """Submit batch and block until results are ready."""
        batch_id = self.submit_batch(requests, **kwargs)
        return self.wait_for_batch(batch_id)

    def _collect_results(self, batch_id: str) -> dict[str, str]:
        """Download and parse batch results."""
        results: dict[str, str] = {}

        for event in self.client.messages.batches.results(batch_id):
            custom_id = event.custom_id
            if event.result.type == "succeeded":
                message = event.result.message
                text = ""
                for block in message.content:
                    if block.type == "text":
                        text += block.text
                results[custom_id] = text
            else:
                console.print(f"[red]Request {custom_id} failed: {event.result.type}[/red]")
                results[custom_id] = ""

        console.print(f"[green]Batch complete: {len(results)} results collected[/green]")
        return results

    def fallback_sequential(
        self,
        requests: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, str]:
        """Process requests sequentially (fallback if batch not available)."""
        from rewriter.llm.client import LLMClient

        llm = LLMClient(self.settings)
        model = model or self.settings.analysis_model
        max_tokens = max_tokens or self.settings.max_tokens
        temperature = temperature if temperature is not None else 0.5

        results: dict[str, str] = {}
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=len(requests))
            for i, req in enumerate(requests):
                progress.update(
                    task,
                    description=f"Chunk {req['custom_id']} ({i+1}/{len(requests)})",
                )
                text = llm.complete(
                    system=req.get("system", ""),
                    messages=req["messages"],
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                results[req["custom_id"]] = text
                progress.advance(task)
                # Brief pause between requests to avoid rate limits
                if i < len(requests) - 1:
                    time.sleep(1)

        return results
