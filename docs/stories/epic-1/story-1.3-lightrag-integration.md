# Story 1.3: Light-RAG 框架集成

**Epic**: Epic 1 - 基础设施与 Light-RAG 集成
**优先级**: P0
**估算**: 大型

---

## 用户故事

**作为** 开发者，
**我想要** 集成 Light-RAG 框架并配置其核心组件，
**以便** 后续可以使用 Light-RAG 处理数据和构建知识图谱。

---

## 验收标准

### AC1: Light-RAG 安装与配置
- [ ] 安装 Light-RAG 库（HKUDS/LightRAG）
- [ ] 创建 Light-RAG 配置类 `LightRAGConfig`
- [ ] 支持从环境变量加载配置
- [ ] 支持配置文件覆盖

### AC2: Neo4j 存储后端配置
- [ ] 配置 Light-RAG 使用 Neo4j 作为图存储后端
- [ ] 验证 Light-RAG 与 Neo4j 的连接
- [ ] 实现 Neo4j 客户端封装

### AC3: LLM 后端配置
- [ ] 支持 Ollama 本地 LLM
- [ ] 支持 OpenAI API（可选）
- [ ] 实现 LLM 后端策略模式，支持切换
- [ ] 配置超时和重试机制

### AC4: 嵌入模型配置
- [ ] 配置 sentence-transformers 嵌入模型
- [ ] 支持自定义嵌入模型路径
- [ ] 验证嵌入生成功能

### AC5: 基础功能验证
- [ ] 验证文档插入功能（insert）
- [ ] 验证基础查询功能（query）
- [ ] 输出集成验证报告

### AC6: 配置文档
- [ ] 编写 Light-RAG 配置文档
- [ ] 说明各参数含义和调优建议

---

## 技术任务

### Task 1.3.1: 安装 Light-RAG
```bash
# 添加到 pyproject.toml
# lightrag-hku>=0.1.0  (或从 GitHub 安装)

pip install lightrag-hku
# 或
pip install git+https://github.com/HKUDS/LightRAG.git
```

### Task 1.3.2: 创建 Light-RAG 配置
```python
# src/epip/config.py

from pydantic_settings import BaseSettings
from typing import Literal, Optional

class LightRAGConfig(BaseSettings):
    """Light-RAG 配置"""

    # 存储配置
    working_dir: str = "./data/lightrag"
    graph_storage: Literal["neo4j", "networkx"] = "neo4j"

    # Neo4j 配置
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # LLM 配置
    llm_backend: Literal["ollama", "openai"] = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # 嵌入配置
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # 处理配置
    chunk_size: int = 1200
    chunk_overlap: int = 100
    max_tokens: int = 32768

    class Config:
        env_prefix = "LIGHTRAG_"
        env_file = ".env"
```

### Task 1.3.3: 实现 LLM 后端策略
```python
# src/epip/core/llm_backend.py

from abc import ABC, abstractmethod
from typing import AsyncIterator

class LLMBackend(ABC):
    """LLM 后端抽象基类"""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """生成响应"""
        pass

    @abstractmethod
    async def generate_stream(self, prompt: str) -> AsyncIterator[str]:
        """流式生成响应"""
        pass

class OllamaBackend(LLMBackend):
    """Ollama 本地 LLM 后端"""

    def __init__(self, url: str, model: str):
        self.url = url
        self.model = model

    async def generate(self, prompt: str) -> str:
        # 实现 Ollama API 调用
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/api/generate",
                json={"model": self.model, "prompt": prompt},
                timeout=120.0
            )
            return response.json()["response"]

class OpenAIBackend(LLMBackend):
    """OpenAI API 后端"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str) -> str:
        # 实现 OpenAI API 调用
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

def create_llm_backend(config: "LightRAGConfig") -> LLMBackend:
    """工厂函数创建 LLM 后端"""
    if config.llm_backend == "ollama":
        return OllamaBackend(config.ollama_url, config.ollama_model)
    elif config.llm_backend == "openai":
        return OpenAIBackend(config.openai_api_key, config.openai_model)
    else:
        raise ValueError(f"Unknown LLM backend: {config.llm_backend}")
```

### Task 1.3.4: 实现 KGBuilder 封装
```python
# src/epip/core/kg_builder.py

from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
import structlog

from lightrag import LightRAG, QueryParam
from lightrag.llm import ollama_model_complete, openai_complete_if_cache
from lightrag.utils import EmbeddingFunc

from epip.config import LightRAGConfig

logger = structlog.get_logger()

@dataclass
class InsertResult:
    """插入结果"""
    file_count: int
    entity_count: int
    relation_count: int
    errors: List[str]

@dataclass
class KGStats:
    """KG 统计信息"""
    total_entities: int
    total_relations: int
    entity_types: dict
    relation_types: dict

class KGBuilder:
    """知识图谱构建器 - Light-RAG 封装"""

    def __init__(self, config: LightRAGConfig):
        self.config = config
        self.rag: Optional[LightRAG] = None
        self._initialize()

    def _initialize(self):
        """初始化 Light-RAG 实例"""
        # 配置 LLM 函数
        if self.config.llm_backend == "ollama":
            llm_func = ollama_model_complete
        else:
            llm_func = openai_complete_if_cache

        # 配置嵌入函数
        embedding_func = EmbeddingFunc(
            embedding_dim=self.config.embedding_dim,
            max_token_size=8192,
            func=self._get_embedding_func()
        )

        # 创建 Light-RAG 实例
        self.rag = LightRAG(
            working_dir=self.config.working_dir,
            llm_model_func=llm_func,
            embedding_func=embedding_func,
            # Neo4j 配置
            graph_storage="Neo4JStorage",
            log_level="INFO"
        )

        logger.info("KGBuilder initialized", config=self.config.model_dump())

    def _get_embedding_func(self):
        """获取嵌入函数"""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(self.config.embedding_model)

        async def embedding_func(texts: List[str]) -> List[List[float]]:
            embeddings = model.encode(texts)
            return embeddings.tolist()

        return embedding_func

    async def insert_documents(self, files: List[Path]) -> InsertResult:
        """批量导入文档"""
        errors = []
        for file in files:
            try:
                content = file.read_text(encoding="utf-8")
                await self.rag.ainsert(content)
                logger.info("Document inserted", file=str(file))
            except Exception as e:
                errors.append(f"{file}: {e}")
                logger.error("Insert failed", file=str(file), error=str(e))

        stats = await self.get_statistics()
        return InsertResult(
            file_count=len(files) - len(errors),
            entity_count=stats.total_entities,
            relation_count=stats.total_relations,
            errors=errors
        )

    def configure(self, **params):
        """更新配置参数"""
        for key, value in params.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._initialize()

    async def get_statistics(self) -> KGStats:
        """获取 KG 统计信息"""
        # 从 Neo4j 查询统计
        # 具体实现依赖 Neo4j 客户端
        return KGStats(
            total_entities=0,
            total_relations=0,
            entity_types={},
            relation_types={}
        )

    async def query(self, question: str, mode: str = "hybrid") -> str:
        """执行查询"""
        return await self.rag.aquery(
            question,
            param=QueryParam(mode=mode)
        )
```

### Task 1.3.5: 创建集成验证脚本
```python
# scripts/verify_lightrag.py

import asyncio
from pathlib import Path
from epip.config import LightRAGConfig
from epip.core.kg_builder import KGBuilder

async def verify_integration():
    """验证 Light-RAG 集成"""
    print("=" * 50)
    print("Light-RAG Integration Verification")
    print("=" * 50)

    # 1. 配置加载
    print("\n[1] Loading configuration...")
    config = LightRAGConfig()
    print(f"    LLM Backend: {config.llm_backend}")
    print(f"    Neo4j URI: {config.neo4j_uri}")
    print(f"    Embedding Model: {config.embedding_model}")

    # 2. 初始化
    print("\n[2] Initializing KGBuilder...")
    builder = KGBuilder(config)
    print("    KGBuilder initialized successfully")

    # 3. 测试插入
    print("\n[3] Testing document insertion...")
    test_doc = Path("/tmp/test_doc.txt")
    test_doc.write_text("This is a test document about Hong Kong health statistics.")

    result = await builder.insert_documents([test_doc])
    print(f"    Inserted: {result.file_count} files")
    print(f"    Errors: {len(result.errors)}")

    # 4. 测试查询
    print("\n[4] Testing query...")
    response = await builder.query("What is this document about?")
    print(f"    Response: {response[:100]}...")

    # 5. 清理
    test_doc.unlink()

    print("\n" + "=" * 50)
    print("Verification PASSED")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(verify_integration())
```

---

## 测试用例

### 单元测试
- [ ] 测试 `LightRAGConfig` 从环境变量加载
- [ ] 测试 `LightRAGConfig` 默认值
- [ ] 测试 `create_llm_backend()` Ollama 创建
- [ ] 测试 `create_llm_backend()` OpenAI 创建
- [ ] 测试 `KGBuilder` 初始化

### 集成测试
- [ ] 测试 Light-RAG 连接 Neo4j
- [ ] 测试文档插入流程
- [ ] 测试基础查询流程
- [ ] 测试 LLM 后端切换

### 验证测试
- [ ] 运行 `scripts/verify_lightrag.py` 全部通过

---

## 依赖关系

- **前置**: Story 1.1, Story 1.2（需要 Neo4j 运行）
- **后置**: Story 1.4, Epic 2

---

## 相关文档

- 架构: `docs/architecture.md` 5.2 节（KGBuilder 组件）
- Light-RAG GitHub: https://github.com/HKUDS/LightRAG
