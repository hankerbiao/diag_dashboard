import type { DailyStatItem } from '../../../api/analytics';
import type { YieldTrendItem } from '../../../api/types';

/** ISO 周键，与后端 analytics_service 格式一致：2026-W22 */
function isoWeekKey(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${date.getUTCFullYear()}-W${week}`;
}

function bucketKey(dateStr: string, granularity: 'day' | 'week' | 'month'): string {
  if (granularity === 'day') return dateStr;
  if (granularity === 'month') return dateStr.slice(0, 7);
  return isoWeekKey(dateStr);
}

/** 将 v2 每日统计按日/周/月聚合为良率趋势序列（时间升序，供图表从左到右展示） */
export function buildYieldTrendFromDaily(
  daily: DailyStatItem[],
  granularity: 'day' | 'week' | 'month',
): YieldTrendItem[] {
  const buckets = new Map<string, { total: number; passed: number; failed: number }>();

  for (const item of daily) {
    const key = bucketKey(item.date, granularity);
    const prev = buckets.get(key) ?? { total: 0, passed: 0, failed: 0 };
    buckets.set(key, {
      total: prev.total + item.stats.total,
      passed: prev.passed + item.stats.passed,
      failed: prev.failed + item.stats.failed,
    });
  }

  return Array.from(buckets.entries())
    .map(([date, s]) => ({
      date,
      total: s.total,
      passed: s.passed,
      failed: s.failed,
      yield: s.total > 0 ? Number(((s.passed / s.total) * 100).toFixed(1)) : 0,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}
