"""Knowledge graph management utilities for manual curation tasks."""

from __future__ import annotations

import asyncio
import copy
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)


class OperationType(str, Enum):
    """Supported knowledge-graph operation identifiers."""

    ADD_ENTITY = "add_entity"
    DELETE_ENTITY = "delete_entity"
    UPDATE_ENTITY = "update_entity"
    ADD_RELATION = "add_relation"
    DELETE_RELATION = "delete_relation"
    MERGE_ENTITIES = "merge_entities"
    BATCH_VALIDATE = "batch_validate"
    BATCH_APPLY = "batch_apply"

    @classmethod
    def from_value(cls, value: str) -> OperationType:
        normalized = value.lower().strip()
        try:
            return cls(normalized)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unsupported operation: {value}") from exc


@dataclass(slots=True)
class AuditEntry:
    """Captured result of a knowledge-graph operation."""

    timestamp: datetime
    operation: OperationType
    target: str
    success: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation.value,
            "target": self.target,
            "success": self.success,
            "details": copy.deepcopy(self.details),
        }


class KGManager:
    """In-memory knowledge-graph state container with audit logging."""

    def __init__(self) -> None:
        self._entities: dict[str, dict[str, Any]] = {}
        self._relations: list[dict[str, Any]] = []
        self._audit_log: list[AuditEntry] = []
        self._lock = asyncio.Lock()

    async def add_entity(self, name: str, entity_type: str, **attrs: Any) -> bool:
        payload = {
            "name": name,
            "entity_type": entity_type,
            "attributes": copy.deepcopy(attrs),
        }
        async with self._lock:
            if name in self._entities:
                self._log_operation(
                    AuditEntry(
                        timestamp=datetime.now(timezone.utc),
                        operation=OperationType.ADD_ENTITY,
                        target=name,
                        success=False,
                        details={"reason": "exists"},
                    )
                )
                return False
            self._entities[name] = payload

        self._log_operation(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                operation=OperationType.ADD_ENTITY,
                target=name,
                success=True,
                details={"entity_type": entity_type, "attributes": copy.deepcopy(attrs)},
            )
        )
        return True

    async def delete_entity(self, name: str) -> bool:
        async with self._lock:
            existed = name in self._entities
            if existed:
                del self._entities[name]
                self._relations = [
                    relation
                    for relation in self._relations
                    if relation["source"] != name and relation["target"] != name
                ]

        self._log_operation(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                operation=OperationType.DELETE_ENTITY,
                target=name,
                success=existed,
            )
        )
        return existed

    async def update_entity(self, name: str, **updates: Any) -> bool:
        if not updates:
            return False
        async with self._lock:
            entity = self._entities.get(name)
            if entity is None:
                success = False
            else:
                if "entity_type" in updates:
                    entity["entity_type"] = str(updates.pop("entity_type"))
                attributes = entity.setdefault("attributes", {})
                attributes.update(updates)
                success = True

        self._log_operation(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                operation=OperationType.UPDATE_ENTITY,
                target=name,
                success=success,
                details={"updates": copy.deepcopy(updates)},
            )
        )
        return success

    async def add_relation(self, source: str, target: str, rel_type: str, **attrs: Any) -> bool:
        async with self._lock:
            if source not in self._entities or target not in self._entities:
                success = False
            else:
                relation = {
                    "source": source,
                    "target": target,
                    "type": rel_type,
                    "attributes": copy.deepcopy(attrs),
                }
                self._relations.append(relation)
                success = True

        self._log_operation(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                operation=OperationType.ADD_RELATION,
                target=f"{source}->{target}",
                success=success,
                details={"relation_type": rel_type, "attributes": copy.deepcopy(attrs)},
            )
        )
        return success

    async def delete_relation(self, source: str, target: str, rel_type: str | None = None) -> bool:
        async with self._lock:
            before = len(self._relations)
            self._relations = [
                relation
                for relation in self._relations
                if not (
                    relation["source"] == source
                    and relation["target"] == target
                    and (rel_type is None or relation["type"] == rel_type)
                )
            ]
            removed = before - len(self._relations)

        self._log_operation(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                operation=OperationType.DELETE_RELATION,
                target=f"{source}->{target}",
                success=removed > 0,
                details={"relation_type": rel_type},
            )
        )
        return removed > 0

    async def merge_entities(self, source: str, target: str) -> bool:
        async with self._lock:
            source_entity = self._entities.get(source)
            target_entity = self._entities.get(target)
            if source_entity is None or target_entity is None:
                success = False
            else:
                merged_attrs = copy.deepcopy(source_entity.get("attributes", {}))
                merged_attrs.update(target_entity.get("attributes", {}))
                target_entity["attributes"] = merged_attrs
                for relation in self._relations:
                    if relation["source"] == source:
                        relation["source"] = target
                    if relation["target"] == source:
                        relation["target"] = target
                del self._entities[source]
                success = True

        self._log_operation(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                operation=OperationType.MERGE_ENTITIES,
                target=f"{source}->{target}",
                success=success,
            )
        )
        return success

    async def list_entities(
        self, entity_type: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        async with self._lock:
            entities = list(self._entities.values())
        if entity_type:
            entities = [entity for entity in entities if entity["entity_type"] == entity_type]
        return [copy.deepcopy(entity) for entity in entities[: max(limit, 0)]]

    async def search_entities(self, pattern: str) -> list[dict[str, Any]]:
        async with self._lock:
            entities = list(self._entities.values())

        def matches(value: str) -> bool:
            value_text = value.lower()
            return needle in value_text if plain_search else bool(regex and regex.search(value))

        try:
            regex = re.compile(pattern, re.IGNORECASE)
            plain_search = False
            needle = ""
        except re.error:
            regex = None
            plain_search = True
            needle = pattern.lower()

        results: list[dict[str, Any]] = []
        for entity in entities:
            name = entity.get("name", "")
            if (regex and regex.search(name)) or (plain_search and needle in name.lower()):
                results.append(copy.deepcopy(entity))
                continue
            attributes = entity.get("attributes", {})
            for value in attributes.values():
                text = str(value)
                if matches(text):
                    results.append(copy.deepcopy(entity))
                    break
        return results

    async def list_relations(
        self, source: str | None = None, target: str | None = None
    ) -> list[dict[str, Any]]:
        async with self._lock:
            relations = list(self._relations)

        def include(relation: dict[str, Any]) -> bool:
            if source and relation["source"] != source:
                return False
            if target and relation["target"] != target:
                return False
            return True

        return [copy.deepcopy(relation) for relation in relations if include(relation)]

    def list_audit_entries(self, limit: int = 100) -> list[AuditEntry]:
        return list(self._audit_log[-limit:])

    def _snapshot_state(self) -> dict[str, Any]:
        return {
            "entities": copy.deepcopy(self._entities),
            "relations": copy.deepcopy(self._relations),
            "audit": list(self._audit_log),
        }

    async def _restore_state(self, snapshot: dict[str, Any]) -> None:
        async with self._lock:
            self._entities = copy.deepcopy(snapshot["entities"])
            self._relations = copy.deepcopy(snapshot["relations"])
            self._audit_log = list(snapshot["audit"])

    def _log_operation(self, entry: AuditEntry) -> None:
        self._audit_log.append(entry)
        logger.info(
            "kg_operation",
            operation=entry.operation.value,
            target=entry.target,
            success=entry.success,
            details=entry.details,
        )


@dataclass(slots=True)
class BatchOperation:
    """Describes a batch entry loaded from disk."""

    index: int
    operation: OperationType
    payload: dict[str, Any]
    description: str | None = None


class BatchProcessor:
    """Batch command processor that applies operations sequentially."""

    def __init__(self, manager: KGManager) -> None:
        self.manager = manager

    def load_operations(self, path: str | Path) -> list[BatchOperation]:
        file_path = Path(path)
        content = file_path.read_text(encoding="utf-8")
        raw = yaml.safe_load(content) or []
        if isinstance(raw, dict):
            candidates = raw.get("operations", [])
        elif isinstance(raw, list):
            candidates = raw
        else:  # pragma: no cover - defensive guard
            raise ValueError("Unsupported YAML structure for batch operations")

        operations: list[BatchOperation] = []
        for index, entry in enumerate(candidates, start=1):
            if not isinstance(entry, dict):
                raise ValueError(f"Operation #{index} must be a mapping")
            op_value = entry.get("operation") or entry.get("type")
            if not op_value:
                raise ValueError(f"Operation #{index} is missing an 'operation' field")
            operation = OperationType.from_value(str(op_value))
            description = entry.get("description")
            payload = {
                key: value
                for key, value in entry.items()
                if key not in {"operation", "type", "description"}
            }
            operations.append(
                BatchOperation(
                    index=index,
                    operation=operation,
                    payload=payload,
                    description=description,
                )
            )
        return operations

    def validate_operations(self, operations: list[BatchOperation]) -> list[str]:
        errors: list[str] = []
        requirements: dict[OperationType, tuple[str, ...]] = {
            OperationType.ADD_ENTITY: ("name", "entity_type"),
            OperationType.DELETE_ENTITY: ("name",),
            OperationType.UPDATE_ENTITY: ("name",),
            OperationType.ADD_RELATION: ("source", "target", "rel_type"),
            OperationType.DELETE_RELATION: ("source", "target"),
            OperationType.MERGE_ENTITIES: ("source", "target"),
        }
        for operation in operations:
            required = requirements.get(operation.operation, ())
            missing = [field for field in required if field not in operation.payload]
            if missing:
                message = (
                    f"Operation #{operation.index} ({operation.operation.value}) is missing: "
                    f"{', '.join(missing)}"
                )
                errors.append(message)
        self.manager._log_operation(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                operation=OperationType.BATCH_VALIDATE,
                target="batch",
                success=not errors,
                details={"count": len(operations), "errors": errors},
            )
        )
        return errors

    async def apply_operations(
        self, operations: list[BatchOperation], rollback_on_error: bool = True
    ) -> tuple[int, int]:
        snapshot = self.manager._snapshot_state()
        success_count = 0
        failure_count = 0
        for operation in operations:
            op_success = await self._execute(operation)
            if op_success:
                success_count += 1
                continue
            failure_count += 1
            if rollback_on_error:
                await self.manager._restore_state(snapshot)
                break

        self.manager._log_operation(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                operation=OperationType.BATCH_APPLY,
                target="batch",
                success=failure_count == 0,
                details={
                    "count": len(operations),
                    "success": success_count,
                    "failed": failure_count,
                    "rollback": rollback_on_error and failure_count > 0,
                },
            )
        )
        return success_count, failure_count

    async def _execute(self, operation: BatchOperation) -> bool:
        payload = operation.payload
        op_type = operation.operation
        if op_type is OperationType.ADD_ENTITY:
            attrs = _extract_attributes(payload)
            return await self.manager.add_entity(payload["name"], payload["entity_type"], **attrs)
        if op_type is OperationType.DELETE_ENTITY:
            return await self.manager.delete_entity(payload["name"])
        if op_type is OperationType.UPDATE_ENTITY:
            updates = _extract_attributes(payload)
            if "entity_type" in payload:
                updates["entity_type"] = payload["entity_type"]
            return await self.manager.update_entity(payload["name"], **updates)
        if op_type is OperationType.ADD_RELATION:
            attrs = _extract_attributes(payload)
            return await self.manager.add_relation(
                payload["source"], payload["target"], payload["rel_type"], **attrs
            )
        if op_type is OperationType.DELETE_RELATION:
            return await self.manager.delete_relation(
                payload["source"], payload["target"], payload.get("rel_type")
            )
        if op_type is OperationType.MERGE_ENTITIES:
            return await self.manager.merge_entities(payload["source"], payload["target"])
        logger.warning("Unsupported operation in batch", operation=op_type.value)
        return False


def _extract_attributes(payload: dict[str, Any]) -> dict[str, Any]:
    attrs = payload.get("attributes") or payload.get("attrs") or {}
    if not isinstance(attrs, dict):
        raise ValueError("Attributes payload must be a dictionary")
    base = copy.deepcopy(attrs)
    for key, value in payload.items():
        if key not in {"name", "entity_type", "source", "target", "rel_type"}:
            if key not in {"attributes", "attrs", "description"}:
                base[key] = value
    return base
