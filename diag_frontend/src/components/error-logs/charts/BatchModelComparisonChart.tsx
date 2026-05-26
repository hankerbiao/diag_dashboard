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
import { LayoutDashboard } from 'lucide-react';
import { useChartTheme } from '../../../hooks/useChartTheme';
import ChartHelp from './ChartHelp';
import type { ModelDefectItem } from '../../../api/fastapi';

interface Props {
  data: ModelDefectItem[];
  loading?: boolean;
}

export default function BatchModelComparisonChart({ data, loading }: Props) {
  const { isDark, textColor, gridColor, bgColor, borderColor } = useChartTheme();
  const tooltipBg = bgColor;

  if (loading) {
    return (
      <div className="rounded-lg border p-5 min-h-[300px] animate-pulse" style={{ backgroundColor: bgColor, borderColor }}>
        <div className="h-4 w-40 bg-slate-200 dark:bg-slate-700 rounded mb-4" />
        <div className="h-56 bg-slate-100 dark:bg-slate-800 rounded" />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="rounded-lg border p-5 min-h-[300px] flex flex-col items-center justify-center" style={{ backgroundColor: bgColor, borderColor }}>
        <LayoutDashboard className="w-8 h-8 mb-2 opacity-30" style={{ color: textColor }} />
        <span className="text-xs" style={{ color: textColor }}>暂无机型数据</span>
      </div>
    );
  }

  return (
    <div className="rounded-lg border p-5 flex flex-col min-h-[300px]" style={{ backgroundColor: bgColor, borderColor }}>
      <h3 className="text-[14px] font-bold flex items-center gap-2 mb-4 flex-none" style={{ color: isDark ? '#f1f5f9' : '#475569' }}>
        <LayoutDashboard className="w-4 h-4 text-indigo-500" />
        各机型测试数据对比
        <ChartHelp text="按最近测试时间（test_time）排序，取前10款活跃机型。对每款机型统计：总测试数（所有测试记录）、失败数（server_test_result=失败）、直通率（通过数÷总数×100%）。数据来源：sync_remote_test_details 关联 sync_remote_servers 获取 product_models。" />
      </h3>
      <div className="flex-1 min-h-0 -ml-4">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 25, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridColor} />
            <XAxis dataKey="model" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} dy={10} />
            <YAxis yAxisId="left" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
            <RechartsTooltip
              contentStyle={{ borderRadius: '8px', border: `1px solid ${borderColor}`, fontSize: '12px', backgroundColor: tooltipBg }}
              formatter={(value: number, name: string) => {
                if (name === '直通率') return [`${value}%`, '直通率'];
                return [value, name];
              }}
            />
            <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px', color: textColor }} />
            <Bar yAxisId="left" dataKey="total" name="总测试数" fill="#94a3b8" radius={[4, 4, 0, 0]} barSize={20}>
              <LabelList dataKey="total" position="top" fill={textColor} fontSize={10} fontWeight={600} />
            </Bar>
            <Bar yAxisId="left" dataKey="failed" name="失败数" fill="#ef4444" radius={[4, 4, 0, 0]} barSize={20}>
              <LabelList dataKey="failed" position="top" fill="#ef4444" fontSize={10} fontWeight={600} />
            </Bar>
            <Line yAxisId="right" type="monotone" dataKey="yield" name="直通率" stroke="#10b981" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
