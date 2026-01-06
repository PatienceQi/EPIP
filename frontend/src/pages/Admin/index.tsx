import { Link } from 'react-router-dom';
import { Database, HardDrive, Layers, Network, Terminal } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useCacheStats, useTenants } from '@/hooks/useApi';

const navCards = [
  {
    title: '租户管理',
    description: '查看、搜索与维护租户元数据与状态。',
    to: '/admin/tenants',
    icon: Layers,
    cta: '进入租户管理',
  },
  {
    title: '缓存管理',
    description: '监控缓存命中率，执行刷新与清理操作。',
    to: '/admin/cache',
    icon: Database,
    cta: '进入缓存管理',
  },
  {
    title: '图数据库浏览器',
    description: '可视化浏览和管理 Neo4j 图数据库节点与关系。',
    to: '/admin/graph-explorer',
    icon: Network,
    cta: '打开图数据库浏览器',
  },
  {
    title: 'Cypher 控制台',
    description: '执行 Cypher 查询语句，探索和分析图数据。',
    to: '/admin/cypher-console',
    icon: Terminal,
    cta: '进入 Cypher 控制台',
  },
  {
    title: '数据管理',
    description: '图数据库维护、批量导入导出与健康监控。',
    to: '/admin/graph-data',
    icon: HardDrive,
    cta: '进入数据管理',
  },
];

const formatBytes = (bytes?: number) => {
  if (!bytes && bytes !== 0) return '--';
  if (bytes < 1024) return `${bytes.toFixed(0)} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const Admin = () => {
  const { data: tenants = [], isLoading: tenantsLoading } = useTenants();
  const { data: cacheStats, isLoading: cacheLoading } = useCacheStats();

  const quickStats = [
    {
      label: '租户数量',
      value: tenantsLoading ? '计算中...' : tenants.length.toString(),
      detail: tenantsLoading ? '正在加载租户' : `当前已注册 ${tenants.length} 个租户`,
    },
    {
      label: '缓存大小',
      value: cacheLoading ? '采集中...' : `${cacheStats?.size ?? 0} 条`,
      detail: cacheLoading
        ? '等待缓存统计'
        : `内存占用约 ${formatBytes(cacheStats?.memory_usage)}`,
    },
  ];

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-wide text-slate-400">EPIP</p>
        <h1 className="text-3xl font-semibold text-slate-900">管理控制台</h1>
        <p className="text-base text-slate-500">集中管理租户、缓存策略与平台级配置。</p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {quickStats.map((stat) => (
          <Card key={stat.label} className="border-slate-100 shadow-none">
            <CardHeader>
              <CardTitle className="text-sm font-medium text-slate-500">{stat.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold text-slate-900">{stat.value}</p>
              <p className="mt-2 text-sm text-slate-500">{stat.detail}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {navCards.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.title} to={card.to} className="group h-full">
              <Card className="h-full border-slate-100 shadow-none transition hover:-translate-y-1 hover:shadow-md">
                <CardContent className="flex h-full flex-col gap-4 p-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-50 text-slate-600 transition group-hover:bg-indigo-600 group-hover:text-white">
                    <Icon className="h-6 w-6" />
                  </div>
                  <div className="flex flex-1 flex-col">
                    <h2 className="text-xl font-semibold text-slate-900">{card.title}</h2>
                    <p className="mt-2 text-sm text-slate-500">{card.description}</p>
                  </div>
                  <span className="text-sm font-medium text-indigo-600 transition group-hover:text-indigo-700">
                    {card.cta}
                  </span>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </section>
  );
};

export default Admin;
