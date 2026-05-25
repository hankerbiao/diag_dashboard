import { getAccessToken } from './auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  try {
    const token = getAccessToken();

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options?.headers,
      },
    });

    return await response.json();
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : '网络请求失败',
    };
  }
}

export interface DiagnosisResult {
  sn: string;
  category: string;
  summary: string;
  confidence: number;
  suggestions: string[];
  reference_logs: Array<{
    id: string;
    source: string;
    timestamp: string;
    content: string;
  }>;
  maintenance_history: Array<{
    id: string;
    date: string;
    component: string;
    action: string;
  }>;
}

export interface ErrorAnalysis {
  error_log: {
    id: string;
    sn: string;
    test_item: string;
    test_time: string;
    fail_details: string;
  };
  analysis: string;
  root_cause: string;
  repair_suggestions: string[];
  similar_cases: Array<{
    id: string;
    title: string;
    root_cause: string;
  }>;
}

export interface Settings {
  ai_api_url: string;
  ai_model: string;
  ai_temperature: number;
  active_kbs: string[];
}

// 诊断 API
export const diagnosisApi = {
  async diagnoseBySN(sn: string, factory: string): Promise<ApiResponse<DiagnosisResult>> {
    return fetchApi<DiagnosisResult>('/api/diagnosis/sn', {
      method: 'POST',
      body: JSON.stringify({ sn, factory }),
    });
  },

  async analyzeErrorLog(errorLogId: string): Promise<ApiResponse<ErrorAnalysis>> {
    return fetchApi<ErrorAnalysis>(`/api/diagnosis/error-log/${errorLogId}`, {
      method: 'POST',
    });
  },
};

// 设置 API
export const settingsApi = {
  async getSettings(): Promise<ApiResponse<Settings>> {
    return fetchApi<Settings>('/api/settings');
  },

  async updateSettings(settings: Partial<Settings>): Promise<ApiResponse<void>> {
    return fetchApi<void>('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  },
};

// ============================================================
// Sync Module Types
// ============================================================

export interface SyncServer {
  id: string;
  server_sn: string;
  order_id: string;
  model: string;
  product_models: string;
  host_ip: string;
  server_state: string;
  test_items: string;
  customer_name: string;
  alarm: number;
  synced_at: string;
}

export interface SyncTestDetail {
  id: string;
  server_sn: string;
  big_flow: string;
  detailed_flow: string;
  decision: string;
  server_test_result: string;
  test_time: string;
  fault_type1: string;
  fault_type2: string;
  fault_type3: string;
  log_path: string;
  mes_record: string;
}

export interface SyncJob {
  id: string;
  status: 'running' | 'success' | 'failed';
  started_at: string;
  finished_at: string | null;
  servers_total: number;
  servers_new: number;
  details_total: number;
  details_new: number;
  error_message: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

// 数据同步 API
export const syncApi = {
  async triggerSync(): Promise<ApiResponse<{ job_id: string }>> {
    return fetchApi<{ job_id: string }>('/api/sync/trigger', {
      method: 'POST',
    });
  },

  async getSyncStatus(): Promise<ApiResponse<SyncJob | null>> {
    return fetchApi<SyncJob | null>('/api/sync/status');
  },

  async getSyncJobs(params?: { page?: number; limit?: number }): Promise<ApiResponse<PaginatedResponse<SyncJob>>> {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    return fetchApi<PaginatedResponse<SyncJob>>(`/api/sync/jobs?${query.toString()}`);
  },

  async getServers(params: {
    search_sn?: string;
    search_product_models?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<PaginatedResponse<SyncServer>>> {
    const query = new URLSearchParams();
    if (params.search_sn) query.set('search_sn', params.search_sn);
    if (params.search_product_models) query.set('search_product_models', params.search_product_models);
    if (params.page) query.set('page', String(params.page));
    if (params.limit) query.set('limit', String(params.limit));
    return fetchApi<PaginatedResponse<SyncServer>>(`/api/sync/servers?${query.toString()}`);
  },

  async getTestDetails(
    serverSn: string,
    params?: { page?: number; limit?: number }
  ): Promise<ApiResponse<PaginatedResponse<SyncTestDetail>>> {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    return fetchApi<PaginatedResponse<SyncTestDetail>>(`/api/sync/servers/${serverSn}/test-details?${query.toString()}`);
  },
};

export { fetchApi };
