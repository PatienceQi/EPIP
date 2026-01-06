import { useEffect, useMemo, useState } from 'react';
import { RefreshCcw } from 'lucide-react';

import GaugeChart from '@/components/charts/GaugeChart';
import LineChart from '@/components/charts/LineChart';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { useMetrics } from '@/hooks/useApi';
import { cn } from '@/lib/cn';

interface MetricsProps {
  autoRefresh: boolean;
  refreshInterval: number;
}

type MetricSample = {
  metric: string;
  value: number;
  labels: Record<string, string>;
};

type ParsedMetrics = Record<string, MetricSample[]>;

interface MetricSnapshot {
  timestamp: number;
  timestampLabel: string;
  totalRequests: number;
  errorRate: number;
  avgLatencyMs: number;
  successRate: number;
  cacheHitRate: number;
}

const RANGE_OPTIONS = [
  { label: '最近 5 分钟', value: '5m', duration: 5 * 60 * 1000 },
  { label: '最近 30 分钟', value: '30m', duration: 30 * 60 * 1000 },
  { label: '最近 6 小时', value: '6h', duration: 6 * 60 * 60 * 1000 },
];

const parsePrometheusMetrics = (raw: string): ParsedMetrics => {
  const metrics: ParsedMetrics = {};
  raw
    .split('\n')
    .map((line) => line.trim())
    .forEach((line) => {
      if (!line || line.startsWith('#')) return;
      const spaceIndex = line.search(/\s/);
      if (spaceIndex === -1) return;
      const metricPart = line.slice(0, spaceIndex);
      const valuePart = line.slice(spaceIndex).trim();
      const [valueToken] = valuePart.split(/\s+/);
      const normalizedValue =
        valueToken === '+Inf'
          ? Number.POSITIVE_INFINITY
          : valueToken === '-Inf'
            ? Number.NEGATIVE_INFINITY
            : Number(valueToken);
      if (!Number.isFinite(normalizedValue)) return;

      let metricName = metricPart;
      let labelsSegment = '';
      const labelStart = metricPart.indexOf('{');
      if (labelStart !== -1) {
        metricName = metricPart.slice(0, labelStart);
        labelsSegment = metricPart.slice(labelStart + 1, metricPart.length - 1);
      }

      const labels: Record<string, string> = {};
      if (labelsSegment) {
        labelsSegment.split(',').forEach((pair) => {
          const [key, ...rest] = pair.split('=');
          const rawValue = rest.join('=');
          labels[key.trim()] = rawValue
            .replace(/^"(.*)"$/, '$1')
            .replace(/\\"/g, '"')
            .trim();
        });
      }

      const sample: MetricSample = { metric: metricName, value: normalizedValue, labels };
      metrics[metricName] = [...(metrics[metricName] ?? []), sample];
    });

  return metrics;
};

const buildSnapshot = (rawMetrics: string): MetricSnapshot | null => {
  if (!rawMetrics) return null;
  const metrics = parsePrometheusMetrics(rawMetrics);
  const requestSamples = metrics['epip_requests_total'] ?? [];
  const totalRequests = requestSamples.reduce((sum, sample) => sum + sample.value, 0);
  const errorRequests = requestSamples
    .filter((sample) => {
      const code = Number(sample.labels.status);
      return Number.isFinite(code) && code >= 400;
    })
    .reduce((sum, sample) => sum + sample.value, 0);

  const durationSum = metrics['epip_request_duration_seconds_sum']?.[0]?.value ?? 0;
  const durationCount = metrics['epip_request_duration_seconds_count']?.[0]?.value ?? 0;
  const avgLatencyMs = durationCount > 0 ? (durationSum / durationCount) * 1000 : 0;
  const errorRate = totalRequests > 0 ? (errorRequests / totalRequests) * 100 : 0;
  const cacheSamples = metrics['epip_cache_hit_ratio'] ?? [];
  const cacheHitRate =
    cacheSamples.length > 0
      ? (cacheSamples.reduce((sum, sample) => sum + sample.value, 0) / cacheSamples.length) * 100
      : 0;

  const timestamp = Date.now();
  return {
    timestamp,
    timestampLabel: new Date(timestamp).toLocaleTimeString('zh-CN', { hour12: false }),
    totalRequests,
    errorRate,
    avgLatencyMs,
    successRate: Math.max(0, 100 - errorRate),
    cacheHitRate: Math.max(0, Math.min(100, cacheHitRate)),
  };
};

const numberFormatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 });

const Metrics = ({ autoRefresh, refreshInterval }: MetricsProps) => {
  const metricsQuery = useMetrics({
    refetchInterval: autoRefresh ? refreshInterval : false,
  });

  const [history, setHistory] = useState<MetricSnapshot[]>([]);
  const [latestSnapshot, setLatestSnapshot] = useState<MetricSnapshot | null>(null);
  const [timeRange, setTimeRange] = useState<string>(RANGE_OPTIONS[0].value);

  useEffect(() => {
    if (!metricsQuery.data) return;
    const snapshot = buildSnapshot(metricsQuery.data);
    if (!snapshot) return;
    setLatestSnapshot(snapshot);
    setHistory((previous) => {
      const next = [...previous, snapshot];
      return next.length > 100 ? next.slice(next.length - 100) : next;
    });
  }, [metricsQuery.data]);

  const chartHistory = useMemo(() => {
    const range = RANGE_OPTIONS.find((option) => option.value === timeRange);
    if (!range) return history;
    const cutoff = Date.now() - range.duration;
    return history.filter((point) => point.timestamp >= cutoff);
  }, [history, timeRange]);

  const chartData = chartHistory.length > 0 ? chartHistory : latestSnapshot ? [latestSnapshot] : [];

  const isLoading = metricsQuery.isLoading && !metricsQuery.data;
  const errorMessage = metricsQuery.error instanceof Error ? metricsQuery.error.message : null;

  const handleManualRefresh = () => metricsQuery.refetch();

  const requestValue = latestSnapshot?.totalRequests ?? 0;
  const errorRateValue = latestSnapshot?.errorRate ?? 0;
  const latencyValue = latestSnapshot?.avgLatencyMs ?? 0;
  const cacheHitValue = latestSnapshot?.cacheHitRate ?? 0;

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <CardTitle>性能指标</CardTitle>
          <CardDescription>Prometheus 指标快照，评估实时流量与服务质量。</CardDescription>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="sm:w-48">
            <Select
              value={timeRange}
              onChange={(event) => setTimeRange(event.target.value)}
              disabled={history.length === 0}
            >
              {RANGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
          <Button variant="outline" onClick={handleManualRefresh} disabled={metricsQuery.isFetching}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            刷新指标
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {errorMessage ? (
          <div className="mb-4 rounded-2xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
            Prometheus 指标获取失败：{errorMessage}
          </div>
        ) : null}
        {isLoading ? (
          <div className="flex h-48 items-center justify-center">
            <Spinner label="指标加载中" />
          </div>
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              <MetricBadge label="请求总数" value={requestValue} suffix="次" />
              <MetricBadge label="错误率" value={errorRateValue} suffix="%" isWarning={errorRateValue > 5} />
              <MetricBadge label="平均延迟" value={latencyValue} suffix="ms" />
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-3">
              <Card className="border-slate-100 lg:col-span-2">
                <CardHeader>
                  <CardTitle className="text-base">延迟趋势</CardTitle>
                  <CardDescription>最近采样的请求平均延迟（毫秒）。</CardDescription>
                </CardHeader>
                <CardContent>
                  {chartData.length === 0 ? (
                    <div className="flex h-48 items-center justify-center text-sm text-slate-500">
                      暂无历史数据，等待自动刷新或手动采样。
                    </div>
                  ) : (
                    <LineChart
                      data={chartData}
                      dataKey="avgLatencyMs"
                      xKey="timestampLabel"
                      color="#0ea5e9"
                      yFormatter={(value) => `${Math.round(value)}ms`}
                      tooltipFormatter={(value) => `${value.toFixed(1)} ms`}
                    />
                  )}
                </CardContent>
              </Card>

              <Card className="border-slate-100">
                <CardHeader>
                  <CardTitle className="text-base">成功率 / 缓存命中</CardTitle>
                  <CardDescription>展示请求成功率与缓存命中率概览。</CardDescription>
                </CardHeader>
                <CardContent>
                  {latestSnapshot ? (
                    <>
                      <GaugeChart value={latestSnapshot.successRate} label="请求成功率" />
                      <div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
                        <div className="flex items-center justify-between">
                          <span>缓存命中率</span>
                          <span className="font-semibold text-slate-900">
                            {numberFormatter.format(cacheHitValue)}%
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          指标来源于每个租户上报的 epip_cache_hit_ratio。
                        </p>
                      </div>
                    </>
                  ) : (
                    <div className="flex h-48 items-center justify-center text-sm text-slate-500">
                      等待新的监控采样...
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

interface MetricBadgeProps {
  label: string;
  value: number;
  suffix?: string;
  isWarning?: boolean;
}

const MetricBadge = ({ label, value, suffix = '', isWarning = false }: MetricBadgeProps) => {
  const formatted =
    suffix.trim() === '%'
      ? `${numberFormatter.format(value)}%`
      : `${numberFormatter.format(value)}${suffix ? ` ${suffix}` : ''}`;

  return (
    <div
      className={cn(
        'rounded-2xl border border-slate-100 bg-white p-5 shadow-sm',
        isWarning && 'border-amber-200 bg-amber-50'
      )}
    >
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{formatted}</p>
    </div>
  );
};

export default Metrics;
