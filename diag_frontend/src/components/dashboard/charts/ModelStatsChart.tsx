import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  LabelList,
  ResponsiveContainer,
} from 'recharts';
import { modelStatsData } from '../../../data/mockData';
import { LayoutDashboard } from 'lucide-react';
import { useTheme } from '../../../contexts/ThemeContext';

export default function ModelStatsChart() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const textColor = isDark ? '#94a3b8' : '#475569';
  const gridColor = isDark ? '#334155' : '#f1f5f9';
  const bgColor = isDark ? '#1e293b' : '#ffffff';
  const borderColor = isDark ? '#334155' : '#e2e8f0';
  const tooltipBg = isDark ? '#1e293b' : '#ffffff';

  return (
    <div
      className="col-span-1 xl:col-span-2 rounded-lg shadow-sm border p-5 flex flex-col min-h-[300px]"
      style={{
        backgroundColor: bgColor,
        borderColor: borderColor,
      }}
    >
      <h3
        className="text-[14px] font-bold flex items-center gap-2 mb-4 flex-none"
        style={{ color: isDark ? '#f1f5f9' : '#475569' }}
      >
        <LayoutDashboard className="w-4 h-4 text-indigo-500" />
        各机型测试数据对比
      </h3>
      <div className="flex-1 min-h-0 -ml-4">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={modelStatsData} margin={{ top: 25, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridColor} />
            <XAxis
              dataKey="model"
              tick={{ fontSize: 11, fill: textColor }}
              axisLine={false}
              tickLine={false}
              dy={10}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11, fill: textColor }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11, fill: textColor }}
              axisLine={false}
              tickLine={false}
              domain={['dataMin - 5', 'auto']}
            />
            <RechartsTooltip
              contentStyle={{
                borderRadius: '8px',
                border: `1px solid ${borderColor}`,
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                fontSize: '12px',
                backgroundColor: tooltipBg,
              }}
            />
            <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px', color: textColor }} />
            <Bar
              yAxisId="left"
              dataKey="total"
              name="总测试数"
              fill="#94a3b8"
              radius={[4, 4, 0, 0]}
              barSize={20}
            >
              <LabelList
                dataKey="total"
                position="top"
                fill={textColor}
                fontSize={10}
                fontWeight={600}
              />
            </Bar>
            <Bar
              yAxisId="left"
              dataKey="failed"
              name="失败数"
              fill="#ef4444"
              radius={[4, 4, 0, 0]}
              barSize={20}
            >
              <LabelList
                dataKey="failed"
                position="top"
                fill="#ef4444"
                fontSize={10}
                fontWeight={600}
              />
            </Bar>
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="yield"
              name="直通率 (%)"
              stroke="#10b981"
              strokeWidth={3}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}