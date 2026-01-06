# Neo4j 图数据库可视化与管理功能实施计划

## 需求概述

- **图数据浏览**：节点/关系可视化、过滤搜索、Cypher 控制台
- **图分析算法**：路径查找 (已有)、链接预测
- **数据管理**：CRUD、批量导入导出、维护工具（仅管理员）
- **监控运维**：图统计、健康监控（仅管理员）
- **权限模型**：管理员读写 / 租户只读

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
├─────────────────────────────────────────────────────────────┤
│  GraphExplorer    CypherConsole    DataManager    Monitor   │
│  (可视化浏览)      (查询控制台)     (数据管理)     (监控)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
├─────────────────────────────────────────────────────────────┤
│  /api/graph/*     /api/cypher/*    /api/admin/graph/*       │
│  (图浏览 API)      (Cypher 执行)    (管理 API)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Neo4j Graph Database                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 步骤 1：后端 - Neo4j Graph Service

### 1.1 扩展 Neo4jClient

**文件**: `src/epip/db/neo4j_client.py`

```python
# 新增方法
async def execute_read(self, query: str, params: dict) -> list[dict]
async def execute_write(self, query: str, params: dict) -> dict
async def get_stats(self) -> dict  # 节点/关系统计
async def get_labels(self) -> list[str]  # 所有标签
async def get_relationship_types(self) -> list[str]  # 所有关系类型
```

### 1.2 创建 Graph Service

**新建文件**: `src/epip/services/graph_service.py`

```python
class GraphService:
    # 节点操作
    async def get_nodes(self, label: str, limit: int, offset: int, filters: dict) -> list[Node]
    async def get_node(self, node_id: str) -> Node
    async def create_node(self, label: str, properties: dict) -> Node
    async def update_node(self, node_id: str, properties: dict) -> Node
    async def delete_node(self, node_id: str) -> bool

    # 关系操作
    async def get_relationships(self, node_id: str, direction: str) -> list[Relationship]
    async def create_relationship(self, source_id: str, target_id: str, type: str, props: dict) -> Relationship
    async def delete_relationship(self, rel_id: str) -> bool

    # 邻居展开
    async def expand_node(self, node_id: str, depth: int) -> GraphData

    # 链接预测
    async def predict_links(self, node_id: str, algorithm: str) -> list[PredictedLink]
```

---

## 步骤 2：后端 - API 路由

### 2.1 图浏览 API

**新建文件**: `src/epip/api/graph.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/graph/nodes` | 分页获取节点 | 全部 |
| GET | `/api/graph/nodes/{id}` | 获取单个节点 | 全部 |
| GET | `/api/graph/nodes/{id}/expand` | 展开邻居节点 | 全部 |
| GET | `/api/graph/nodes/{id}/relationships` | 获取节点关系 | 全部 |
| GET | `/api/graph/labels` | 获取所有标签 | 全部 |
| GET | `/api/graph/relationship-types` | 获取所有关系类型 | 全部 |
| GET | `/api/graph/search` | 搜索节点 | 全部 |

### 2.2 Cypher API

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/cypher/execute` | 执行 Cypher 查询 | 管理员: 读写 / 租户: 只读 |
| GET | `/api/cypher/history` | 查询历史 | 全部 |

### 2.3 管理 API（仅管理员）

**新建文件**: `src/epip/api/admin/graph.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/admin/graph/nodes` | 创建节点 |
| PUT | `/api/admin/graph/nodes/{id}` | 更新节点 |
| DELETE | `/api/admin/graph/nodes/{id}` | 删除节点 |
| POST | `/api/admin/graph/relationships` | 创建关系 |
| DELETE | `/api/admin/graph/relationships/{id}` | 删除关系 |
| POST | `/api/admin/graph/import` | 批量导入 (CSV/JSON) |
| GET | `/api/admin/graph/export` | 导出数据 |
| POST | `/api/admin/graph/maintenance/reindex` | 重建索引 |
| DELETE | `/api/admin/graph/maintenance/orphans` | 清理孤立节点 |

### 2.4 监控 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/graph/stats` | 图统计信息 |
| GET | `/api/admin/graph/health` | Neo4j 健康状态 |

### 2.5 算法 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/graph/algorithms/path` | 路径查找 |
| POST | `/api/graph/algorithms/link-prediction` | 链接预测 |

---

## 步骤 3：权限控制

### 3.1 权限中间件

**修改文件**: `src/epip/api/middleware/tenant.py`

```python
def is_admin(tenant: Tenant) -> bool:
    return tenant.config.get("role") == "admin"

def require_admin(request: Request):
    tenant = TenantContext.get_current()
    if not is_admin(tenant):
        raise HTTPException(403, "Admin access required")
```

### 3.2 Cypher 安全过滤

```python
WRITE_KEYWORDS = {"CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP"}

def is_write_query(cypher: str) -> bool:
    tokens = cypher.upper().split()
    return any(keyword in tokens for keyword in WRITE_KEYWORDS)

async def execute_cypher(cypher: str, tenant: Tenant):
    if is_write_query(cypher) and not is_admin(tenant):
        raise HTTPException(403, "Write operations require admin access")
```

---

## 步骤 4：前端 - 类型定义

**新建文件**: `frontend/src/types/graph.ts`

```typescript
interface GraphNode {
  id: string;
  labels: string[];
  properties: Record<string, unknown>;
}

interface GraphRelationship {
  id: string;
  type: string;
  startNodeId: string;
  endNodeId: string;
  properties: Record<string, unknown>;
}

interface GraphData {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
}

interface GraphStats {
  nodeCount: number;
  relationshipCount: number;
  labelCounts: Record<string, number>;
  relationshipTypeCounts: Record<string, number>;
}
```

---

## 步骤 5：前端 - GraphExplorer 页面

**新建文件**: `frontend/src/pages/Admin/GraphExplorer.tsx`

### 5.1 组件结构

```
GraphExplorer
├── Toolbar (搜索、过滤、布局切换)
├── GraphCanvas (React Flow 力导向图)
│   ├── CustomNode (可点击展开)
│   └── CustomEdge (显示关系类型)
├── NodeDetailPanel (右侧详情面板)
│   ├── PropertiesView
│   ├── RelationshipsView
│   └── EditForm (仅管理员)
└── ActionBar (CRUD 按钮, 仅管理员)
```

### 5.2 核心功能

- **分页加载**: 初始加载 50 节点，滚动/展开时加载更多
- **点击展开**: 点击节点加载相邻节点
- **拖拽布局**: 支持自由拖拽调整位置
- **过滤器**: 按标签、属性值过滤
- **搜索**: 支持属性模糊搜索

---

## 步骤 6：前端 - Cypher 控制台

**新建文件**: `frontend/src/pages/Admin/CypherConsole.tsx`

### 6.1 组件结构

```
CypherConsole
├── Editor (Monaco Editor with Cypher syntax)
├── ExecuteButton
├── ResultsPanel
│   ├── TableView (表格展示)
│   ├── GraphView (图形展示)
│   └── RawView (JSON 原始数据)
└── HistoryPanel (查询历史)
```

### 6.2 安全限制

- 非管理员：禁用写操作关键字高亮
- 执行前校验：前端预检测写操作

---

## 步骤 7：前端 - 数据管理面板

**新建文件**: `frontend/src/pages/Admin/GraphDataManager.tsx`

### 7.1 功能模块

```
GraphDataManager (仅管理员)
├── ImportExport
│   ├── ImportForm (CSV/JSON 上传)
│   └── ExportButton (下载)
├── MaintenanceTools
│   ├── ReindexButton
│   ├── OrphanCleanup
│   └── StatsRefresh
└── BulkOperations
    ├── BatchCreate
    └── BatchDelete
```

---

## 步骤 8：前端 - 路由配置

**修改文件**: `frontend/src/routes.tsx`

```typescript
// 新增路由
{ path: '/admin/graph', element: <GraphExplorer /> }
{ path: '/admin/graph/cypher', element: <CypherConsole /> }
{ path: '/admin/graph/data', element: <GraphDataManager /> }
```

---

## 步骤 9：前端 - 监控集成

**修改文件**: `frontend/src/pages/Monitor/index.tsx`

- 添加 Neo4j 图统计卡片
- 添加健康状态指标

---

## 文件清单

### 后端新建

| 文件 | 说明 |
|------|------|
| `src/epip/services/graph_service.py` | 图数据服务 |
| `src/epip/api/graph.py` | 图浏览 API |
| `src/epip/api/admin/graph.py` | 管理 API |
| `src/epip/api/schemas/graph.py` | Pydantic 模型 |

### 后端修改

| 文件 | 修改 |
|------|------|
| `src/epip/db/neo4j_client.py` | 扩展 CRUD 方法 |
| `src/epip/api/middleware/tenant.py` | 添加权限检查 |
| `src/epip/api/routes.py` | 注册新路由 |

### 前端新建

| 文件 | 说明 |
|------|------|
| `frontend/src/types/graph.ts` | 类型定义 |
| `frontend/src/pages/Admin/GraphExplorer.tsx` | 图浏览器 |
| `frontend/src/pages/Admin/CypherConsole.tsx` | Cypher 控制台 |
| `frontend/src/pages/Admin/GraphDataManager.tsx` | 数据管理 |
| `frontend/src/hooks/useGraph.ts` | 图数据 Hooks |
| `frontend/src/components/graph/NodeEditor.tsx` | 节点编辑组件 |

### 前端修改

| 文件 | 修改 |
|------|------|
| `frontend/src/routes.tsx` | 添加路由 |
| `frontend/src/pages/Admin/index.tsx` | 添加导航链接 |
| `frontend/src/pages/Monitor/index.tsx` | 添加图统计 |
| `frontend/src/stores/tenantStore.ts` | 添加权限判断 |

---

## 预期交付

1. 图浏览器：力导向图可视化，支持展开、搜索、过滤
2. Cypher 控制台：语法高亮编辑器，结果多视图展示
3. 数据管理：CRUD 界面，批量导入导出
4. 权限控制：管理员读写，租户只读
5. 监控集成：图统计、健康状态

---

## 风险与依赖

| 风险 | 缓解措施 |
|------|----------|
| 大图性能问题 | 分页加载 + 虚拟化渲染 |
| Cypher 注入 | 参数化查询 + 写操作白名单 |
| Neo4j GDS 未安装 | 算法降级为基础 Cypher 实现 |
