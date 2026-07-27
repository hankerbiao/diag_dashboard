import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Activity,
  ArrowDownRight,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CalendarPlus,
  RefreshCw,
  Search,
  UserRoundCheck,
  UsersRound,
} from 'lucide-react';
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { userAnalyticsApi, type UserAnalyticsOverview, type UserUsageRow } from '../../api/userAnalytics';
import { useChartTheme } from '../../hooks/useChartTheme';
import { useDebounce } from '../../hooks/useDebounce';

const RANGE_OPTIONS = [
  { value: 7, label: '近 7 天' },
  { value: 30, label: '近 30 天' },
  { value: 90, label: '近 90 天' },
] as const;

const FEATURE_LABELS: Record<string, string> = {
  diagnosis: '单机诊断',
  diagnosis_run: 'AI 诊断执行',
  error_logs: '异常看板',
  knowledge_base: '知识库',
  feedback: '反馈管理',
  user_analytics: '用户看板',
  settings: '系统设置',
  login: '登录',
  other: '其他',
};

const FEATURE_COLORS = ['#2563eb', '#10b981', '#f59e0b', '#e11d48', '#06b6d4', '#8b5cf6', '#64748b'];

const STATUS_META: Record<UserUsageRow['status'], { label: string; color: string; bg: string }> = {
  active: { label: '活跃', color: '#047857', bg: 'rgba(16, 185, 129, 0.12)' },
  dormant: { label: '低频', color: '#b45309', bg: 'rgba(245, 158, 11, 0.14)' },
  inactive: { label: '沉默', color: '#64748b', bg: 'rgba(100, 116, 139, 0.12)' },
};

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value);
}

function formatDate(value: string, includeTime = false): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, includeTime ? 16 : 10);
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    ...(includeTime ? { hour: '2-digit', minute: '2-digit', hour12: false } : {}),
  }).format(date);
}

function ChangeTag({ value, suffix = '较上期' }: { value: number; suffix?: string }) {
  const positive = value >= 0;
  const Icon = positive ? ArrowUpRight : ArrowDownRight;
  return (
    <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold" style={{ color: positive ? '#059669' : '#e11d48' }}>
      <Icon className="h-3 w-3" />
      {Math.abs(value)}% {suffix}
    </span>
  );
}

interface MetricCardProps {
  label: string;
  value: number;
  icon: ReactNode;
  color: string;
  detail: ReactNode;
}

function MetricCard({ label, value, icon, color, detail }: MetricCardProps) {
  return (
    <section
      className="relative min-h-[112px] overflow-hidden rounded-lg border p-4"
      style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
    >
      <div className="absolute inset-x-0 top-0 h-0.5" style={{ backgroundColor: color }} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[12px] font-semibold" style={{ color: 'var(--color-text-secondary)' }}>{label}</p>
          <p className="mt-1 text-[26px] font-bold leading-tight" style={{ color: 'var(--color-text-primary)' }}>{formatNumber(value)}</p>
        </div>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ backgroundColor: `${color}16`, color }}>
          {icon}
        </span>
      </div>
      <div className="mt-2 min-h-4 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>{detail}</div>
    </section>
  );
}

function LoadingView() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((item) => <div key={item} className="h-28 rounded-lg bg-slate-200/70 dark:bg-slate-800" />)}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.7fr)]">
        <div className="h-[318px] rounded-lg bg-slate-200/70 dark:bg-slate-800" />
        <div className="h-[318px] rounded-lg bg-slate-200/70 dark:bg-slate-800" />
      </div>
      <div className="h-72 rounded-lg bg-slate-200/70 dark:bg-slate-800" />
    </div>
  );
}

export default function UserAnalyticsTab() {
  const chartTheme = useChartTheme();
  const [days, setDays] = useState(30);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 350);
  const [data, setData] = useState<UserAnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    const response = await userAnalyticsApi.getOverview({
      days,
      page,
      limit: 10,
      search: debouncedSearch || undefined,
    });
    if (response.success && response.data) {
      setData(response.data);
    } else {
      setError(response.error || '用户统计加载失败');
    }
    setLoading(false);
  }, [days, page, debouncedSearch]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    setPage(1);
  }, [days, debouncedSearch]);

  const featureData = useMemo(
    () => (data?.features ?? []).map((item, index) => ({
      ...item,
      name: FEATURE_LABELS[item.feature] || item.feature,
      fill: FEATURE_COLORS[index % FEATURE_COLORS.length],
    })),
    [data?.features],
  );

  const totalPages = Math.max(1, Math.ceil((data?.users.total ?? 0) / 10));
  const summary = data?.summary;

  return (
    <main className="h-full overflow-y-auto custom-scrollbar" style={{ backgroundColor: 'var(--color-bg-primary)' }}>
      <div className="mx-auto w-full max-w-[1600px] p-4 sm:p-5">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-[16px] font-bold" style={{ color: 'var(--color-text-primary)' }}>用户运营概览</h2>
            <p className="mt-1 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
              {data?.generated_at ? `数据更新于 ${formatDate(data.generated_at, true)}` : '正在读取最新数据'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex h-8 overflow-hidden rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
              {RANGE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setDays(option.value)}
                  className="px-3 text-[11px] font-semibold transition-colors"
                  style={{
                    backgroundColor: days === option.value ? 'var(--color-accent)' : 'var(--color-bg-secondary)',
                    color: days === option.value ? '#fff' : 'var(--color-text-secondary)',
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => void loadData()}
              className="flex h-8 w-8 items-center justify-center rounded-lg border"
              style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
              title="刷新数据"
              aria-label="刷新数据"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {loading && !data ? (
          <LoadingView />
        ) : error && !data ? (
          <div className="flex min-h-[420px] flex-col items-center justify-center rounded-lg border" style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
            <BarChart3 className="mb-3 h-9 w-9 opacity-30" style={{ color: 'var(--color-text-secondary)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{error}</p>
            <button type="button" onClick={() => void loadData()} className="mt-4 inline-flex h-8 items-center gap-2 rounded-lg px-3 text-xs font-semibold text-white" style={{ backgroundColor: 'var(--color-accent)' }}>
              <RefreshCw className="h-3.5 w-3.5" />重试
            </button>
          </div>
        ) : data && summary ? (
          <div className="space-y-4">
            {error && <div className="rounded-lg border px-3 py-2 text-xs" style={{ borderColor: '#f59e0b', color: '#b45309', backgroundColor: 'rgba(245,158,11,0.08)' }}>{error}</div>}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="注册用户" value={summary.total_users} color="#2563eb" icon={<UsersRound className="h-4.5 w-4.5" />} detail={<span>本周期新增 <b style={{ color: 'var(--color-text-primary)' }}>{formatNumber(summary.new_users)}</b> 人</span>} />
              <MetricCard label="周期活跃用户" value={summary.active_users} color="#10b981" icon={<UserRoundCheck className="h-4.5 w-4.5" />} detail={<ChangeTag value={summary.changes.active_users} />} />
              <MetricCard label="今日活跃用户" value={summary.today_active_users} color="#f59e0b" icon={<Activity className="h-4.5 w-4.5" />} detail={<span>人均使用 <b style={{ color: 'var(--color-text-primary)' }}>{summary.avg_usage_per_active_user}</b> 次</span>} />
              <MetricCard label="周期使用次数" value={summary.total_usage} color="#e11d48" icon={<BarChart3 className="h-4.5 w-4.5" />} detail={<ChangeTag value={summary.changes.total_usage} />} />
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.7fr)]">
              <section className="min-h-[318px] min-w-0 rounded-lg border p-4" style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-[13px] font-bold" style={{ color: 'var(--color-text-primary)' }}>每日使用趋势</h3>
                    <p className="mt-0.5 text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>柱形为活跃用户，曲线为使用次数</p>
                  </div>
                  <span className="inline-flex items-center gap-1 text-[10px]" style={{ color: 'var(--color-text-secondary)' }}><CalendarPlus className="h-3.5 w-3.5" />新增用户同步统计</span>
                </div>
                <div className="h-[250px] min-w-0 w-full">
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                    minWidth={0}
                    initialDimension={{ width: 720, height: 250 }}
                  >
                    <ComposedChart data={data.daily} margin={{ top: 12, right: 8, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="usageArea" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#e11d48" stopOpacity={0.22} />
                          <stop offset="95%" stopColor="#e11d48" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid vertical={false} strokeDasharray="3 3" stroke={chartTheme.gridColor} />
                      <XAxis dataKey="date" tickFormatter={(value: string) => value.slice(5)} tick={{ fill: chartTheme.textColor, fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={22} />
                      <YAxis tick={{ fill: chartTheme.textColor, fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{ backgroundColor: chartTheme.bgColor, borderColor: chartTheme.borderColor, borderRadius: 8, fontSize: 11 }}
                        labelFormatter={(value) => `日期 ${value}`}
                        formatter={(value, name) => [formatNumber(Number(value ?? 0)), name === 'active_users' ? '活跃用户' : name === 'usage_count' ? '使用次数' : '新增用户']}
                      />
                      <Bar dataKey="active_users" fill="#2563eb" radius={[3, 3, 0, 0]} maxBarSize={22} />
                      <Bar dataKey="new_users" fill="#10b981" radius={[3, 3, 0, 0]} maxBarSize={12} />
                      <Area type="monotone" dataKey="usage_count" stroke="#e11d48" strokeWidth={2.5} fill="url(#usageArea)" dot={false} activeDot={{ r: 4 }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </section>

              <section className="min-h-[318px] min-w-0 rounded-lg border p-4" style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
                <h3 className="text-[13px] font-bold" style={{ color: 'var(--color-text-primary)' }}>功能使用分布</h3>
                {featureData.length === 0 ? (
                  <div className="flex h-[250px] items-center justify-center text-xs" style={{ color: 'var(--color-text-secondary)' }}>暂无功能使用记录</div>
                ) : (
                  <div className="grid h-[260px] grid-cols-[minmax(150px,0.9fr)_minmax(120px,1.1fr)] items-center gap-2">
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                      minWidth={0}
                      initialDimension={{ width: 180, height: 260 }}
                    >
                      <PieChart>
                        <Pie data={featureData} dataKey="count" nameKey="name" innerRadius="52%" outerRadius="76%" paddingAngle={2} stroke="none" />
                        <Tooltip contentStyle={{ backgroundColor: chartTheme.bgColor, borderColor: chartTheme.borderColor, borderRadius: 8, fontSize: 11 }} formatter={(value) => [formatNumber(Number(value ?? 0)), '使用次数']} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="space-y-2 overflow-hidden">
                      {featureData.slice(0, 7).map((item) => (
                        <div key={item.feature} className="flex items-center justify-between gap-2 text-[11px]">
                          <span className="flex min-w-0 items-center gap-2" style={{ color: 'var(--color-text-secondary)' }}>
                            <span className="h-2 w-2 shrink-0 rounded-sm" style={{ backgroundColor: item.fill }} />
                            <span className="truncate">{item.name}</span>
                          </span>
                          <b style={{ color: 'var(--color-text-primary)' }}>{formatNumber(item.count)}</b>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            </div>

            <section className="overflow-hidden rounded-lg border" style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
              <div className="flex flex-col gap-3 border-b px-4 py-3 sm:flex-row sm:items-center sm:justify-between" style={{ borderColor: 'var(--color-border)' }}>
                <div>
                  <h3 className="text-[13px] font-bold" style={{ color: 'var(--color-text-primary)' }}>用户使用明细</h3>
                  <p className="mt-0.5 text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>共 {formatNumber(data.users.total)} 位用户</p>
                </div>
                <label className="relative block w-full sm:w-64">
                  <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: 'var(--color-text-secondary)' }} />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="搜索姓名、ITCode 或邮箱"
                    className="h-8 w-full rounded-lg border bg-transparent pl-9 pr-3 text-[11px] outline-none focus:ring-2 focus:ring-blue-500/20"
                    style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
                  />
                </label>
              </div>

              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full min-w-[920px] text-left text-[11px]">
                  <thead style={{ color: 'var(--color-text-secondary)', backgroundColor: chartTheme.isDark ? '#182235' : '#f8fafc' }}>
                    <tr>
                      <th className="px-4 py-2.5 font-semibold">用户</th>
                      <th className="px-4 py-2.5 font-semibold">状态</th>
                      <th className="px-4 py-2.5 font-semibold">注册时间</th>
                      <th className="px-4 py-2.5 font-semibold">最近活跃</th>
                      <th className="px-4 py-2.5 text-right font-semibold">登录次数</th>
                      <th className="px-4 py-2.5 text-right font-semibold">诊断次数</th>
                      <th className="px-4 py-2.5 text-right font-semibold">总使用次数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.users.items.length === 0 ? (
                      <tr><td colSpan={7} className="px-4 py-12 text-center" style={{ color: 'var(--color-text-secondary)' }}>没有匹配的用户</td></tr>
                    ) : data.users.items.map((user) => {
                      const status = STATUS_META[user.status];
                      return (
                        <tr key={user.id} className="border-t hover:bg-slate-50/70 dark:hover:bg-slate-800/40" style={{ borderColor: 'var(--color-border)' }}>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2.5">
                              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold" style={{ color: '#2563eb', backgroundColor: 'rgba(37,99,235,0.1)' }}>{user.name.slice(0, 2).toUpperCase()}</span>
                              <span className="min-w-0">
                                <span className="block max-w-[190px] truncate font-semibold" style={{ color: 'var(--color-text-primary)' }}>{user.name}</span>
                                <span className="block max-w-[190px] truncate text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>{user.itcode || user.email || '-'}</span>
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3"><span className="inline-flex rounded px-2 py-0.5 font-semibold" style={{ color: status.color, backgroundColor: status.bg }}>{status.label}</span></td>
                          <td className="px-4 py-3" style={{ color: 'var(--color-text-secondary)' }}>{formatDate(user.created_at)}</td>
                          <td className="px-4 py-3" style={{ color: 'var(--color-text-secondary)' }}>{formatDate(user.last_active_at, true)}</td>
                          <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--color-text-primary)' }}>{formatNumber(user.login_count)}</td>
                          <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--color-text-primary)' }}>{formatNumber(user.diagnosis_count)}</td>
                          <td className="px-4 py-3 text-right font-mono font-bold" style={{ color: 'var(--color-accent)' }}>{formatNumber(user.usage_count)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between border-t px-4 py-3" style={{ borderColor: 'var(--color-border)' }}>
                <span className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>第 {page} / {totalPages} 页</span>
                <div className="flex gap-1.5">
                  <button type="button" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="flex h-7 w-7 items-center justify-center rounded-lg border disabled:cursor-not-allowed disabled:opacity-35" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }} title="上一页" aria-label="上一页"><ArrowLeft className="h-3.5 w-3.5" /></button>
                  <button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} className="flex h-7 w-7 items-center justify-center rounded-lg border disabled:cursor-not-allowed disabled:opacity-35" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }} title="下一页" aria-label="下一页"><ArrowRight className="h-3.5 w-3.5" /></button>
                </div>
              </div>
            </section>
          </div>
        ) : null}
      </div>
    </main>
  );
}
