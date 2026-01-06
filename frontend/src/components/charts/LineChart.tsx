import {
  CartesianGrid,
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export interface LineChartProps<T extends Record<string, unknown>> {
  data: T[];
  dataKey: keyof T;
  xKey?: keyof T;
  color?: string;
  height?: number;
  yFormatter?: (value: number) => string;
  tooltipFormatter?: (value: number) => string;
}

const formatNumber = (value: number) => {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return Number.isFinite(value) ? value.toFixed(0) : '0';
};

const LineChart = <T extends Record<string, unknown>>({
  data,
  dataKey,
  xKey,
  color = '#6366f1',
  height = 260,
  yFormatter,
  tooltipFormatter,
}: LineChartProps<T>) => {
  const axisKey = (xKey ?? 'timestamp') as string;
  const seriesKey = dataKey as string;
  const formatTick = (value: string | number) => {
    if (typeof value === 'number') {
      return yFormatter ? yFormatter(value) : formatNumber(value);
    }
    return value;
  };

  const tooltipValueFormatter = (value: number) =>
    tooltipFormatter ? tooltipFormatter(value) : formatNumber(value);

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RechartsLineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey={axisKey}
            tick={{ fontSize: 12, fill: '#94a3b8' }}
            tickLine={false}
            axisLine={{ stroke: '#e2e8f0' }}
          />
          <YAxis
            tick={{ fontSize: 12, fill: '#94a3b8' }}
            tickLine={false}
            axisLine={{ stroke: '#e2e8f0' }}
            tickFormatter={formatTick}
            width={60}
          />
          <Tooltip
            contentStyle={{ borderRadius: '0.75rem', border: '1px solid #e2e8f0' }}
            labelStyle={{ color: '#0f172a', fontWeight: 600 }}
            formatter={(value: number) => [tooltipValueFormatter(value), '']}
          />
          <Line
            type="monotone"
            dataKey={seriesKey}
            stroke={color}
            strokeWidth={2.4}
            dot={false}
            activeDot={{ r: 5, strokeWidth: 0 }}
          />
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default LineChart;
