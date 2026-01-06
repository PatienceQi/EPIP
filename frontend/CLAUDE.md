[根目录](../CLAUDE.md) > **frontend**

# 前端模块 (Frontend)

> 最后更新：2026-01-06T19:33:46+0800

---

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

React 前端应用，提供仪表盘、查询中心、可视化、管理等功能。

核心能力：
- **仪表盘**：系统状态概览、统计数据
- **查询中心**：自然语言查询、历史记录
- **可视化**：知识图谱、推理轨迹、验证报告
- **管理中心**：租户管理、缓存管理、图数据管理
- **监控面板**：健康状态、Prometheus 指标

---

## 入口与启动

主要入口点：
- `src/main.tsx`：应用入口
- `src/App.tsx`：路由配置

启动命令：
```bash
cd frontend
npm install
npm run dev    # 开发服务器，默认 http://localhost:5173
npm run build  # 生产构建
```

---

## 对外接口

### 页面路由

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | Dashboard | 仪表盘概览，系统状态与统计 |
| `/query` | QueryCenter | 自然语言查询，知识图谱检索 |
| `/visualization` | Visualization | 知识图谱、推理链可视化 |
| `/visualization/trace/:traceId` | TraceDetail | ReAct 推理步骤详情 |
| `/admin` | Admin | 管理中心入口 |
| `/admin/tenants` | Tenants | 多租户 CRUD |
| `/admin/cache` | Cache | Redis 缓存查看与清理 |
| `/admin/graph-explorer` | GraphExplorer | 图数据浏览器 |
| `/admin/cypher-console` | CypherConsole | Cypher 查询控制台 |
| `/admin/graph-data` | GraphDataManager | 图数据管理 |
| `/monitor` | Monitor | Prometheus 指标可视化 |

---

## 关键依赖与配置

### 技术栈

- **框架**：React 18 + TypeScript
- **构建工具**：Vite 5
- **路由**：React Router 6
- **状态管理**：Zustand 4
- **数据获取**：TanStack Query 5 + Axios
- **样式**：Tailwind CSS 3
- **图可视化**：XYFlow (React Flow) 12 + D3.js
- **图表**：Recharts 2
- **UI 组件**：自定义组件 + shadcn/ui 风格

### 配置文件

- `package.json`：依赖与脚本
- `tsconfig.json`：TypeScript 配置
- `vite.config.ts`：Vite 构建配置
- `tailwind.config.js`：Tailwind CSS 配置
- `postcss.config.js`：PostCSS 配置

---

## 数据模型

### API 客户端

```typescript
// src/api/client.ts
const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'X-Tenant-ID': 'admin',
  },
});
```

### 状态管理

```typescript
// src/stores/queryStore.ts
interface QueryStore {
  query: string;
  result: QueryResult | null;
  loading: boolean;
  setQuery: (query: string) => void;
  executeQuery: () => Promise<void>;
}
```

---

## 测试与质量

### 测试覆盖

⚠️ **当前缺少测试文件**

建议添加：
- 单元测试：组件逻辑测试（Vitest + React Testing Library）
- 集成测试：页面流程测试
- E2E 测试：关键用户路径测试（Playwright / Cypress）

---

## 常见问题 (FAQ)

**Q: 如何添加新页面？**
A: 在 `src/pages/` 创建新组件，更新 `App.tsx` 路由配置。

**Q: 如何自定义主题？**
A: 修改 `tailwind.config.js` 中的颜色、字体等配置。

**Q: 如何连接后端 API？**
A: 开发环境通过 Vite 代理（`vite.config.ts`），生产环境通过 Nginx 反向代理。

**Q: 如何优化构建体积？**
A: 使用动态导入（`lazy`）、Tree Shaking、代码分割。

---

## 相关文件清单

```
frontend/
├── src/
│   ├── main.tsx              # 应用入口
│   ├── App.tsx               # 路由配置
│   ├── index.css             # 全局样式
│   ├── pages/                # 页面组件
│   │   ├── Dashboard/
│   │   ├── Query/
│   │   ├── Visualization/
│   │   ├── Admin/
│   │   ├── Monitor/
│   │   └── NotFound/
│   ├── components/           # 可复用组件
│   │   ├── layout/
│   │   ├── ui/
│   │   ├── charts/
│   │   └── graph/
│   ├── stores/               # Zustand 状态管理
│   ├── api/                  # API 客户端
│   └── utils/                # 工具函数
├── public/                   # 静态资源
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

---

## 相关文档

- [架构文档](../docs/architecture.md)
- [API 参考](../docs/api-reference.md)
- [部署指南](../docs/deployment-guide.md)
