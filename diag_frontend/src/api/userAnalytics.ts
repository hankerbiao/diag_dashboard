import { fetchApi } from './fetch';

export type UserFeature =
  | 'diagnosis'
  | 'error_logs'
  | 'knowledge_base'
  | 'feedback'
  | 'user_analytics'
  | 'settings';

export interface UserAnalyticsSummary {
  total_users: number;
  new_users: number;
  active_users: number;
  today_active_users: number;
  total_usage: number;
  avg_usage_per_active_user: number;
  changes: {
    new_users: number;
    active_users: number;
    total_usage: number;
  };
}

export interface UserDailyUsage {
  date: string;
  new_users: number;
  active_users: number;
  usage_count: number;
}

export interface FeatureUsage {
  feature: string;
  count: number;
}

export interface UserUsageRow {
  id: string;
  name: string;
  itcode: string;
  email: string;
  created_at: string;
  last_login_at: string;
  last_active_at: string;
  login_count: number;
  diagnosis_count: number;
  usage_count: number;
  status: 'active' | 'dormant' | 'inactive';
}

export interface UserAnalyticsOverview {
  summary: UserAnalyticsSummary;
  daily: UserDailyUsage[];
  features: FeatureUsage[];
  users: {
    items: UserUsageRow[];
    total: number;
    page: number;
    limit: number;
  };
  generated_at: string;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value));
  });
  return `?${query.toString()}`;
}

export const userAnalyticsApi = {
  getOverview(params: { days: number; page: number; limit?: number; search?: string }) {
    return fetchApi<UserAnalyticsOverview>(`/api/user-analytics/overview${buildQuery(params)}`);
  },

  trackFeature(feature: UserFeature) {
    return fetchApi<{ recorded: boolean }>('/api/user-analytics/events', {
      method: 'POST',
      body: JSON.stringify({ feature }),
    });
  },
};
