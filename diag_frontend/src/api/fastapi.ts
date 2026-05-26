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
// Sync Module — 查询已同步数据（只读）
// ============================================================

export interface FactorySite {
  id?: string;
  factory_id: string;
  name: string;
  base_url: string;
  log_base_url?: string;
}

export interface SyncServer {
  id: string;
  server_sn: string;
  order_id: string;
  model: string;
  product_models: string;
  host_ip: string;
  server_state: string;
  test_items: string;
  next_item: string;
  position: string;
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

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

// 数据查询 API（只读 — 数据由独立脚本同步）
export const syncApi = {
  async getServers(params: {
    factory_id?: string;
    search_sn?: string;
    search_product_models?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<PaginatedResponse<SyncServer>>> {
    const query = new URLSearchParams();
    if (params.factory_id) query.set('factory_id', params.factory_id);
    if (params.search_sn) query.set('search_sn', params.search_sn);
    if (params.search_product_models) query.set('search_product_models', params.search_product_models);
    if (params.page) query.set('page', String(params.page));
    if (params.limit) query.set('limit', String(params.limit));
    return fetchApi<PaginatedResponse<SyncServer>>(`/api/sync/servers?${query.toString()}`);
  },

  async getTestDetails(
    serverSn: string,
    params?: { factory_id?: string; page?: number; limit?: number }
  ): Promise<ApiResponse<PaginatedResponse<SyncTestDetail>>> {
    const query = new URLSearchParams();
    if (params?.factory_id) query.set('factory_id', params.factory_id);
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    return fetchApi<PaginatedResponse<SyncTestDetail>>(`/api/sync/servers/${serverSn}/test-details?${query.toString()}`);
  },
};

// 厂区查询 API（只读 — 配置来自 YAML 文件）
export const factoryApi = {
  async list(): Promise<ApiResponse<FactorySite[]>> {
    return fetchApi<FactorySite[]>('/api/factories');
  },
};

// ============================================================
// Analytics Module
// ============================================================

export interface FaultCategoryItem {
  name: string;
  count: number;
}

export interface YieldTrendItem {
  date: string;
  total: number;
  passed: number;
  failed: number;
  yield: number;
}

export interface StationFailureItem {
  station: string;
  count: number;
}

export interface DecisionDistributionItem {
  decision: string;
  count: number;
}

export interface ModelDefectItem {
  model: string;
  total: number;
  failed: number;
  yield: number;
}

export interface DashboardInsights {
  fault_categories: FaultCategoryItem[];
  fault_subcategories: FaultCategoryItem[];
  yield_trend: YieldTrendItem[];
  station_failures: StationFailureItem[];
  decision_distribution: DecisionDistributionItem[];
  model_defects: ModelDefectItem[];
}

// 数据分析 API
export const analyticsApi = {
  async getInsights(params?: {
    factory_id?: string;
    search_sn?: string;
    search_product_models?: string;
    days?: number;
    trend?: string;
  }): Promise<ApiResponse<DashboardInsights>> {
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

// ============================================================
// Knowledge Base Module
// ============================================================

export interface KnowledgeDoc {
  id: string;
  title: string;
  description: string;
  format: string;
  size_bytes: number;
  status: string;
  tags: string[];
  uploaded_at: string;
}

export const knowledgeBaseApi = {
  async upload(file: File, title?: string, description?: string, tags?: string): Promise<ApiResponse<KnowledgeDoc>> {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    if (description) formData.append('description', description);
    if (tags) formData.append('tags', tags);

    const token = getAccessToken();
    const response = await fetch(`${API_BASE_URL}/api/knowledge-base/documents`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    return response.json();
  },

  async list(params?: {
    search?: string;
    format?: string;
    tag?: string;
    page?: number;
    limit?: number;
    sync_status?: boolean;
  }): Promise<ApiResponse<{ items: KnowledgeDoc[]; total: number; page: number; limit: number }>> {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.format) query.set('format', params.format);
    if (params?.tag) query.set('tag', params.tag);
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.sync_status) query.set('sync_status', 'true');
    const qs = query.toString();
    return fetchApi(`/api/knowledge-base/documents${qs ? `?${qs}` : ''}`);
  },

  async delete(docId: string): Promise<ApiResponse<void>> {
    return fetchApi(`/api/knowledge-base/documents/${docId}`, { method: 'DELETE' });
  },

  async update(docId: string, data: { title?: string; description?: string; tags?: string[] }): Promise<ApiResponse<KnowledgeDoc>> {
    return fetchApi(`/api/knowledge-base/documents/${docId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async getFormats(): Promise<ApiResponse<{ formats: string[] }>> {
    return fetchApi('/api/knowledge-base/formats');
  },

  async getRagflowStatus(): Promise<ApiResponse<{
    enabled: boolean;
    dataset: {
      id: string;
      name: string;
      document_count: number;
      chunk_count: number;
    } | null;
  }>> {
    return fetchApi('/api/knowledge-base/ragflow/status');
  },
};

export { fetchApi };
