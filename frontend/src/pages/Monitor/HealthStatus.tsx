import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, RefreshCcw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { get } from '@/lib/api';

type HealthStatusLevel = 'healthy' | 'degraded' | 'unhealthy';

type LiveHealthResponse = {
  status: string;
};

type ReadyHealthResponse = {
  status: string;
  neo4j: string;
  redis: string;
};

interface HealthStatusProps {
  autoRefresh: boolean;
  refreshInterval: number;
}

const statusMeta: Record<
  HealthStatusLevel,
  { label: string; badge: string; dot: string; description: string }
> = {
  healthy: {
    label: '运行健康',
    badge: 'text-emerald-600 bg-emerald-50',
    dot: 'bg-emerald-500',
    description: '全部核心服务响应正常。',
  },
  degraded: {
    label: '部分降级',
    badge: 'text-amber-600 bg-amber-50',
    dot: 'bg-amber-400',
    description: '存在需要关注的依赖或资源。',
  },
  unhealthy: {
    label: '服务异常',
    badge: 'text-red-600 bg-red-50',
    dot: 'bg-red-500',
    description: '核心服务不可用，需立即排查。',
  },
};

const mapStatus = (value?: string): HealthStatusLevel => {
  if (!value) return 'degraded';
  const normalized = value.toLowerCase();
  if (['ok', 'healthy', 'up', 'ready'].includes(normalized)) return 'healthy';
  if (['warn', 'warning', 'degraded'].includes(normalized)) return 'degraded';
  return 'unhealthy';
};

const HealthStatus = ({ autoRefresh, refreshInterval }: HealthStatusProps) => {
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const liveQuery = useQuery<LiveHealthResponse>({
    queryKey: ['monitoring', 'health', 'live'],
    queryFn: () => get<LiveHealthResponse>('/monitoring/health/live'),
    refetchInterval: autoRefresh ? refreshInterval : false,
  });

  const readyQuery = useQuery<ReadyHealthResponse>({
    queryKey: ['monitoring', 'health', 'ready'],
    queryFn: () => get<ReadyHealthResponse>('/monitoring/health/ready'),
    refetchInterval: autoRefresh ? refreshInterval : false,
  });

  useEffect(() => {
    if (liveQuery.data && readyQuery.data) {
      setLastChecked(new Date());
    }
  }, [liveQuery.data, readyQuery.data]);

  const serviceCards = useMemo(
    () => [
      {
        key: 'api',
        name: 'API 服务',
        status: mapStatus(liveQuery.data?.status),
        description: 'FastAPI 应用与业务逻辑运行状况。',
        detail: liveQuery.data?.status ?? '未知',
      },
      {
        key: 'neo4j',
        name: 'Neo4j 图数据库',
        status: mapStatus(readyQuery.data?.neo4j),
        description: '图数据库连接与查询能力。',
        detail: readyQuery.data?.neo4j ?? '未知',
      },
      {
        key: 'redis',
        name: 'Redis 缓存',
        status: mapStatus(readyQuery.data?.redis),
        description: '缓存与消息能力健康状况。',
        detail: readyQuery.data?.redis ?? '未知',
      },
    ],
    [liveQuery.data, readyQuery.data]
  );

  const overallStatus: HealthStatusLevel = useMemo(() => {
    if (serviceCards.some((service) => service.status === 'unhealthy')) {
      return 'unhealthy';
    }
    if (serviceCards.some((service) => service.status === 'degraded')) {
      return 'degraded';
    }
    return 'healthy';
  }, [serviceCards]);

  const isLoading = (liveQuery.isLoading || readyQuery.isLoading) && !(liveQuery.data && readyQuery.data);
  const isFetching = liveQuery.isFetching || readyQuery.isFetching;
  const error = liveQuery.error ?? readyQuery.error;
  const errorMessage = error instanceof Error ? error.message : null;

  const handleRefresh = async () => {
    await Promise.all([liveQuery.refetch(), readyQuery.refetch()]);
    setLastChecked(new Date());
  };

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle>系统健康状态</CardTitle>
          <CardDescription>实时查看核心依赖的可用性与状态。</CardDescription>
          <p className="mt-2 text-xs text-slate-400">
            最后检查时间：{lastChecked ? lastChecked.toLocaleString('zh-CN', { hour12: false }) : '等待数据...'}
          </p>
        </div>
        <Button variant="outline" onClick={handleRefresh} disabled={isFetching}>
          <RefreshCcw className="mr-2 h-4 w-4" />
          手动刷新
        </Button>
      </CardHeader>
      <CardContent>
        {errorMessage ? (
          <div className="mb-4 flex items-center gap-3 rounded-2xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
            <AlertTriangle className="h-5 w-5 flex-none" />
            健康检查失败：{errorMessage}
          </div>
        ) : null}

        {isLoading ? (
          <div className="flex h-48 items-center justify-center">
            <Spinner label="健康状态加载中" />
          </div>
        ) : (
          <>
            <div
              className={`mb-6 flex flex-col gap-2 rounded-2xl border border-slate-100 p-5 lg:flex-row lg:items-center lg:justify-between ${statusMeta[overallStatus].badge}`}
            >
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">整体状态</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{statusMeta[overallStatus].label}</p>
                <p className="text-sm text-slate-500">{statusMeta[overallStatus].description}</p>
              </div>
              <div className="flex items-center gap-3 rounded-full bg-white/70 px-4 py-2 text-sm font-medium text-slate-500 shadow-sm">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${statusMeta[overallStatus].dot}`}
                  aria-hidden="true"
                />
                <span>自动刷新 {autoRefresh ? `已开启 (${refreshInterval / 1000}s)` : '已关闭'}</span>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {serviceCards.map((service) => (
                <div
                  key={service.key}
                  className="rounded-2xl border border-slate-100 bg-slate-50 p-5 transition hover:border-slate-200 hover:bg-white"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{service.name}</p>
                      <p className="text-xs text-slate-500">{service.description}</p>
                    </div>
                    <span
                      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${statusMeta[service.status].badge}`}
                    >
                      <span
                        className={`h-2 w-2 rounded-full ${statusMeta[service.status].dot}`}
                        aria-hidden="true"
                      />
                      {statusMeta[service.status].label}
                    </span>
                  </div>
                  <p className="mt-4 text-sm text-slate-500">
                    当前响应：<span className="font-medium text-slate-900">{service.detail}</span>
                  </p>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default HealthStatus;
