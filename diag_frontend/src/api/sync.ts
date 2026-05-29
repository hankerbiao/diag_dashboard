import { fetchApi } from './fetch';
import type { FactorySite, SyncServer, SyncTestDetail, PaginatedResponse, AutoSyncConfig, SyncJobItem } from './types';

export const factoryApi = {
  async list() { return fetchApi<FactorySite[]>('/api/factories'); },
};

export const syncApi = {
  async getServers(params: { factory_id?: string; search_sn?: string; search_product_models?: string; page?: number; limit?: number }) {
    const query = new URLSearchParams();
    if (params.factory_id) query.set('factory_id', params.factory_id);
    if (params.search_sn) query.set('search_sn', params.search_sn);
    if (params.search_product_models) query.set('search_product_models', params.search_product_models);
    if (params.page) query.set('page', String(params.page));
    if (params.limit) query.set('limit', String(params.limit));
    return fetchApi<PaginatedResponse<SyncServer>>(`/api/sync/servers?${query.toString()}`);
  },
  async getTestDetails(serverSn: string, params?: { factory_id?: string; page?: number; limit?: number }) {
    const query = new URLSearchParams();
    if (params?.factory_id) query.set('factory_id', params.factory_id);
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    return fetchApi<PaginatedResponse<SyncTestDetail>>(`/api/sync/servers/${serverSn}/test-details?${query.toString()}`);
  },
  async getJobs(params?: { factory_id?: string; page?: number; limit?: number }) {
    const query = new URLSearchParams();
    if (params?.factory_id) query.set('factory_id', params.factory_id);
    if (params?.page) query.set('page', String(params.page ?? 1));
    if (params?.limit) query.set('limit', String(params?.limit ?? 5));
    return fetchApi<PaginatedResponse<SyncJobItem>>(`/api/sync/jobs?${query.toString()}`);
  },
  async getJobDetail(jobId: string) { return fetchApi<SyncJobItem>(`/api/sync/jobs/${jobId}`); },
  async getAutoConfig() { return fetchApi<AutoSyncConfig>('/api/sync/auto-config'); },
  async updateAutoConfig(config: {
    sims_enabled?: boolean; sims_interval_minutes?: number;
    factory_overrides?: Record<string, { enabled?: boolean; interval_minutes?: number; cutoff_hours?: number }>;
    mes_enabled?: boolean; mes_interval_minutes?: number;
  }) { return fetchApi<AutoSyncConfig>('/api/sync/auto-config', { method: 'PUT', body: JSON.stringify(config) }); },
  async triggerSync(factory?: string) {
    const params = factory ? `?factory=${encodeURIComponent(factory)}` : '';
    return fetchApi<{ job_id: string; status: string }>(`/api/sync/trigger${params}`, { method: 'POST' });
  },
  async triggerMesSync() { return fetchApi<{ job_id: string; status: string }>('/api/sync/trigger-mes', { method: 'POST' }); },
};