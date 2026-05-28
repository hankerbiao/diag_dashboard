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

export interface TestLogItem {
  id: string;
  test_item: string;
  test_time: string;
  fail_details: string;
  fault_type1: string;
  fault_type2: string;
  fault_type3: string;
  decision: string;
  big_flow: string;
  log_path: string;
}

export interface SimilarCaseItem {
  id: string;
  title: string;
  root_cause: string;
  similarity: number;
}

export interface DiagnosisResult {
  sn: string;
  category: string;
  summary: string;
  confidence: number;
  root_cause_detail: string;
  affected_components: string[];
  suggestions: string[];
  preventive_measures: string[];
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
  test_logs: TestLogItem[];
  similar_cases: SimilarCaseItem[];
}

export interface SnHistoryItem {
  id: string;
  sn: string;
  factory: string;
  category: string;
  confidence: number;
  summary: string;
  created_at: string;
}

export interface SnHistoryDetail {
  id: string;
  sn: string;
  factory: string;
  diagnosis_result: DiagnosisResult;
  chat_messages: Array<{ role: string; content: string }>;
  created_at: string;
  updated_at: string;
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

export interface GlobalAiConfig {
  api_key: string;
  base_url: string;
  model: string;
  temperature: number;
  provider: string;
  updated_at: string;
  updated_by: string;
}

export interface DiagnosisCache {
  id: string;
  error_log_id: string;
  sn: string;
  test_item: string;
  root_cause: string;
  evidence: Array<{ log_line: string; conclusion: string }>;
  analysis: string;
  repair_suggestions: string[];
  knowledge_refs: Array<{ source: string; content: string }>;
  log_content: string;
  created_at: string;
  is_cached: boolean;
}

interface SSECallbacks<T> {
  onProgress: (stage: string, detail: string) => void;
  onComplete: (data: T) => void;
  onError: (message: string) => void;
  onToken?: (text: string) => void;
}

async function consumeSSE<T>(resp: Response, callbacks: SSECallbacks<T>): Promise<void> {
  if (!resp.ok || !resp.body) {
    callbacks.onError(`请求失败: ${resp.status}`);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const { onProgress, onComplete, onError, onToken } = callbacks;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      let currentEvent = '';
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (currentEvent === 'progress') {
              onProgress(data.stage, data.detail);
            } else if (currentEvent === 'token') {
              onToken?.(data.text);
            } else if (currentEvent === 'done') {
              if (data.success && data.data) {
                onComplete(data.data);
              } else {
                onError(data.message || '分析失败');
              }
            } else if (currentEvent === 'error') {
              onError(data.message || '未知错误');
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    }
  } catch (e) {
    onError(e instanceof Error ? e.message : '网络连接中断');
  }
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

  async analyzeErrorLogWithKB(errorLogId: string, logBaseUrl?: string): Promise<ApiResponse<DiagnosisCache>> {
    const params = logBaseUrl ? `?log_base_url=${encodeURIComponent(logBaseUrl)}` : '';
    return fetchApi<DiagnosisCache>(`/api/diagnosis/error-log/${errorLogId}/analyze${params}`, {
      method: 'POST',
    });
  },

  async analyzeSSE(
    endpoint: string,
    onProgress: (stage: string, detail: string) => void,
    onComplete: (data: DiagnosisCache) => void,
    onError: (message: string) => void,
    onToken?: (text: string) => void,
  ): Promise<void> {
    const token = getAccessToken();
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    await consumeSSE<DiagnosisCache>(resp, { onProgress, onComplete, onError, onToken });
  },

  async followUp(sn: string, question: string, diagnosisContext: string): Promise<ApiResponse<{ answer: string }>> {
    return fetchApi<{ answer: string }>('/api/diagnosis/sn/follow-up', {
      method: 'POST',
      body: JSON.stringify({ sn, question, diagnosis_context: diagnosisContext }),
    });
  },

  async getLogContent(sn: string, factory: string, logPath: string): Promise<ApiResponse<{ content: string }>> {
    const params = `log_path=${encodeURIComponent(logPath)}`;
    return fetchApi<{ content: string }>(`/api/diagnosis/sn/log-content?${params}`, {
      method: 'POST',
      body: JSON.stringify({ sn, factory }),
    });
  },

  async diagnoseBySNSse(
    sn: string, factory: string,
    onProgress: (stage: string, detail: string) => void,
    onComplete: (data: DiagnosisResult) => void,
    onError: (message: string) => void,
    onToken?: (text: string) => void,
  ): Promise<void> {
    const token = getAccessToken();
    const resp = await fetch(`${API_BASE_URL}/api/diagnosis/sn/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ sn, factory }),
    });
    await consumeSSE<DiagnosisResult>(resp, { onProgress, onComplete, onError, onToken });
  },

  async reAnalyzeErrorLog(errorLogId: string, logBaseUrl?: string): Promise<ApiResponse<DiagnosisCache>> {
    const params = logBaseUrl ? `?log_base_url=${encodeURIComponent(logBaseUrl)}` : '';
    return fetchApi<DiagnosisCache>(`/api/diagnosis/error-log/${errorLogId}/re-analyze${params}`, {
      method: 'POST',
    });
  },

  // SN 诊断历史记录
  async saveSnHistory(sn: string, factory: string, diagnosisResult: object): Promise<ApiResponse<{ id: string }>> {
    return fetchApi<{ id: string }>('/api/diagnosis/sn/save-history', {
      method: 'POST',
      body: JSON.stringify({ sn, factory, diagnosis_result: diagnosisResult }),
    });
  },

  async appendChatMessage(historyId: string, role: string, content: string): Promise<ApiResponse<void>> {
    return fetchApi<void>(`/api/diagnosis/sn/history/${historyId}/chat`, {
      method: 'PUT',
      body: JSON.stringify({ role, content }),
    });
  },

  async getSnHistoryList(params: {
    sn?: string; factory?: string; page?: number; limit?: number;
  }): Promise<ApiResponse<{ items: SnHistoryItem[]; total: number; page: number; limit: number }>> {
    const query = new URLSearchParams();
    if (params.sn) query.set('sn', params.sn);
    if (params.factory) query.set('factory', params.factory);
    if (params.page) query.set('page', String(params.page));
    if (params.limit) query.set('limit', String(params.limit));
    return fetchApi(`/api/diagnosis/sn/history?${query.toString()}`);
  },

  async getSnHistoryDetail(historyId: string): Promise<ApiResponse<SnHistoryDetail>> {
    return fetchApi<SnHistoryDetail>(`/api/diagnosis/sn/history/${historyId}`);
  },
};

// 设置 API
export const settingsApi = {
  async getAiConfig(): Promise<ApiResponse<GlobalAiConfig>> {
    return fetchApi<GlobalAiConfig>('/api/settings/ai-config');
  },

  async updateAiConfig(config: {
    api_key?: string;
    base_url?: string;
    model?: string;
    temperature?: number;
  }): Promise<ApiResponse<void>> {
    return fetchApi<void>('/api/settings/ai-config', {
      method: 'PUT',
      body: JSON.stringify(config),
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

export interface SearchReference {
  chunk_id: string;
  content: string;
  similarity: number;
  doc_name: string;
}

export interface KnowledgeSearchResult {
  references: SearchReference[];
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

  async search(question: string): Promise<ApiResponse<KnowledgeSearchResult>> {
    return fetchApi<KnowledgeSearchResult>('/api/knowledge-base/search', {
      method: 'POST',
      body: JSON.stringify({ question }),
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
