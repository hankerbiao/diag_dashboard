import ModelStatsChart from './charts/ModelStatsChart';
import DefectPieChart from './charts/DefectPieChart';
import YieldTrendChart from './charts/YieldTrendChart';
import LineIssuesChart from './charts/LineIssuesChart';

export default function ModelStatisticsDashboard() {
  return (
    <div
      className="mx-4 mb-4 flex-1 flex flex-col gap-4 min-h-0 overflow-y-auto animate-in fade-in duration-500 pr-2 pb-4 custom-scrollbar"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 flex-none lg:min-h-[320px]">
        <ModelStatsChart />
        <DefectPieChart />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-none lg:min-h-[280px]">
        <YieldTrendChart />
        <LineIssuesChart />
      </div>
    </div>
  );
}