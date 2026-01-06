import { AlertTriangle, CheckCircle2, Server } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useHealth } from '@/hooks/useApi';
import { cn } from '@/lib/cn';

interface SystemHealthProps {
  className?: string;
}

const STATUS_MAP: Record<string, { label: string; healthy: boolean }> = {
  healthy: { label: '正常', healthy: true },
  up: { label: '正常', healthy: true },
  ok: { label: '正常', healthy: true },
  running: { label: '正常', healthy: true },
  degraded: { label: '波动', healthy: false },
  warning: { label: '波动', healthy: false },
  down: { label: '异常', healthy: false },
  failed: { label: '异常', healthy: false },
  error: { label: '异常', healthy: false },
};

const normalizeStatus = (status?: string) => {
  const normalized = status?.toLowerCase() ?? 'unknown';
  const matched = STATUS_MAP[normalized];
  if (matched) {
    return matched;
  }
  return { label: '未知', healthy: false };
};

type ServiceKey = 'status' | 'neo4j' | 'redis';

const STATUS_ITEMS: Array<{ key: ServiceKey; label: string }> = [
  { key: 'status', label: 'API 服务' },
  { key: 'neo4j', label: 'Neo4j 图数据库' },
  { key: 'redis', label: 'Redis 缓存' },
];

const getStatusValue = (
  data: { status?: string; services?: { neo4j?: string; redis?: string } } | undefined,
  key: ServiceKey
): string | undefined => {
  if (!data) return undefined;
  if (key === 'status') return data.status;
  return data.services?.[key as 'neo4j' | 'redis'];
};

const SystemHealth = ({ className }: SystemHealthProps) => {
  const { data, isLoading, isError, refetch, isRefetching } = useHealth();

  return (
    <Card className={cn('border-slate-100 shadow-none', className)}>
      <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 pb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50 text-slate-600">
            <Server className="h-5 w-5" />
          </div>
          <div>
            <CardTitle className="text-base text-slate-900">系统健康</CardTitle>
            <p className="text-sm text-slate-500">核心服务运行状态监控</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="text-sm font-medium text-indigo-600 transition hover:text-indigo-700"
          disabled={isRefetching}
        >
          {isRefetching ? '刷新中...' : '刷新'}
        </button>
      </CardHeader>
      <CardContent className="space-y-4 p-6">
        {isLoading ? (
          <p className="text-sm text-slate-500">健康状态加载中...</p>
        ) : isError ? (
          <div className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            获取系统健康信息失败，请稍后重试。
          </div>
        ) : (
          <>
            <ul className="space-y-3">
              {STATUS_ITEMS.map((item) => {
                const rawStatus = getStatusValue(data, item.key);
                const { label, healthy } = normalizeStatus(rawStatus);
                const Icon = healthy ? CheckCircle2 : AlertTriangle;
                const colorClass = healthy ? 'text-emerald-600' : 'text-rose-500';

                return (
                  <li
                    key={item.key}
                    className="flex items-center justify-between rounded-xl border border-slate-100 px-4 py-3"
                  >
                    <div>
                      <p className="text-sm font-medium text-slate-900">{item.label}</p>
                      <p className="text-xs text-slate-500">{healthy ? '运行稳定' : '需要关注'}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Icon className={cn('h-4 w-4', colorClass)} />
                      <span className={cn('text-sm font-semibold', colorClass)}>{label}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">当前版本</span>
                <Badge variant="secondary" className="bg-white text-slate-900">
                  {data?.version ?? '--'}
                </Badge>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                API 状态：{normalizeStatus(data?.status).label} · Neo4j：{normalizeStatus(data?.services?.neo4j).label} · Redis：
                {normalizeStatus(data?.services?.redis).label}
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default SystemHealth;
