import { useMemo, useState } from 'react';
import { Database, RefreshCcw, Sparkles, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { useCacheStats, useClearCache } from '@/hooks/useApi';

const formatPercent = (value: number | undefined) => {
  if (value === undefined || Number.isNaN(value)) return '--';
  return `${(value * 100).toFixed(1)}%`;
};

const formatBytes = (bytes?: number) => {
  if (!bytes && bytes !== 0) return '--';
  if (bytes < 1024) return `${bytes.toFixed(0)} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const Cache = () => {
  const { data: stats, isLoading, isFetching, refetch } = useCacheStats();
  const clearCache = useClearCache();
  const [pattern, setPattern] = useState('*');

  const hitRate = stats?.hit_rate ?? 0;
  const missRate = 1 - hitRate;

  const statCards = useMemo(
    () => [
      {
        label: '命中率',
        value: formatPercent(hitRate),
        detail: `累计命中 ${stats?.hits ?? 0} 次 / 未命中 ${stats?.misses ?? 0} 次`,
        icon: Sparkles,
      },
      {
        label: '缓存条目',
        value: stats?.size?.toLocaleString('zh-CN') ?? '--',
        detail: `整体未命中率约 ${formatPercent(missRate)}`,
        icon: Database,
      },
      {
        label: '内存占用',
        value: formatBytes(stats?.memory_usage),
        detail: '数据来源于 Redis 统计',
        icon: Trash2,
      },
    ],
    [hitRate, missRate, stats?.hits, stats?.memory_usage, stats?.misses, stats?.size]
  );

  const handleClear = async (targetPattern?: string) => {
    try {
      await clearCache.mutateAsync({ pattern: targetPattern ?? '*' });
    } catch {
      // error handled via global error boundary
    }
  };

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-slate-900">缓存管理</h1>
          <p className="mt-2 text-base text-slate-500">监控缓存命中情况，执行清理与刷新。</p>
        </div>
        <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? '刷新中...' : '重新获取统计'}
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.label} className="border-slate-100 shadow-none">
              <CardContent className="flex flex-col gap-4 p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-50 text-slate-600">
                  <Icon className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">{card.label}</p>
                  <p className="mt-1 text-3xl font-semibold text-slate-900">{card.value}</p>
                  <p className="mt-2 text-xs text-slate-500">{card.detail}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="border-slate-100 shadow-none lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-slate-900">缓存控制</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {isLoading ? (
              <div className="flex items-center justify-center">
                <Spinner label="加载缓存统计" />
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">按模式清理</label>
                  <div className="flex flex-col gap-3 md:flex-row">
                    <Input
                      placeholder="如 demo* 或 * 表示全部"
                      value={pattern}
                      onChange={(event) => setPattern(event.target.value)}
                      className="md:flex-1"
                    />
                    <div className="flex gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => handleClear('*')}
                        disabled={clearCache.isPending}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        清理全部
                      </Button>
                      <Button
                        type="button"
                        onClick={() => handleClear(pattern || '*')}
                        disabled={clearCache.isPending}
                      >
                        <RefreshCcw className="mr-2 h-4 w-4" />
                        按模式清理
                      </Button>
                    </div>
                  </div>
                  <p className="text-xs text-slate-400">
                    模式遵循 Redis glob 语法，例如 <code>demo*</code>。
                  </p>
                </div>
                {clearCache.isPending && (
                  <p className="text-sm text-slate-500">正在清理缓存，请稍候...</p>
                )}
                {clearCache.data && !clearCache.isPending && (
                  <p className="text-sm text-green-600">
                    已清理 {clearCache.data.cleared} 条缓存（模式 {clearCache.data.pattern}）。
                  </p>
                )}
                {clearCache.error && (
                  <p className="text-sm text-red-500">
                    {clearCache.error.message ?? '清理缓存失败'}
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-100 shadow-none">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-slate-900">缓存条目</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-600">
            <p>当前后端 API 暂未提供缓存条目列表。</p>
            <p>如需排查具体条目，可直接连接 Redis 或使用 CLI 工具。</p>
            <p>一旦 API 可用，可在此区域展示明细、TTL、命中次数等指标。</p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
};

export default Cache;
