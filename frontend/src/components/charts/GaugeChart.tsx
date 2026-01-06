import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from 'recharts';

export interface GaugeChartProps {
  value: number;
  label?: string;
  color?: string;
  height?: number;
}

const clamp = (value: number) => Math.min(100, Math.max(0, value));

const GaugeChart = ({ value, label, color = '#22c55e', height = 220 }: GaugeChartProps) => {
  const normalizedValue = clamp(value);
  const chartData = [{ name: label ?? 'value', value: normalizedValue, fill: color }];

  return (
    <div className="relative w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          data={chartData}
          startAngle={180}
          endAngle={0}
          innerRadius="70%"
          outerRadius="100%"
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar background dataKey="value" clockWise cornerRadius={999} fill={color} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold text-slate-900">{normalizedValue.toFixed(1)}%</span>
        {label ? <span className="mt-1 text-sm text-slate-500">{label}</span> : null}
      </div>
    </div>
  );
};

export default GaugeChart;
