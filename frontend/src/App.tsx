import { Suspense, lazy } from 'react';
import { Route, Routes } from 'react-router-dom';

import AppLayout from '@/components/layout/AppLayout';

const Dashboard = lazy(() => import('@/pages/Dashboard'));
const QueryCenter = lazy(() => import('@/pages/Query'));
const Visualization = lazy(() => import('@/pages/Visualization'));
const TraceDetail = lazy(() => import('@/pages/Visualization/TraceDetail'));
const Admin = lazy(() => import('@/pages/Admin'));
const AdminTenants = lazy(() => import('@/pages/Admin/Tenants'));
const AdminCache = lazy(() => import('@/pages/Admin/Cache'));
const GraphExplorer = lazy(() => import('@/pages/Admin/GraphExplorer'));
const CypherConsole = lazy(() => import('@/pages/Admin/CypherConsole'));
const GraphDataManager = lazy(() => import('@/pages/Admin/GraphDataManager'));
const Monitor = lazy(() => import('@/pages/Monitor'));
const NotFound = lazy(() => import('@/pages/NotFound'));

const PageLoader = () => (
  <div className="flex min-h-[200px] items-center justify-center text-slate-500">
    页面加载中...
  </div>
);

const App = () => {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="query" element={<QueryCenter />} />
          <Route path="visualization" element={<Visualization />} />
          <Route path="visualization/trace/:traceId" element={<TraceDetail />} />
          <Route path="admin" element={<Admin />} />
          <Route path="admin/tenants" element={<AdminTenants />} />
          <Route path="admin/cache" element={<AdminCache />} />
          <Route path="admin/graph-explorer" element={<GraphExplorer />} />
          <Route path="admin/cypher-console" element={<CypherConsole />} />
          <Route path="admin/graph-data" element={<GraphDataManager />} />
          <Route path="monitor" element={<Monitor />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
};

export default App;
