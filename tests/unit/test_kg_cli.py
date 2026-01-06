"""Tests for KG CLI commands."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from scripts.kg_cli import cli, reset_manager


def _invoke(args: list[str], runner: CliRunner | None = None):
    runner = runner or CliRunner()
    return runner.invoke(cli, args)


def test_entity_and_relation_commands(tmp_path: Path):
    reset_manager()
    runner = CliRunner()

    result = _invoke(
        ["entity", "add", "Policy Alpha", "--type", "POLICY", "-a", "status=active"],
        runner,
    )
    assert result.exit_code == 0

    result = _invoke(["entity", "add", "Agency X", "--type", "AGENCY"], runner)
    assert result.exit_code == 0

    result = _invoke(["entity", "update", "Policy Alpha", "-a", "status=retired"], runner)
    assert result.exit_code == 0

    result = _invoke(["entity", "list"], runner)
    data = yaml.safe_load(result.output)
    assert len(data) == 2
    assert any(entity["attributes"].get("status") == "retired" for entity in data)

    result = _invoke(
        ["relation", "add", "Agency X", "Policy Alpha", "--type", "SUPPORTS", "-a", "weight=0.95"],
        runner,
    )
    assert result.exit_code == 0

    result = _invoke(["relation", "list"], runner)
    relations = yaml.safe_load(result.output)
    assert relations[0]["type"] == "SUPPORTS"

    result = _invoke(["merge", "Policy Alpha", "Agency X"], runner)
    assert result.exit_code == 0

    result = _invoke(["audit", "list"], runner)
    audit_entries = yaml.safe_load(result.output)
    assert any(entry["operation"] == "merge_entities" for entry in audit_entries)


def test_batch_commands(tmp_path: Path):
    reset_manager()
    batch_file = tmp_path / "ops.yaml"
    batch_file.write_text(
        """
        - operation: add_entity
          name: Alpha
          entity_type: POLICY
        - operation: add_entity
          name: Beta
          entity_type: POLICY
        """,
        encoding="utf-8",
    )
    runner = CliRunner()

    result = _invoke(["batch", "validate", str(batch_file)], runner)
    assert result.exit_code == 0

    result = _invoke(["batch", "apply", str(batch_file), "--no-rollback"], runner)
    assert result.exit_code == 0

    result = _invoke(["entity", "search", "Alpha"], runner)
    data = yaml.safe_load(result.output)
    assert data[0]["name"] == "Alpha"
