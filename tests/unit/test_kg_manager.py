"""Tests for KGManager core primitives."""

from __future__ import annotations

from pathlib import Path

import pytest

from epip.core.kg_manager import BatchProcessor, KGManager, OperationType


@pytest.mark.asyncio
async def test_entity_lifecycle_and_relations():
    manager = KGManager()
    assert await manager.add_entity("Policy Alpha", "POLICY", status="draft")
    assert not await manager.add_entity("Policy Alpha", "POLICY")
    assert await manager.add_entity("Agency X", "AGENCY")

    assert await manager.update_entity("Policy Alpha", status="final", entity_type="POLICY")
    entities = await manager.list_entities()
    assert entities[0]["attributes"]["status"] == "final"

    assert await manager.add_relation("Agency X", "Policy Alpha", "SUPPORTS", confidence=0.9)
    relations = await manager.list_relations()
    assert relations[0]["type"] == "SUPPORTS"
    assert relations[0]["attributes"]["confidence"] == 0.9

    assert await manager.merge_entities("Policy Alpha", "Agency X")
    merged = await manager.list_entities()
    names = {entity["name"] for entity in merged}
    assert "Policy Alpha" not in names
    assert "Agency X" in names
    merged_entity = next(entity for entity in merged if entity["name"] == "Agency X")
    assert merged_entity["attributes"]["status"] == "final"

    assert await manager.delete_relation("Agency X", "Agency X")
    assert await manager.delete_entity("Agency X")
    assert not await manager.delete_entity("Agency X")

    audit = manager.list_audit_entries(limit=5)
    assert audit[-1].operation is OperationType.DELETE_ENTITY


@pytest.mark.asyncio
async def test_search_supports_regex_and_plain():
    manager = KGManager()
    await manager.add_entity("Department of Energy", "AGENCY", country="US")
    await manager.add_entity("财政部", "AGENCY", country="CN")

    plain = await manager.search_entities("energy")
    assert plain[0]["name"] == "Department of Energy"

    regex = await manager.search_entities("财.+部")
    assert regex[0]["name"] == "财政部"


@pytest.mark.asyncio
async def test_batch_processor_apply_and_rollback(tmp_path: Path):
    manager = KGManager()
    batch_file = tmp_path / "operations.yaml"
    batch_file.write_text(
        """
        operations:
          - operation: add_entity
            name: Alpha
            entity_type: POLICY
          - operation: add_entity
            name: Beta
            entity_type: POLICY
          - operation: add_relation
            source: Alpha
            target: Beta
            rel_type: ASSOCIATED_WITH
          - operation: delete_entity
            name: Missing
        """,
        encoding="utf-8",
    )

    processor = BatchProcessor(manager)
    operations = processor.load_operations(batch_file)
    errors = processor.validate_operations(operations)
    assert len(errors) == 0

    success, failure = await processor.apply_operations(operations, rollback_on_error=True)
    assert success == 3
    assert failure == 1
    entities = await manager.list_entities()
    assert entities == []

    success, failure = await processor.apply_operations(operations, rollback_on_error=False)
    assert success == 3
    assert failure == 1
    entities = await manager.list_entities()
    assert len(entities) == 2
