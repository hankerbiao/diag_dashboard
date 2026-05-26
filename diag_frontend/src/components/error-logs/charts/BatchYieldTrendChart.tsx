import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import { useChartTheme } from '../../../hooks/useChartTheme';
import ChartHelp from './ChartHelp';
import type { YieldTrendItem } from '../../../api/fastapi';

interface Props {
  data: YieldTrendItem[];
  loading?: boolean;
  trend: 'day' | 'week' | 'month';
  onTrendChange: (g: 'day' | 'week' | 'month') => void;
}

const TREND_OPTIONS: { value: 'day' | 'week' | 'month'; label: string }[] = [
  { value: 'day', label: '日' },
  { value: 'week', label: '周' },
  { value: 'month', label: '月' },
];

const YIELD_GRADIENT_ID = 'colorYieldBatch';

export default function BatchYieldTrendChart({ data, loading, trend, onTrendChange }: Props) {
  const { isDark, textColor, gridColor, bgColor, borderColor } = useChartTheme();
  const tooltipBg = bgColor;

  if (loading) {
    return (
      <div className="rounded-lg border p-5 min-h-[260px] animate-pulse" style={{ backgroundColor: bgColor, borderColor }}>
        <div className="h-4 w-36 bg-slate-200 dark:bg-slate-700 rounded mb-4" />
        <div className="h-48 bg-slate-100 dark:bg-slate-800 rounded" />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="rounded-lg border p-5 min-h-[260px] flex flex-col items-center justify-center" style={{ backgroundColor: bgColor, borderColor }}>
        <TrendingUp className="w-8 h-8 mb-2 opacity-30" style={{ color: textColor }} />
        <span className="text-xs" style={{ color: textColor }}>暂无良率趋势数据</span>
      </div>
    );
  }

  return (
    <div className="rounded-lg border p-5 flex flex-col min-h-[260px]" style={{ backgroundColor: bgColor, borderColor }}>
      <div className="flex items-center justify-between mb-4 flex-none">
        <h3 className="text-[14px] font-bold flex items-center gap-2" style={{ color: isDark ? '#f1f5f9' : '#475569' }}>
          <TrendingUp className="w-4 h-4 text-emerald-500" />
          良率趋势
          <ChartHelp text="统计全部服务器近30天内所有测试记录的直通率趋势。按日/周/月聚合：直通率 = 通过数（server_test_result=成功）÷ 总测试数 × 100%。Y轴固定80%-100%区间，便于放大观察波动。" />
        </h3>
        <div className="flex rounded border overflow-hidden text-[11px]" style={{ borderColor }}>
          {TREND_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => onTrendChange(opt.value)}
              className="px-2.5 py-0.5 font-medium transition-colors"
              style={{
                backgroundColor: trend === opt.value ? (isDark ? '#334155' : '#e2e8f0') : 'transparent',
                color: trend === opt.value ? (isDark ? '#f1f5f9' : '#0f172a') : textColor,
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 min-h-0 -ml-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 15, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={YIELD_GRADIENT_ID} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridColor} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} dy={10} />
            <YAxis domain={[80, 100]} tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${v}%`} />
            <RechartsTooltip
              contentStyle={{ borderRadius: '8px', border: `1px solid ${borderColor}`, fontSize: '12px', backgroundColor: tooltipBg }}
              itemStyle={{ color: '#10b981', fontWeight: 'bold' }}
              formatter={(value: number) => [`${value}%`, '良率']}
              labelFormatter={(label: string) => `${trend === 'week' ? '周' : trend === 'month' ? '月' : '日期'}: ${label}`}
            />
            <Area type="monotone" dataKey="yield" name="良率" stroke="#10b981" strokeWidth={3} fillOpacity={1} fill={`url(#${YIELD_GRADIENT_ID})`} activeDot={{ r: 6, strokeWidth: 0, fill: '#10b981' }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
