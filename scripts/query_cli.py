"""Command-line interface for query parsing and planning."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import structlog

from epip.core.kg_builder import KnowledgeGraphBuilder
from epip.query.linker import EntityLinker
from epip.query.parser import ParsedQuery, QueryParser
from epip.query.planner import QueryPlan, QueryPlanner

logger = structlog.get_logger(__name__)

HISTORY_PATH = Path.home() / ".epip_query_history.jsonl"

parser = QueryParser()
linker = EntityLinker()
planner = QueryPlanner()
_kg_builder: KnowledgeGraphBuilder | None = None


def _get_builder() -> KnowledgeGraphBuilder:
    global _kg_builder
    if _kg_builder is None:
        _kg_builder = KnowledgeGraphBuilder()
    return _kg_builder


def _run(coro):
    return asyncio.run(coro)


async def _execute_pipeline(question: str) -> tuple[ParsedQuery, QueryPlan]:
    parsed = await parser.parse(question)
    linked = []
    try:
        builder = _get_builder()
        linked = await linker.link(parsed.entities, builder)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Entity linking skipped due to error", error=str(exc))
    plan = await planner.plan(parsed, linked)
    return parsed, plan


def _record_history(parsed: ParsedQuery, plan: QueryPlan) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": parsed.original,
        "intent": parsed.intent.value,
        "complexity": parsed.complexity,
        "plan": planner.to_json(plan),
    }
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - IO errors depend on environment
        logger.warning("Failed to write query history", error=str(exc))


def _load_history(limit: int) -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    selected = lines[-limit:] if limit > 0 else lines
    entries: list[dict[str, Any]] = []
    for raw in selected:
        try:
            entries.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return entries


def _print_history(limit: int) -> None:
    entries = _load_history(limit)
    if not entries:
        click.echo("No query history found.")
        return
    for entry in entries:
        click.echo(
            f"[{entry.get('timestamp')}] intent={entry.get('intent')} "
            f"complexity={entry.get('complexity')} :: {entry.get('query')}"
        )


@click.group()
def cli() -> None:
    """Interact with EPIP's natural-language query parser."""


@cli.command("query")
# Use nargs=-1 to support multi-word queries without quoting issues.
@click.argument("question", nargs=-1)
@click.option(
    "--summary",
    is_flag=True,
    default=False,
    help="Print a concise summary instead of the full JSON plan.",
)
@click.option(
    "--history",
    "history_limit",
    type=int,
    default=0,
    help="Display the last N history entries after executing the query.",
)
def run_query(question: tuple[str, ...], summary: bool, history_limit: int) -> None:
    """Parse a natural-language question and output a query plan."""
    if not question:
        raise click.ClickException("Provide a question to parse.")
    query_text = " ".join(question).strip()
    parsed, plan = _run(_execute_pipeline(query_text))
    plan_json = planner.to_json(plan)
    if summary:
        click.echo(f"Intent: {parsed.intent.value} (complexity={parsed.complexity})")
        click.echo(f"Entities: {[mention.text for mention in parsed.entities]}")
        click.echo(f"Constraints: {[constraint.field for constraint in parsed.constraints]}")
    else:
        click.echo(plan_json)
    _record_history(parsed, plan)
    if history_limit > 0:
        _print_history(history_limit)


@cli.command("history")
@click.option("--limit", type=int, default=5, help="Number of entries to display.")
def history(limit: int) -> None:
    """Display stored query parsing history."""
    _print_history(limit)


if __name__ == "__main__":  # pragma: no cover - manual execution path
    cli()
