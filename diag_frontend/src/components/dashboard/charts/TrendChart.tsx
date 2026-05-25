import { useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import { trendDataDaily, trendDataWeekly, trendDataMonthly } from '../../../data/mockData';
import { Activity } from 'lucide-react';
import { useTheme } from '../../../contexts/ThemeContext';

export default function TrendChart() {
  const [timeRange, setTimeRange] = useState<'day' | 'week' | 'month'>('day');
  const { theme } = useTheme();

  const isDark = theme === 'dark';
  const textColor = isDark ? '#94a3b8' : '#64748b';
  const gridColor = isDark ? '#334155' : '#f1f5f9';
  const bgColor = isDark ? '#1e293b' : '#ffffff';
  const borderColor = isDark ? '#334155' : '#e2e8f0';

  const currentTrendData =
    timeRange === 'day'
      ? trendDataDaily
      : timeRange === 'week'
        ? trendDataWeekly
        : trendDataMonthly;

  return (
    <div
      className="col-span-1 lg:col-span-2 rounded-lg shadow-sm border p-4"
      style={{
        backgroundColor: bgColor,
        borderColor: borderColor,
      }}
    >
      <div className="flex justify-between items-center mb-6">
        <h3
          className="text-[13px] font-bold flex items-center gap-2"
          style={{ color: isDark ? '#f1f5f9' : '#475569' }}
        >
          <Activity className="w-4 h-4 text-indigo-500" />
          测试阻断历史趋势
        </h3>
        <div
          className="flex p-0.5 rounded-md shadow-inner border"
          style={{
            backgroundColor: isDark ? '#1e293b' : '#f8fafc',
            borderColor: isDark ? '#475657' : '#e2e8f0',
          }}
        >
          {(['day', 'week', 'month'] as const).map((range, idx) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className="px-4 py-1 text-[11px] font-bold rounded"
              style={
                timeRange === range
                  ? {
                      backgroundColor: bgColor,
                      color: '#4f46e5',
                      border: `1px solid ${borderColor}`,
                      boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                    }
                  : {
                      color: isDark ? '#64748b' : '#64748b',
                    }
              }
            >
              {['日度', '周度', '月度'][idx]}
            </button>
          ))}
        </div>
      </div>

      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={currentTrendData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorIssues" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridColor} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: textColor }} axisLine={false} tickLine={false} dy={10} />
            <YAxis tick={{ fontSize: 10, fill: textColor }} axisLine={false} tickLine={false} />
            <RechartsTooltip
              contentStyle={{
                borderRadius: '8px',
                border: `1px solid ${borderColor}`,
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                fontSize: '12px',
                backgroundColor: bgColor,
              }}
              itemStyle={{ color: '#4f46e5', fontWeight: 'bold' }}
            />
            <Area
              type="monotone"
              dataKey="issues"
              name="阻断数量"
              stroke="#4f46e5"
              strokeWidth={3}
              fillOpacity={1}
              fill="url(#colorIssues)"
              activeDot={{ r: 6, strokeWidth: 0, fill: '#4f46e5' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}