import { fetchApi } from './fetch';
import type { FactorySite, SyncServer, SyncTestDetail, PaginatedResponse } from './types';

export const factoryApi = {
  async list() { return fetchApi<FactorySite[]>('/api/factories'); },
};

/** MES 实时查询 + 厂区列表；历史数据同步见 scripts/weaveeye_sync.py */
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
};
