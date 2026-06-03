import { fetchApi } from './fetch';
import type { DashboardInsights } from './types';

function buildQuery(params?: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  if (!params) return '';
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') query.set(k, String(v));
  }
  const qs = query.toString();
  return qs ? `?${qs}` : '';
}

export const analyticsApi = {
  /** v1 — 实时聚合（保留） */
  async getInsights(params?: {
    factory_id?: string; search_sn?: string; search_product_models?: string; days?: number; trend?: string;
  }) {
    return fetchApi<DashboardInsights>(`/api/analytics/insights${buildQuery(params)}`);
  },

  /** v2 — 按日统计列表 */
  async getDailyStats(params?: { factory_id?: string; days?: number }) {
    return fetchApi<{ items: DailyStatItem[]; total_days: number }>(
      `/api/analytics/v2/daily${buildQuery(params)}`,
    );
  },

  /** v2 — 汇总统计 */
  async getSummary(params?: { factory_id?: string; days?: number }) {
    return fetchApi<SummaryResponse>(`/api/analytics/v2/summary${buildQuery(params)}`);
  },
};

export interface DailyStatItem {
  date: string;
  factory_id: string;
  computed_at: string;
  stats: {
    total: number;
    passed: number;
    failed: number;
    fault_categories: { name: string; count: number }[];
    fault_subcategories: { name: string; count: number }[];
    station_failures: { station: string; count: number }[];
    decision_distribution: { decision: string; count: number }[];
    model_defects: {
      model: string; total: number; failed: number; yield: number;
      station_failures: { station: string; count: number }[];
      fault_categories: { name: string; count: number }[];
    }[];
  };
}

export interface SummaryResponse {
  total: number;
  passed: number;
  failed: number;
  avg_yield: number;
  total_days: number;
  fault_categories: { name: string; count: number }[];
  fault_subcategories: { name: string; count: number }[];
  station_failures: { station: string; count: number }[];
  decision_distribution: { decision: string; count: number }[];
  model_defects: {
    model: string; total: number; failed: number; yield: number;
    station_failures: { station: string; count: number }[];
    fault_categories: { name: string; count: number }[];
  }[];
}