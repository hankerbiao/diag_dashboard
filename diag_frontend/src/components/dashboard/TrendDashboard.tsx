import TrendChart from './charts/TrendChart';
import IssueTypeChart from './charts/IssueTypeChart';

export default function TrendDashboard() {
  return (
    <div
      className="mx-4 mb-4 grid grid-cols-1 lg:grid-cols-3 gap-4 shrink-0 transition-all"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <TrendChart />
      <IssueTypeChart />
    </div>
  );
}