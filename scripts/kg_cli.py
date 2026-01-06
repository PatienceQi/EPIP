"""Command-line interface for manual KG curation operations."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import click
import yaml

from epip.core.kg_manager import BatchProcessor, KGManager

manager = KGManager()


def reset_manager() -> KGManager:
    """Reset the global manager; primarily used in tests."""
    global manager
    manager = KGManager()
    return manager


def _run(coro):
    return asyncio.run(coro)


def _parse_attrs(pairs: tuple[str, ...]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise click.BadParameter(f"Attribute '{pair}' must be in key=value format")
        key, value = pair.split("=", 1)
        try:
            attrs[key] = yaml.safe_load(value)
        except yaml.YAMLError as exc:  # pragma: no cover - defensive guard
            raise click.BadParameter(f"Invalid value for {key}: {exc}") from exc
    return attrs


def _echo_data(data: Any) -> None:
    click.echo(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


@click.group()
def cli() -> None:
    """EPIP knowledge-graph management utilities."""


@cli.group()
def entity() -> None:
    """Entity management commands."""


@entity.command("add")
@click.argument("name")
@click.option("--type", "entity_type", required=True, help="Entity type label.")
@click.option(
    "--attr",
    "-a",
    multiple=True,
    help="Attribute key=value pair. Accepts YAML literals as values.",
)
def entity_add(name: str, entity_type: str, attr: tuple[str, ...]) -> None:
    attrs = _parse_attrs(attr)
    success = _run(manager.add_entity(name, entity_type, **attrs))
    if not success:
        raise click.ClickException(f"Entity '{name}' already exists.")
    click.echo(f"Entity '{name}' created.")


@entity.command("delete")
@click.argument("name")
def entity_delete(name: str) -> None:
    success = _run(manager.delete_entity(name))
    if not success:
        raise click.ClickException(f"Entity '{name}' not found.")
    click.echo(f"Entity '{name}' deleted.")


@entity.command("update")
@click.argument("name")
@click.option("--type", "entity_type", default=None, help="Updated entity type.")
@click.option(
    "--attr",
    "-a",
    multiple=True,
    help="Attribute key=value updates. Accepts YAML literals.",
)
def entity_update(name: str, entity_type: str | None, attr: tuple[str, ...]) -> None:
    updates = _parse_attrs(attr)
    if entity_type:
        updates["entity_type"] = entity_type
    if not updates:
        raise click.ClickException("Provide at least one update via --type or --attr.")
    success = _run(manager.update_entity(name, **updates))
    if not success:
        raise click.ClickException(f"Entity '{name}' not found.")
    click.echo(f"Entity '{name}' updated.")


@entity.command("list")
@click.option("--type", "entity_type", default=None, help="Filter by entity type.")
@click.option("--limit", type=int, default=100, help="Maximum entities to show.")
def entity_list(entity_type: str | None, limit: int) -> None:
    records = _run(manager.list_entities(entity_type=entity_type, limit=limit))
    _echo_data(records)


@entity.command("search")
@click.argument("pattern")
def entity_search(pattern: str) -> None:
    records = _run(manager.search_entities(pattern))
    _echo_data(records)


@cli.group()
def relation() -> None:
    """Relation management commands."""


@relation.command("add")
@click.argument("source")
@click.argument("target")
@click.option("--type", "relation_type", required=True, help="Relation type label.")
@click.option("--attr", "-a", multiple=True, help="Attribute key=value pairs.")
def relation_add(
    source: str, target: str, relation_type: str, attr: tuple[str, ...]
) -> None:
    attrs = _parse_attrs(attr)
    success = _run(manager.add_relation(source, target, relation_type, **attrs))
    if not success:
        raise click.ClickException("Both source and target must exist before adding relations.")
    click.echo(f"Relation {source} -[{relation_type}]-> {target} created.")


@relation.command("delete")
@click.argument("source")
@click.argument("target")
@click.option(
    "--type",
    "relation_type",
    default=None,
    help="Only delete relations matching this type.",
)
def relation_delete(source: str, target: str, relation_type: str | None) -> None:
    success = _run(manager.delete_relation(source, target, relation_type))
    if not success:
        raise click.ClickException("No matching relation found.")
    click.echo("Relation deleted.")


@relation.command("list")
@click.option("--source", default=None, help="Filter by source entity.")
@click.option("--target", default=None, help="Filter by target entity.")
def relation_list(source: str | None, target: str | None) -> None:
    records = _run(manager.list_relations(source=source, target=target))
    _echo_data(records)


@cli.command()
@click.argument("source")
@click.argument("target")
def merge(source: str, target: str) -> None:
    success = _run(manager.merge_entities(source, target))
    if not success:
        raise click.ClickException("Both source and target entities must exist.")
    click.echo(f"Merged '{source}' into '{target}'.")


@cli.group()
def audit() -> None:
    """Audit log commands."""


@audit.command("list")
@click.option("--limit", type=int, default=50, help="Number of entries to show.")
def audit_list(limit: int) -> None:
    entries = [entry.to_dict() for entry in manager.list_audit_entries(limit=limit)]
    _echo_data(entries)


@cli.group()
def batch() -> None:
    """Batch processing commands."""


def _report_errors(errors: list[str]) -> None:
    for error in errors:
        click.echo(error, err=True)


@batch.command("validate")
@click.argument("path")
def batch_validate(path: str) -> None:
    processor = BatchProcessor(manager)
    operations = processor.load_operations(path)
    errors = processor.validate_operations(operations)
    if errors:
        _report_errors(errors)
        raise click.ClickException("Validation failed.")
    click.echo(f"{len(operations)} operations validated successfully.")


@batch.command("apply")
@click.argument("path")
@click.option(
    "--rollback/--no-rollback",
    default=True,
    show_default=True,
    help="Rollback if any operation fails.",
)
def batch_apply(path: str, rollback: bool) -> None:
    processor = BatchProcessor(manager)
    operations = processor.load_operations(path)
    success, failure = _run(processor.apply_operations(operations, rollback_on_error=rollback))
    if failure and rollback:
        raise click.ClickException("Batch failed and changes were rolled back.")
    click.echo(f"Applied operations - success: {success}, failed: {failure}")


if __name__ == "__main__":
    try:
        cli()
    except click.ClickException as exc:  # pragma: no cover - handled via click
        click.echo(str(exc), err=True)
        sys.exit(exc.exit_code)
