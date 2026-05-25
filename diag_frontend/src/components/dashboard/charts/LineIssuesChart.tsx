import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  LabelList,
} from 'recharts';
import { lineIssuesData } from '../../../data/mockData';
import { Factory } from 'lucide-react';
import { useTheme } from '../../../contexts/ThemeContext';

export default function LineIssuesChart() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const textColor = isDark ? '#94a3b8' : '#475569';
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
        <Factory className="w-4 h-4 text-blue-500" />
        各测试线体失败拦截数
      </h3>
      <div className="flex-1 min-h-0 -ml-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={lineIssuesData} margin={{ top: 15, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridColor} />
            <XAxis dataKey="line" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} dy={10} />
            <YAxis tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
            <RechartsTooltip
              cursor={{ fill: isDark ? '#334155' : '#f8fafc' }}
              contentStyle={{
                borderRadius: '8px',
                border: `1px solid ${borderColor}`,
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                fontSize: '12px',
                backgroundColor: tooltipBg,
              }}
              itemStyle={{ color: '#3b82f6', fontWeight: 'bold' }}
            />
            <Bar dataKey="issues" name="拦截数" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={24}>
              <LabelList dataKey="issues" position="top" fill="#3b82f6" fontSize={11} fontWeight={600} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}