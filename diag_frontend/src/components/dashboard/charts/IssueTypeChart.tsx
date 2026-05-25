import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import { issueTypeData } from '../../../data/mockData';
import { AlertTriangle } from 'lucide-react';
import { useTheme } from '../../../contexts/ThemeContext';

export default function IssueTypeChart() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const textColor = isDark ? '#94a3b8' : '#475569';
  const gridColor = isDark ? '#334155' : '#f1f5f9';
  const bgColor = isDark ? '#1e293b' : '#ffffff';
  const borderColor = isDark ? '#334155' : '#e2e8f0';
  const tooltipBg = isDark ? '#1e293b' : '#ffffff';

  return (
    <div
      className="col-span-1 rounded-lg shadow-sm border p-4 flex flex-col"
      style={{
        backgroundColor: bgColor,
        borderColor: borderColor,
      }}
    >
      <h3
        className="text-[13px] font-bold flex items-center gap-2 mb-4"
        style={{ color: isDark ? '#f1f5f9' : '#475569' }}
      >
        <AlertTriangle className="w-4 h-4 text-rose-500" />
        问题暴露类型分布分布
      </h3>
      <div className="flex-1 w-full min-h-[160px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={issueTypeData} layout="vertical" margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} vertical={true} stroke={gridColor} />
            <XAxis type="number" hide />
            <YAxis
              dataKey="name"
              type="category"
              tick={{ fontSize: 11, fill: textColor, fontWeight: 500 }}
              axisLine={false}
              tickLine={false}
              width={60}
            />
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
            <Bar dataKey="count" name="发生频率" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={16}>
              {issueTypeData.map((_, index) => (
                <rect
                  key={`cell-${index}`}
                  fill={index === 0 ? '#ef4444' : index === 1 ? '#f97316' : '#3b82f6'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}