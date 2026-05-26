import type { DashboardInsights } from '../../../api/fastapi';
import BatchModelComparisonChart from './BatchModelComparisonChart';
import BatchYieldTrendChart from './BatchYieldTrendChart';
import RootCausePieChart from './RootCausePieChart';

interface Props {
  data: DashboardInsights | null;
  loading: boolean;
  trend: 'day' | 'week' | 'month';
  onTrendChange: (g: 'day' | 'week' | 'month') => void;
}

export default function BatchTestCharts({ data, loading, trend, onTrendChange }: Props) {
  if (!data && !loading) return null;

  return (
    <div className="px-4 pb-4 flex flex-col gap-4">
      <BatchModelComparisonChart data={data?.model_defects ?? []} loading={loading} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BatchYieldTrendChart data={data?.yield_trend ?? []} loading={loading} trend={trend} onTrendChange={onTrendChange} />
        <RootCausePieChart data={data?.station_failures ?? []} loading={loading} />
      </div>
    </div>
  );
}
