# Story 1.1: 项目初始化与开发环境配置

**Epic**: Epic 1 - 基础设施与 Light-RAG 集成
**优先级**: P0
**估算**: 小型

---

## 用户故事

**作为** 开发者，
**我想要** 一个标准化的项目结构和开发环境，
**以便** 团队可以统一开发和部署。

---

## 验收标准

### AC1: 项目结构创建
- [ ] 创建 `src/epip/` 目录结构，包含 `__init__.py`
- [ ] 创建 `src/epip/api/` 模块（routes.py, schemas.py, dependencies.py）
- [ ] 创建 `src/epip/core/` 模块（data_processor.py, kg_builder.py, query_engine.py, hallucination.py）
- [ ] 创建 `src/epip/db/` 模块（neo4j_client.py, redis_client.py）
- [ ] 创建 `src/epip/utils/` 模块（logging.py, helpers.py）
- [ ] 创建 `src/epip/main.py` 和 `src/epip/config.py`

### AC2: 依赖管理配置
- [ ] 创建 `pyproject.toml`，配置项目元数据
- [ ] 定义核心依赖：pandas, neo4j, sentence-transformers, fastapi, uvicorn, redis, structlog
- [ ] 定义开发依赖：pytest, pytest-cov, ruff, mypy, testcontainers
- [ ] 创建 `requirements.txt`（从 pyproject.toml 导出）

### AC3: 开发工具配置
- [ ] 配置 ruff（pyproject.toml [tool.ruff]）
- [ ] 配置 mypy（pyproject.toml [tool.mypy]）
- [ ] 配置 pytest（pyproject.toml [tool.pytest.ini_options]）

### AC4: 标准文件创建
- [ ] 更新 `.gitignore`（Python、IDE、环境文件）
- [ ] 创建 `.env.example`（环境变量模板）
- [ ] 创建 `Makefile`（install, test, lint, format, run 命令）

### AC5: 文档
- [ ] 更新 `README.md`（项目说明、快速开始、开发指南）

---

## 技术任务

### Task 1.1.1: 创建项目目录结构
```bash
# 预期结构
src/
└── epip/
    ├── __init__.py
    ├── main.py
    ├── config.py
    ├── api/
    │   ├── __init__.py
    │   ├── routes.py
    │   ├── schemas.py
    │   └── dependencies.py
    ├── core/
    │   ├── __init__.py
    │   ├── data_processor.py
    │   ├── kg_builder.py
    │   ├── query_engine.py
    │   └── hallucination.py
    ├── db/
    │   ├── __init__.py
    │   ├── neo4j_client.py
    │   └── redis_client.py
    └── utils/
        ├── __init__.py
        ├── logging.py
        └── helpers.py
```

### Task 1.1.2: 配置 pyproject.toml
```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "epip"
version = "0.1.0"
description = "Enterprise Policy Insight Platform"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0",
    "neo4j>=5.0",
    "sentence-transformers>=2.0",
    "fastapi>=0.100",
    "uvicorn>=0.20",
    "redis>=4.0",
    "structlog>=23.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.21",
    "ruff>=0.1",
    "mypy>=1.0",
    "testcontainers>=3.0",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.10"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

### Task 1.1.3: 创建 Makefile
```makefile
.PHONY: install test lint format run clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=src/epip --cov-report=term-missing

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

run:
	uvicorn epip.main:app --reload

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
```

### Task 1.1.4: 创建 .env.example
```env
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Redis
REDIS_URL=redis://localhost:6379

# LLM Backend
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434
OPENAI_API_KEY=

# Application
LOG_LEVEL=INFO
DEBUG=false
```

### Task 1.1.5: 创建测试目录结构
```bash
tests/
├── __init__.py
├── conftest.py
├── unit/
│   ├── __init__.py
│   ├── test_data_processor.py
│   ├── test_kg_builder.py
│   ├── test_query_engine.py
│   └── test_hallucination.py
└── integration/
    ├── __init__.py
    ├── test_api.py
    └── test_pipeline.py
```

---

## 测试用例

### 单元测试
- [ ] 测试项目可正确导入：`from epip import __version__`
- [ ] 测试配置加载：`from epip.config import settings`

### 集成测试
- [ ] 测试 `make install` 成功执行
- [ ] 测试 `make lint` 无错误
- [ ] 测试 `make test` 基础测试通过

---

## 依赖关系

- **前置**: 无
- **后置**: Story 1.2, 1.3, 1.4

---

## 相关文档

- 架构: `docs/architecture.md` 第 8 节（项目结构）
- 编码标准: `docs/architecture.md` 第 11 节
