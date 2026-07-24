import {
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import { AlertTriangle } from 'lucide-react';
import { useChartTheme } from '../../../hooks/useChartTheme';
import ChartHelp from './ChartHelp';
import type { StationFailureItem } from '../../../api/fastapi';

interface Props {
  data: StationFailureItem[];
  loading?: boolean;
}

const COLORS = [
  '#3b82f6', '#ef4444', '#f59e0b', '#22c55e', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];

export default function RootCausePieChart({ data, loading }: Props) {
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
        <AlertTriangle className="w-8 h-8 mb-2 opacity-30" style={{ color: textColor }} />
        <span className="text-xs" style={{ color: textColor }}>暂无不良根因数据</span>
      </div>
    );
  }

  const total = data.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="rounded-lg border p-5 flex flex-col min-h-[260px]" style={{ backgroundColor: bgColor, borderColor }}>
      <h3 className="text-[14px] font-bold flex items-center gap-2 mb-4 flex-none" style={{ color: isDark ? '#f1f5f9' : '#475569' }}>
        <AlertTriangle className="w-4 h-4" style={{ color: '#ef4444' }} />
        不良根因占比 TOP10
        <ChartHelp text="统计全部服务器近30天内各工站的不良分布占比（基于 server_test_result ≠ 成功的记录），展示 TOP10 根因及占比。数据来源：sync_remote_test_details" />
      </h3>
      <div className="flex-1 min-h-0 flex items-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="count"
              nameKey="station"
              cx="50%"
              cy="50%"
              outerRadius="75%"
              innerRadius="45%"
              paddingAngle={2}
              label={({ value }) => {
                const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0.0';
                return `${pct}%`;
              }}
              labelLine={{ stroke: textColor, strokeWidth: 1, strokeOpacity: 0.3 }}
            >
              {data.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <RechartsTooltip
              contentStyle={{ borderRadius: '8px', border: `1px solid ${borderColor}`, fontSize: '12px', backgroundColor: tooltipBg }}
              formatter={(value: number, name: string) => {
                const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0.0';
                return [`${value} 次 (${pct}%)`, name];
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        {/* Legend */}
        <div className="ml-2 shrink-0 space-y-1.5 max-w-[180px]">
          {data.map((item, index) => (
            <div key={item.station} className="flex items-center gap-1.5 text-[11px]" style={{ color: textColor }}>
              <span
                className="w-2.5 h-2.5 rounded-sm shrink-0"
                style={{ backgroundColor: COLORS[index % COLORS.length] }}
              />
              <span className="truncate">{item.station}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
