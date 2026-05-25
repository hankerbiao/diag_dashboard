import {
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { defectDistributionData, COLORS } from '../../../data/mockData';
import { AlertTriangle } from 'lucide-react';
import { useTheme } from '../../../contexts/ThemeContext';

export default function DefectPieChart() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const bgColor = isDark ? '#1e293b' : '#ffffff';
  const borderColor = isDark ? '#334155' : '#e2e8f0';
  const tooltipBg = isDark ? '#1e293b' : '#ffffff';
  const textColor = isDark ? '#94a3b8' : '#475569';

  return (
    <div
      className="col-span-1 rounded-lg shadow-sm border p-5 flex flex-col min-h-[300px]"
      style={{
        backgroundColor: bgColor,
        borderColor: borderColor,
      }}
    >
      <h3
        className="text-[14px] font-bold flex items-center gap-2 mb-4 flex-none"
        style={{ color: isDark ? '#f1f5f9' : '#475569' }}
      >
        <AlertTriangle className="w-4 h-4 text-rose-500" />
        不良根因占比 Top 5
      </h3>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={defectDistributionData}
              cx="50%"
              cy="45%"
              innerRadius={55}
              outerRadius={85}
              paddingAngle={3}
              dataKey="value"
            >
              {defectDistributionData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <RechartsTooltip
              contentStyle={{
                borderRadius: '8px',
                border: `1px solid ${borderColor}`,
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                fontSize: '12px',
                backgroundColor: tooltipBg,
              }}
              itemStyle={{ fontWeight: 'bold', color: textColor }}
            />
            <Legend
              iconType="circle"
              layout="horizontal"
              verticalAlign="bottom"
              align="center"
              wrapperStyle={{ fontSize: '11px', paddingTop: '10px', color: textColor }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}