# Enterprise Policy Insight Platform (EPIP)

EPIP（Enterprise Policy Insight Platform）是一套围绕政策情报与知识治理打造的实验性平台，整合多租户管理、知识图谱推理与可视化监控能力，帮助团队快速搭建端到端的洞察系统。

## 项目概述与特性

- **多租户隔离**：内置 `X-Tenant-ID` 中间件与租户 CRUD API，可为每个组织配置独立资源与配额。
- **RBAC 扩展点**：API 层提供角色/权限钩子，与网关或自定义 AuthZ 服务组合实现精细化控制。
- **知识图谱引擎**：统一 Neo4j/Redis 存储，支持实体提取、链接与图检索的轻量 RAG 流程。
- **ReAct 推理链**：通过结构化计划描述步骤并记录中间结果，方便调试与复现。
- **幻觉检测**：将回答与验证报告映射为图节点，结合证据/冲突关系给出可信度提示。
- **可视化工具**：`/api/visualization/*` 端点输出轨迹、验证、证据图，前端可直接消费。
- **Prometheus 监控**：`/monitoring/metrics` 暴露核心指标，附带 liveness/readiness 探针。

## 系统要求

- Python 3.10+
- Node.js 18+（前端开发）
- Docker / Docker Compose
- Neo4j 5.x（可通过 docker-compose 预置）
- Redis 7+
- 阿里云 DashScope API（可选，用于 LLM 和 Embedding）

## 快速开始

### 本地开发

1. 创建虚拟环境并安装依赖：`make install`
2. 复制 `.env.example` 为 `.env`，填写 Neo4j、Redis、LLM Provider 等连接信息。
   - `.env` 支持两种 LLM 后端：本地 Ollama 或阿里云通义千问。
   - 当 `LLM_BINDING=openai` 时，将调用阿里云 DashScope API。
   - 请配置 `LLM_API_KEY`、`LLM_BASE_URL`、`EMBEDDING_API_KEY` 等必要变量。
3. 启动开发服务器：`make run`（默认监听 `http://127.0.0.1:8000`）
4. 验证：访问 `/health` 或 `/docs` 确认服务状态。

### Docker 部署

1. 构建镜像：`make docker-build`
2. 后台启动：`make docker-up`（可选 `make docker-up-llm` 同时拉起 Ollama）
3. 查看日志或健康检查：`make docker-logs` 或 `curl http://localhost:8000/health`
4. 关闭：`make docker-down`

### 前端开发

```bash
cd frontend
npm install
npm run dev    # 启动开发服务器，默认 http://localhost:5173
npm run build  # 生产构建
```

**技术栈**: React 18 + TypeScript + Vite + Tailwind CSS + Zustand

## 前端页面导航

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | Dashboard | 仪表盘概览，系统状态与统计 |
| `/query` | 查询中心 | 自然语言查询，知识图谱检索 |
| `/visualization` | 可视化 | 知识图谱、推理链可视化 |
| `/visualization/trace/:id` | 轨迹详情 | ReAct 推理步骤详情 |
| `/admin` | 管理中心 | 系统管理入口 |
| `/admin/tenants` | 租户管理 | 多租户 CRUD |
| `/admin/cache` | 缓存管理 | Redis 缓存查看与清理 |
| `/monitor` | 监控面板 | Prometheus 指标可视化 |

## 数据导入

使用 Light-RAG 构建知识图谱：

```bash
# 查看导入状态
python scripts/import_data.py --status

# 开始导入（支持断点续传）
python scripts/import_data.py

# 自定义参数
python scripts/import_data.py --timeout 900 --max-retries 3 --cooldown 5

# 重试失败文件
python scripts/import_data.py --retry-failed
```

导入脚本特性：
- **断点续传**：进度自动保存，中断后可继续
- **错误重试**：单文件最多重试 5 次，指数退避
- **中断安全**：Ctrl+C 安全退出

## API 端点速查表

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 聚合健康检查（应用 + Neo4j + Redis） |
| GET | `/api/status` | 返回部署环境与版本 |
| POST | `/api/query` | 执行查询/检索/推理流水线（需 `X-Tenant-ID`） |
| GET | `/api/cache/stats` | 查询缓存命中情况 |
| POST | `/api/cache/clear` | 按模式清理缓存 |
| CRUD | `/api/tenants/` | 管理租户实体（创建、列表、更新、删除） |
| GET | `/api/visualization/trace/{trace_id}` | 输出 ReAct 轨迹图数据 |
| GET | `/api/visualization/verification/{answer_id}` | 输出验证图谱 |
| GET | `/api/visualization/evidence/{node_id}` | 查看证据/冲突上下文 |
| POST | `/api/visualization/export` | 导出图为 JSON/SVG/Markdown |
| GET | `/monitoring/metrics` | Prometheus 指标（公开） |
| GET | `/monitoring/health/live` | Liveness Probe（公开） |
| GET | `/monitoring/health/ready` | Readiness Probe（公开） |

> 更完整的字段说明与示例请见 `docs/api-reference.md`。

## 配置参考

- `docs/configuration.md`：环境变量、Secret 与连接配置。
- `docs/deployment-guide.md`：部署拓扑、容器参数与优化建议。
- `docs/architecture.md`：模块划分、数据流与安全边界。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| LLM_BINDING | LLM 后端类型 | ollama |
| LLM_MODEL | 语言模型名称 | qwen-plus |
| LLM_BASE_URL | API 地址 | - |
| LLM_API_KEY | API 密钥 | - |
| EMBEDDING_MODEL | 嵌入模型 | text-embedding-v4 |
| NEO4J_PASSWORD | Neo4j 密码 | password |

## 开发指南（make 命令）

- `make install`：安装基础与开发依赖。
- `make run`：以 uvicorn 热重载模式运行 API。
- `make lint` / `make format`：执行 Ruff + mypy 检查与格式化。
- `make test`：运行 pytest 并输出覆盖率。
- `make docker-build` / `make docker-up` / `make docker-down`：容器化构建与生命周期管理。
- `make backup` / `make restore`：备份或恢复 Neo4j、Redis 数据卷。

## 文档索引

- `docs/`：主文档目录。
  - `docs/api-reference.md`：详细端点说明。
  - `docs/architecture.md`：系统架构。
  - `docs/prd.md`、`docs/stories/`：产品需求与故事列表。
  - `docs/test-strategy.md`、`docs/validation-report.md`：测试策略与验证记录。

## 许可证

本项目当前以 **UNLICENSED** 形式发布，尚未对外开放使用许可（见 `docker/Dockerfile` 中 `org.opencontainers.image.licenses` 标签）。如需获取授权，请联系项目维护者。
