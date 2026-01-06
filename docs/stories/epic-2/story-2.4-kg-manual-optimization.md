# Story 2.4: KG 手动优化界面

**Epic**: Epic 2 - 知识图谱构建与优化
**优先级**: P1
**估算**: 中型

---

## 用户故事

**作为** 知识工程师，
**我想要** 通过命令行界面手动调整 KG，
**以便** 修正自动化流程的错误。

---

## 验收标准

### AC1: 实体操作命令
- [ ] `kg entity add <name> --type <type>` 添加实体
- [ ] `kg entity delete <name>` 删除实体
- [ ] `kg entity update <name> --type <new_type>` 修改实体类型
- [ ] `kg entity list [--type <type>] [--limit N]` 列出实体
- [ ] `kg entity search <pattern>` 搜索实体

### AC2: 关系操作命令
- [ ] `kg relation add <source> <target> --type <rel_type>` 添加关系
- [ ] `kg relation delete <source> <target> [--type <rel_type>]` 删除关系
- [ ] `kg relation list [--source <name>] [--target <name>]` 列出关系
- [ ] 支持关系属性设置

### AC3: 实体合并命令
- [ ] `kg merge <entity1> <entity2>` 合并两个实体
- [ ] 自动迁移所有关系到目标实体
- [ ] 保留合并历史记录

### AC4: 审计日志
- [ ] 记录所有修改操作到日志文件
- [ ] 包含：时间戳、操作类型、操作者、详情
- [ ] 支持 JSON 格式日志
- [ ] `kg audit list [--since <date>]` 查看审计日志

### AC5: 批量操作
- [ ] `kg batch apply <file.yaml>` 从配置文件执行批量操作
- [ ] `kg batch validate <file.yaml>` 验证配置文件
- [ ] 支持 YAML 和 JSON 格式
- [ ] 支持事务回滚（失败时撤销所有操作）

---

## 技术任务

### Task 2.4.1: KG 操作管理器
```python
# src/epip/core/kg_manager.py

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

class OperationType(Enum):
    ADD_ENTITY = "add_entity"
    DELETE_ENTITY = "delete_entity"
    UPDATE_ENTITY = "update_entity"
    ADD_RELATION = "add_relation"
    DELETE_RELATION = "delete_relation"
    MERGE_ENTITIES = "merge_entities"

@dataclass
class AuditEntry:
    """审计日志条目"""
    timestamp: datetime
    operation: OperationType
    operator: str
    details: dict
    success: bool
    error: str | None = None

class KGManager:
    """知识图谱管理器"""

    def __init__(self, kg_builder: KGBuilder, audit_path: Path):
        self.kg_builder = kg_builder
        self.audit_path = audit_path
        self._audit_log: list[AuditEntry] = []

    async def add_entity(self, name: str, entity_type: str, **attrs) -> bool:
        """添加实体"""
        pass

    async def delete_entity(self, name: str) -> bool:
        """删除实体及其所有关系"""
        pass

    async def update_entity(self, name: str, **updates) -> bool:
        """更新实体属性"""
        pass

    async def add_relation(
        self, source: str, target: str, rel_type: str, **attrs
    ) -> bool:
        """添加关系"""
        pass

    async def delete_relation(
        self, source: str, target: str, rel_type: str | None = None
    ) -> bool:
        """删除关系"""
        pass

    async def merge_entities(self, source: str, target: str) -> bool:
        """合并实体"""
        pass

    async def list_entities(
        self, entity_type: str | None = None, limit: int = 100
    ) -> list[dict]:
        """列出实体"""
        pass

    async def search_entities(self, pattern: str) -> list[dict]:
        """搜索实体"""
        pass

    async def list_relations(
        self, source: str | None = None, target: str | None = None
    ) -> list[dict]:
        """列出关系"""
        pass

    def _log_operation(self, entry: AuditEntry) -> None:
        """记录审计日志"""
        pass
```

### Task 2.4.2: 批量操作处理器
```python
# src/epip/core/kg_manager.py (续)

@dataclass
class BatchOperation:
    """批量操作定义"""
    operation: OperationType
    params: dict

class BatchProcessor:
    """批量操作处理器"""

    def __init__(self, manager: KGManager):
        self.manager = manager

    def load_operations(self, path: Path) -> list[BatchOperation]:
        """从文件加载操作"""
        pass

    def validate_operations(self, operations: list[BatchOperation]) -> list[str]:
        """验证操作有效性"""
        pass

    async def apply_operations(
        self,
        operations: list[BatchOperation],
        rollback_on_error: bool = True
    ) -> tuple[int, int]:  # (success, failed)
        """执行批量操作"""
        pass
```

### Task 2.4.3: CLI 入口
```python
# scripts/kg_cli.py

import click

@click.group()
def cli():
    """EPIP Knowledge Graph Management CLI"""
    pass

@cli.group()
def entity():
    """Entity operations"""
    pass

@entity.command("add")
@click.argument("name")
@click.option("--type", "entity_type", required=True)
def entity_add(name: str, entity_type: str):
    """Add a new entity"""
    pass

@entity.command("delete")
@click.argument("name")
def entity_delete(name: str):
    """Delete an entity"""
    pass

# ... 其他命令
```

### Task 2.4.4: 更新依赖
```toml
# pyproject.toml
dependencies = [
    # ... 现有 ...
    "click>=8.0",
    "pyyaml>=6.0",
]

[project.scripts]
epip-kg = "scripts.kg_cli:cli"
```

---

## 批量操作文件格式

```yaml
# operations.yaml
operations:
  - operation: add_entity
    params:
      name: "香港医院管理局"
      type: "ORGANIZATION"
      attributes:
        alias: "HA"

  - operation: add_relation
    params:
      source: "香港医院管理局"
      target: "医务卫生局"
      type: "REPORTS_TO"

  - operation: merge_entities
    params:
      source: "Hospital Authority"
      target: "香港医院管理局"
```

---

## 测试用例

### 单元测试
- [ ] 测试 `add_entity()` 创建实体
- [ ] 测试 `delete_entity()` 级联删除关系
- [ ] 测试 `merge_entities()` 关系迁移
- [ ] 测试审计日志记录
- [ ] 测试批量操作加载和验证

### 集成测试
- [ ] 测试完整 CLI 流程
- [ ] 测试批量操作事务回滚
- [ ] 测试并发操作冲突处理

### 验收测试
- [ ] 所有 CLI 命令可正常执行
- [ ] 审计日志完整记录所有操作
- [ ] 批量操作支持回滚

---

## 依赖关系

- **前置**: Story 2.3（需要有关系数据才能操作）
- **后置**: Story 2.5（质量评估使用手动优化后的数据）

---

## 相关文档

- 架构: `docs/architecture.md`
- KG: `src/epip/core/kg_builder.py`
- 实体: `src/epip/core/entity_extractor.py`
- 关系: `src/epip/core/relation_extractor.py`
