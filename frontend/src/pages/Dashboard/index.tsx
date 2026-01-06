import { Link } from 'react-router-dom';
import { ArrowUpRight, LineChart, Search, Settings } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';

import RecentQueries from './RecentQueries';
import StatCards from './StatCards';
import SystemHealth from './SystemHealth';

const quickEntries = [
  {
    title: '查询中心',
    description: '快速构建和执行图谱查询，查看实时结果。',
    to: '/query',
    icon: Search,
  },
  {
    title: '可视化',
    description: '使用图谱可视化洞察实体关系与调用链路。',
    to: '/visualization',
    icon: LineChart,
  },
  {
    title: '管理控制台',
    description: '统一管理租户、缓存策略与系统配置。',
    to: '/admin',
    icon: Settings,
  },
];

const Dashboard = () => {
  return (
    <section className="space-y-8">
      <div>
        <p className="text-sm uppercase tracking-wide text-slate-400">EPIP</p>
        <h1 className="mt-1 text-3xl font-semibold text-slate-900">系统概览</h1>
        <p className="mt-2 text-base text-slate-500">掌握平台运行状态、近期查询与关键入口。</p>
      </div>

      <StatCards />

      <div className="grid gap-6 lg:grid-cols-3">
        <RecentQueries className="lg:col-span-2" />
        <SystemHealth />
      </div>

      <div>
        <h2 className="text-lg font-semibold text-slate-900">快速入口</h2>
        <p className="text-sm text-slate-500">跳转至常用功能，快速完成任务。</p>
        <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {quickEntries.map((entry) => {
            const Icon = entry.icon;
            return (
              <Link key={entry.title} to={entry.to} className="group h-full">
                <Card className="h-full border-slate-100 shadow-none transition hover:-translate-y-1 hover:shadow-md">
                  <CardContent className="flex h-full flex-col gap-4 p-6">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-50 text-slate-600 transition group-hover:bg-indigo-600 group-hover:text-white">
                      <Icon className="h-6 w-6" />
                    </div>
                    <div className="flex flex-1 flex-col">
                      <h3 className="text-base font-semibold text-slate-900">{entry.title}</h3>
                      <p className="mt-1 text-sm text-slate-500">{entry.description}</p>
                    </div>
                    <span className="inline-flex items-center text-sm font-medium text-indigo-600 transition group-hover:text-indigo-700">
                      立即前往
                      <ArrowUpRight className="ml-1 h-4 w-4" />
                    </span>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default Dashboard;
