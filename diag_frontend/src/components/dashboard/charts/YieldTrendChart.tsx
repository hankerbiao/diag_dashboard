import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import { yieldTrendData } from '../../../data/mockData';
import { Activity } from 'lucide-react';
import { useTheme } from '../../../contexts/ThemeContext';

export default function YieldTrendChart() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const textColor = isDark ? '#94a3b8' : '#64748b';
  const gridColor = isDark ? '#334155' : '#f1f5f9';
  const bgColor = isDark ? '#1e293b' : '#ffffff';
  const borderColor = isDark ? '#334155' : '#e2e8f0';
  const tooltipBg = isDark ? '#1e293b' : '#ffffff';

  return (
    <div
      className="rounded-lg shadow-sm border p-5 flex flex-col min-h-[260px]"
      style={{
        backgroundColor: bgColor,
        borderColor: borderColor,
      }}
    >
      <h3
        className="text-[14px] font-bold flex items-center gap-2 mb-4 flex-none"
        style={{ color: isDark ? '#f1f5f9' : '#475569' }}
      >
        <Activity className="w-4 h-4 text-emerald-500" />
        过去7天整体直通率趋势
      </h3>
      <div className="flex-1 min-h-0 -ml-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={yieldTrendData} margin={{ top: 15, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorYield" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridColor} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} dy={10} />
            <YAxis
              domain={['dataMin - 1', 'auto']}
              tick={{ fontSize: 11, fill: textColor }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(val) => `${val}%`}
            />
            <RechartsTooltip
              contentStyle={{
                borderRadius: '8px',
                border: `1px solid ${borderColor}`,
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                fontSize: '12px',
                backgroundColor: tooltipBg,
              }}
              itemStyle={{ color: '#10b981', fontWeight: 'bold' }}
            />
            <Area
              type="monotone"
              dataKey="yield"
              name="直通率"
              stroke="#10b981"
              strokeWidth={3}
              fillOpacity={1}
              fill="url(#colorYield)"
              activeDot={{ r: 6, strokeWidth: 0, fill: '#10b981' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}