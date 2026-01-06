# Story 1.2: Docker 环境与 Neo4j 配置

**Epic**: Epic 1 - 基础设施与 Light-RAG 集成
**优先级**: P0
**估算**: 中型

---

## 用户故事

**作为** 开发者，
**我想要** 容器化的开发环境和 Neo4j 数据库，
**以便** 快速启动和部署系统。

---

## 验收标准

### AC1: Dockerfile 创建
- [ ] 创建 `docker/Dockerfile`，基于 Python 3.10
- [ ] 使用多阶段构建减小镜像体积
- [ ] 配置非 root 用户运行应用
- [ ] 暴露端口 8000

### AC2: Docker Compose 编排
- [ ] 创建 `docker-compose.yml`
- [ ] 配置 Neo4j 服务（5-community 镜像）
- [ ] 配置 Redis 服务（7-alpine 镜像）
- [ ] 配置应用服务（依赖 Neo4j 和 Redis）
- [ ] 配置 Ollama 服务（可选）
- [ ] 配置持久化卷

### AC3: Neo4j 配置
- [ ] 启用 APOC 插件
- [ ] 启用 GDS 插件
- [ ] 配置认证（neo4j/password）
- [ ] 创建初始化脚本（约束和索引）

### AC4: 健康检查
- [ ] 实现 `/health` 端点
- [ ] 检查 Neo4j 连接状态
- [ ] 检查 Redis 连接状态
- [ ] 返回 JSON 格式的健康状态

### AC5: 文档
- [ ] 编写 Docker 启动指南（README 或单独文档）
- [ ] 说明环境变量配置
- [ ] 说明首次启动步骤

---

## 技术任务

### Task 1.2.1: 创建 Dockerfile
```dockerfile
# docker/Dockerfile
FROM python:3.10-slim as builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install build && python -m build --wheel

FROM python:3.10-slim

WORKDIR /app

# 创建非 root 用户
RUN useradd -m -u 1000 epip

# 安装依赖
COPY --from=builder /app/dist/*.whl .
RUN pip install *.whl && rm *.whl

# 复制源码
COPY src/ src/

# 切换用户
USER epip

EXPOSE 8000

CMD ["uvicorn", "epip.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Task 1.2.2: 创建 docker-compose.yml
```yaml
version: '3.8'

services:
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
      - REDIS_URL=redis://redis:6379
      - LLM_BACKEND=ollama
      - OLLAMA_URL=http://ollama:11434
    depends_on:
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ../dataset:/app/dataset:ro
      - ../data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.*
      - NEO4J_dbms_security_procedures_allowlist=apoc.*,gds.*
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - ./neo4j-init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7474"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    profiles:
      - llm

volumes:
  neo4j_data:
  neo4j_logs:
  redis_data:
  ollama_data:
```

### Task 1.2.3: 创建 Neo4j 初始化脚本
```cypher
// docker/neo4j-init/init.cypher

// 创建约束
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

// 创建索引
CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type);
CREATE INDEX document_hash IF NOT EXISTS FOR (d:Document) ON (d.file_hash);

// 向量索引将在运行时创建（需要数据）
```

### Task 1.2.4: 实现健康检查端点
```python
# src/epip/api/routes.py

from fastapi import APIRouter, Depends
from epip.db.neo4j_client import Neo4jClient
from epip.db.redis_client import RedisClient

router = APIRouter()

@router.get("/health")
async def health_check(
    neo4j: Neo4jClient = Depends(),
    redis: RedisClient = Depends()
) -> dict:
    """健康检查端点"""
    neo4j_ok = await neo4j.ping()
    redis_ok = await redis.ping()

    status = "healthy" if (neo4j_ok and redis_ok) else "unhealthy"

    return {
        "status": status,
        "services": {
            "neo4j": "up" if neo4j_ok else "down",
            "redis": "up" if redis_ok else "down"
        }
    }
```

### Task 1.2.5: 更新 Makefile
```makefile
# 添加 Docker 相关命令

docker-build:
	docker compose -f docker/docker-compose.yml build

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

docker-logs:
	docker compose -f docker/docker-compose.yml logs -f

docker-up-llm:
	docker compose -f docker/docker-compose.yml --profile llm up -d
```

---

## 测试用例

### 集成测试
- [ ] 测试 `docker compose up` 所有服务启动成功
- [ ] 测试 Neo4j 健康检查通过
- [ ] 测试 Redis 健康检查通过
- [ ] 测试 `/health` 端点返回正确状态
- [ ] 测试 Neo4j APOC 插件可用：`CALL apoc.help('apoc')`
- [ ] 测试 Neo4j GDS 插件可用：`CALL gds.list()`

### 冒烟测试
- [ ] 从全新环境执行 `docker compose up`，10 分钟内所有服务就绪

---

## 依赖关系

- **前置**: Story 1.1（项目结构）
- **后置**: Story 1.3, 1.4

---

## 相关文档

- 架构: `docs/architecture.md` 第 9 节（部署架构）
- Docker Compose 配置: `docs/architecture.md` 9.1 节
