# 配置参考

## 概述
EPIP 的所有运行配置均集中在 `src/epip/config.py`，借助 Pydantic `BaseSettings` 自动从环境变量和 `.env`/`.env.local` 文件注入值。每个配置类都定义了字段、默认值以及对应的环境变量名称（类上若声明 `env_prefix`，则实际变量名会附加该前缀）。本指南汇总所有可用配置项、用途及默认值，便于快速查阅与编写 `.env`。

## 基础配置（`Settings`）
| 字段 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `environment` | `ENVIRONMENT` | `development` | 服务运行环境标签，可用于区分 development / staging / production。 |
| `debug` | `DEBUG` | `False` | 是否开启调试模式，开启后会打印更详细的日志。 |
| `log_level` | `LOG_LEVEL` | `INFO` | 全局日志级别（如 `DEBUG`、`INFO`、`WARNING`）。 |
| `neo4j_uri` | `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt 连接地址。 |
| `neo4j_user` | `NEO4J_USER` | `neo4j` | Neo4j 登录用户名。 |
| `neo4j_password` | `NEO4J_PASSWORD` | `password` | Neo4j 登录密码。 |
| `redis_url` | `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接串，用于缓存与队列。 |
| `llm_backend` | `LLM_BACKEND` | `ollama` | 推理所用 LLM 类型，支持 `ollama` 或 `openai`。 |
| `ollama_url` | `OLLAMA_URL` | `http://localhost:11434` | 本地 Ollama 服务地址。 |
| `openai_api_key` | `OPENAI_API_KEY` | `None` | OpenAI API Key，无需时可留空。 |

## LightRAG 配置
| 字段 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `working_dir` | `LIGHTRAG_WORKING_DIR` | `./data/lightrag` | LightRAG 中间文件与缓存目录。 |
| `graph_storage` | `LIGHTRAG_GRAPH_STORAGE` | `neo4j` | 图存储后端，可选 `neo4j` 或 `networkx`。 |
| `neo4j_uri` | `LIGHTRAG_NEO4J_URI` | `bolt://localhost:7687` | LightRAG 专用 Neo4j 连接。 |
| `neo4j_user` | `LIGHTRAG_NEO4J_USER` | `neo4j` | LightRAG 连接 Neo4j 的用户名。 |
| `neo4j_password` | `LIGHTRAG_NEO4J_PASSWORD` | `password` | LightRAG 连接 Neo4j 的密码。 |
| `llm_backend` | `LIGHTRAG_LLM_BACKEND` | `ollama` | LightRAG 推理所用 LLM 类型。 |
| `ollama_url` | `LIGHTRAG_OLLAMA_URL` | `http://localhost:11434` | LightRAG 调用 Ollama 的地址。 |
| `ollama_model` | `LIGHTRAG_OLLAMA_MODEL` | `llama3.2` | LightRAG 使用的 Ollama 模型名称。 |
| `openai_api_key` | `LIGHTRAG_OPENAI_API_KEY` | `None` | LightRAG 若走 OpenAI，则需提供 Key。 |
| `openai_model` | `LIGHTRAG_OPENAI_MODEL` | `gpt-4o-mini` | 使用 OpenAI 时的模型名。 |
| `embedding_model` | `LIGHTRAG_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 文本嵌入模型，用于向量检索。 |
| `embedding_dim` | `LIGHTRAG_EMBEDDING_DIM` | `384` | 嵌入向量维度，应与模型匹配。 |
| `chunk_size` | `LIGHTRAG_CHUNK_SIZE` | `1200` | 文档切片长度（字符数）。 |
| `chunk_overlap` | `LIGHTRAG_CHUNK_OVERLAP` | `100` | 切片之间的重叠字符数。 |
| `max_tokens` | `LIGHTRAG_MAX_TOKENS` | `32768` | 单次调用允许的最大 token 数。 |

## 实体提取配置
| 字段 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `confidence_threshold` | `ENTITY_CONFIDENCE_THRESHOLD` | `0.6` | 预测置信度低于该阈值的实体将被过滤。 |
| `entity_types` | `ENTITY_ENTITY_TYPES` | `["POLICY","ORGANIZATION","PERSON","LOCATION","DATE","METRIC","DISEASE","BUDGET"]` | 允许抽取的实体类型列表（JSON/逗号表示）。 |
| `max_entities_per_chunk` | `ENTITY_MAX_ENTITIES_PER_CHUNK` | `50` | 每个文本块返回的实体上限。 |
| `enable_disambiguation` | `ENTITY_ENABLE_DISAMBIGUATION` | `True` | 是否启用实体消歧。 |
| `similarity_threshold` | `ENTITY_SIMILARITY_THRESHOLD` | `0.85` | 消歧时的语义相似度阈值。 |
| `report_sample_size` | `ENTITY_REPORT_SAMPLE_SIZE` | `20` | 质量报告抽样实体数量。 |

## 关系提取配置
| 字段 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `confidence_threshold` | `RELATION_CONFIDENCE_THRESHOLD` | `0.5` | 关系预测最小置信度。 |
| `relation_types` | `RELATION_RELATION_TYPES` | `["ASSOCIATED_WITH","SUPPORTED_BY","FUNDED_BY","COORDINATES_WITH","LOCATED_IN"]` | 可识别的关系类型集合。 |
| `default_relation_type` | `RELATION_DEFAULT_RELATION_TYPE` | `ASSOCIATED_WITH` | 未匹配时使用的默认关系标签。 |
| `report_sample_size` | `RELATION_REPORT_SAMPLE_SIZE` | `25` | 关系质量报告抽样数量。 |

## 质量评估配置
| 字段 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `ground_truth_path` | `QUALITY_GROUND_TRUTH_PATH` | `data/ground_truth/expected_kg.yaml` | 存放基准知识图谱的 YAML 文件。 |
| `markdown_report` | `QUALITY_MARKDOWN_REPORT` | `data/reports/kg_quality.md` | 质量评估 Markdown 输出路径。 |
| `json_report` | `QUALITY_JSON_REPORT` | `data/reports/kg_quality.json` | 质量评估 JSON 输出路径。 |
| `entity_precision` | `QUALITY_ENTITY_PRECISION` | `0.8` | 实体精确率的最低阈值。 |
| `entity_recall` | `QUALITY_ENTITY_RECALL` | `0.75` | 实体召回率最低阈值。 |
| `relation_coverage` | `QUALITY_RELATION_COVERAGE` | `0.7` | 关系覆盖率最低阈值。 |
| `graph_density` | `QUALITY_GRAPH_DENSITY` | `0.01` | 图密度下限，用于检测稀疏图谱。 |
| `min_avg_degree` | `QUALITY_MIN_AVG_DEGREE` | `1.0` | 平均度最小阈值。 |
| `max_isolated_ratio` | `QUALITY_MAX_ISOLATED_RATIO` | `0.1` | 可接受的最大孤立节点比例。 |

## Cypher 执行器配置
| 字段 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `timeout` | `CYPHER_EXECUTOR_TIMEOUT` | `5.0` | 单个 Cypher 查询的超时时间（秒）。 |
| `max_retries` | `CYPHER_EXECUTOR_MAX_RETRIES` | `1` | 失败后自动重试次数。 |

## ReAct 配置
| 字段 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `max_iterations` | `REACT_MAX_ITERATIONS` | `5` | ReAct 代理每个问题允许的最大思考/行动轮数。 |
| `timeout_per_step` | `REACT_TIMEOUT_PER_STEP` | `10.0` | 每次思考或行动的超时时间（秒）。 |

## 环境变量示例（`.env`）
```env
# 基础设置
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
REDIS_URL=redis://localhost:6379/0
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434
OPENAI_API_KEY=

# LightRAG
LIGHTRAG_WORKING_DIR=./data/lightrag
LIGHTRAG_GRAPH_STORAGE=neo4j
LIGHTRAG_NEO4J_URI=bolt://localhost:7687
LIGHTRAG_NEO4J_USER=neo4j
LIGHTRAG_NEO4J_PASSWORD=password
LIGHTRAG_LLM_BACKEND=ollama
LIGHTRAG_OLLAMA_URL=http://localhost:11434
LIGHTRAG_OLLAMA_MODEL=llama3.2
LIGHTRAG_OPENAI_API_KEY=
LIGHTRAG_OPENAI_MODEL=gpt-4o-mini
LIGHTRAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LIGHTRAG_EMBEDDING_DIM=384
LIGHTRAG_CHUNK_SIZE=1200
LIGHTRAG_CHUNK_OVERLAP=100
LIGHTRAG_MAX_TOKENS=32768

# 实体/关系配置
ENTITY_CONFIDENCE_THRESHOLD=0.6
ENTITY_ENTITY_TYPES=["POLICY","ORGANIZATION","PERSON","LOCATION","DATE","METRIC","DISEASE","BUDGET"]
ENTITY_MAX_ENTITIES_PER_CHUNK=50
ENTITY_ENABLE_DISAMBIGUATION=true
ENTITY_SIMILARITY_THRESHOLD=0.85
ENTITY_REPORT_SAMPLE_SIZE=20

RELATION_CONFIDENCE_THRESHOLD=0.5
RELATION_RELATION_TYPES=["ASSOCIATED_WITH","SUPPORTED_BY","FUNDED_BY","COORDINATES_WITH","LOCATED_IN"]
RELATION_DEFAULT_RELATION_TYPE=ASSOCIATED_WITH
RELATION_REPORT_SAMPLE_SIZE=25

# 质量评估
QUALITY_GROUND_TRUTH_PATH=data/ground_truth/expected_kg.yaml
QUALITY_MARKDOWN_REPORT=data/reports/kg_quality.md
QUALITY_JSON_REPORT=data/reports/kg_quality.json
QUALITY_ENTITY_PRECISION=0.8
QUALITY_ENTITY_RECALL=0.75
QUALITY_RELATION_COVERAGE=0.7
QUALITY_GRAPH_DENSITY=0.01
QUALITY_MIN_AVG_DEGREE=1.0
QUALITY_MAX_ISOLATED_RATIO=0.1

# 执行与推理
CYPHER_EXECUTOR_TIMEOUT=5.0
CYPHER_EXECUTOR_MAX_RETRIES=1
REACT_MAX_ITERATIONS=5
REACT_TIMEOUT_PER_STEP=10.0
```
