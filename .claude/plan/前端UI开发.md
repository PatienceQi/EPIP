# EPIP 前端 UI 开发计划

## 概述
- 技术栈: React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui
- 部署方式: 与后端同容器（静态文件）
- 设计风格: 浅色调为主

## 执行步骤

### Step 1: 项目初始化 ⬜
- [ ] frontend/package.json
- [ ] frontend/vite.config.ts
- [ ] frontend/tsconfig.json
- [ ] frontend/tailwind.config.js
- [ ] frontend/index.html
- [ ] frontend/src/main.tsx
- [ ] frontend/src/index.css

### Step 2: 基础架构 ⬜
- [ ] src/lib/api.ts
- [ ] src/types/api.ts
- [ ] src/stores/tenantStore.ts
- [ ] src/hooks/useApi.ts
- [ ] src/App.tsx

### Step 3: 布局组件 ⬜
- [ ] src/components/layout/AppLayout.tsx
- [ ] src/components/layout/Header.tsx
- [ ] src/components/layout/Sidebar.tsx
- [ ] src/components/ui/ (shadcn/ui)

### Step 4: 仪表板页面 ⬜
- [ ] src/pages/Dashboard/index.tsx
- [ ] src/pages/Dashboard/StatCards.tsx
- [ ] src/pages/Dashboard/RecentQueries.tsx
- [ ] src/pages/Dashboard/SystemHealth.tsx

### Step 5: 查询中心 ⬜
- [ ] src/pages/Query/index.tsx
- [ ] src/pages/Query/QueryInput.tsx
- [ ] src/pages/Query/QueryResult.tsx
- [ ] src/pages/Query/QueryHistory.tsx

### Step 6: 可视化模块 ⬜
- [ ] src/components/graph/KnowledgeGraph.tsx
- [ ] src/components/graph/ReasoningTrace.tsx
- [ ] src/components/graph/VerificationReport.tsx
- [ ] src/pages/Visualization/index.tsx

### Step 7: 管理控制台 ⬜
- [ ] src/pages/Admin/index.tsx
- [ ] src/pages/Admin/Tenants.tsx
- [ ] src/pages/Admin/Cache.tsx

### Step 8: 监控中心 ⬜
- [ ] src/pages/Monitor/index.tsx
- [ ] src/pages/Monitor/HealthStatus.tsx
- [ ] src/pages/Monitor/Metrics.tsx

### Step 9: 后端集成 ⬜
- [ ] 修改 src/epip/main.py
- [ ] 修改 docker/Dockerfile
- [ ] 更新 Makefile

## 设计规范
```css
--primary: #3b82f6;
--primary-light: #eff6ff;
--background: #ffffff;
--surface: #f8fafc;
--sidebar: #f1f5f9;
--text-primary: #1e293b;
--text-secondary: #64748b;
```
