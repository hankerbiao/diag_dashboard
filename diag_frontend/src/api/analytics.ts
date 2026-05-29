import { fetchApi } from './fetch';
import type { DashboardInsights } from './types';

export const analyticsApi = {
  async getInsights(params?: {
    factory_id?: string; search_sn?: string; search_product_models?: string; days?: number; trend?: string;
  }) {
    const query = new URLSearchParams();
    if (params?.factory_id) query.set('factory_id', params.factory_id);
    if (params?.search_sn) query.set('search_sn', params.search_sn);
    if (params?.search_product_models) query.set('search_product_models', params.search_product_models);
    if (params?.days) query.set('days', String(params.days));
    if (params?.trend) query.set('trend', params.trend);
    const qs = query.toString();
    return fetchApi<DashboardInsights>(`/api/analytics/insights${qs ? `?${qs}` : ''}`);
  },
};