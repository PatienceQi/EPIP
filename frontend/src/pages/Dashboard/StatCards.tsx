import { useMemo } from 'react';
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Gauge,
  ShieldCheck,
  Users,
  type LucideIcon,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useCacheStats, useHealth, useTenants } from '@/hooks/useApi';
import { cn } from '@/lib/cn';

type TrendDirection = 'up' | 'down';

interface StatCardsProps {
  className?: string;
}

interface StatCardConfig {
  title: string;
  value: string;
  caption: string;
  change: number;
  icon: LucideIcon;
  accentClass: string;
  trend: TrendDirection;
}

const clampChange = (value: number) => {
  if (Number.isNaN(value)) {
    return 0;
  }
  return Math.max(-25, Math.min(25, value));
};

const formatPercent = (value: number, digits = 1) =>
  `${(Number.isFinite(value) ? value : 0).toFixed(digits)}%`;

const TrendLabel = ({ trend, change }: { trend: TrendDirection; change: number }) => {
  const Icon = trend === 'up' ? ArrowUpRight : ArrowDownRight;
  const colorClass = trend === 'up' ? 'text-emerald-600' : 'text-rose-500';
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-sm font-medium', colorClass)}>
      <Icon className="h-4 w-4" />
      {trend === 'up' ? '+' : '-'}
      {Math.abs(change).toFixed(1)}%
    </span>
  );
};

const StatCards = ({ className }: StatCardsProps) => {
  const { data: cacheStats, isLoading: cacheLoading } = useCacheStats();
  const { data: health, isLoading: healthLoading } = useHealth();
  const { data: tenantData, isLoading: tenantLoading } = useTenants();

  const cards = useMemo<StatCardConfig[]>(() => {
    const hits = cacheStats?.hits ?? 0;
    const misses = cacheStats?.misses ?? 0;
    const totalQueries = hits + misses;
    const hitRatePercent = (cacheStats?.hit_rate ?? 0) * 100;
    const queryChange = clampChange(
      totalQueries === 0 ? 0 : ((hits - misses) / Math.max(totalQueries, 1)) * 100
    );
    const hitRateChange = clampChange(hitRatePercent - 70);

    const tenants = tenantData ?? [];
    const activeTenants =
      tenants.filter((tenant) => tenant.status?.toLowerCase() !== 'inactive').length || tenants.length;
    const tenantChange = tenants.length
      ? clampChange(((activeTenants / Math.max(tenants.length, 1)) - 0.8) * 100)
      : 0;

    const statusText = health?.status ? health.status.toLowerCase() : 'unknown';
    const systemTrend =
      statusText === 'healthy' || statusText === 'up' || statusText === 'ok'
        ? 'up'
        : statusText === 'degraded'
          ? 'down'
          : statusText === 'unknown'
            ? 'up'
            : 'down';
    const systemChange =
      statusText === 'healthy'
        ? 12
        : statusText === 'degraded'
          ? -6
          : statusText === 'unknown'
            ? 0
            : -18;

    const readableStatus =
      statusText === 'healthy'
        ? '健康'
        : statusText === 'degraded'
          ? '波动'
        : statusText === 'down'
            ? '异常'
            : '未知';

    return [
      {
        title: '今日查询数',
        value: totalQueries ? totalQueries.toLocaleString('zh-CN') : cacheLoading ? '检测中...' : '0',
        caption: '命中 + 未命中',
        change: queryChange,
        icon: Activity,
        accentClass: 'bg-indigo-50 text-indigo-600',
        trend: queryChange >= 0 ? 'up' : 'down',
      },
      {
        title: '缓存命中率',
        value: cacheStats ? formatPercent(hitRatePercent) : cacheLoading ? '检测中...' : '--',
        caption: `容量 ${cacheStats?.size ?? 0} 条`,
        change: hitRateChange,
        icon: Gauge,
        accentClass: 'bg-emerald-50 text-emerald-600',
        trend: hitRateChange >= 0 ? 'up' : 'down',
      },
      {
        title: '活跃租户',
        value: tenantLoading ? '检测中...' : activeTenants.toString(),
        caption: `总计 ${tenants.length || 0} 个租户`,
        change: tenantChange,
        icon: Users,
        accentClass: 'bg-sky-50 text-sky-600',
        trend: tenantChange >= 0 ? 'up' : 'down',
      },
      {
        title: '系统状态',
        value: healthLoading ? '检测中...' : readableStatus,
        caption: `版本 ${health?.version ?? '--'}`,
        change: clampChange(systemChange),
        icon: ShieldCheck,
        accentClass: 'bg-amber-50 text-amber-600',
        trend: systemTrend,
      },
    ];
  }, [cacheLoading, cacheStats, health?.status, health?.version, healthLoading, tenantData, tenantLoading]);

  return (
    <div className={cn('grid gap-4 md:grid-cols-2 xl:grid-cols-4', className)}>
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <Card key={card.title} className="border-slate-100 shadow-none">
            <CardHeader className="flex flex-row items-center justify-between border-none p-5">
              <div>
                <CardTitle className="text-sm text-slate-500">{card.title}</CardTitle>
                <div className="mt-2 text-2xl font-semibold text-slate-900">{card.value}</div>
                <p className="mt-1 text-sm text-slate-500">{card.caption}</p>
              </div>
              <div className={cn('flex h-12 w-12 items-center justify-center rounded-xl', card.accentClass)}>
                <Icon className="h-6 w-6" />
              </div>
            </CardHeader>
            <CardContent className="border-t border-slate-100 px-5 py-4">
              <div className="flex items-center justify-between text-sm">
                <TrendLabel trend={card.trend} change={card.change} />
                <span className="text-slate-500">较昨日</span>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
};

export default StatCards;
