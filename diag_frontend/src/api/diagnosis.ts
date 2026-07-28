import { fetchApi, API_BASE_URL, type ApiResponse } from './fetch';
import { getAccessToken } from './auth';
import type {
  DiagnosisResult, DiagnosisCache, ErrorAnalysis, SnHistoryItem, SnHistoryDetail,
  DiagnosisRating, FeedbackListResponse, FeedbackStatus,
} from './types';

export interface DiagnosisProgressMeta {
  file_count?: number;
  machine_model?: string;
  prompt_model?: string;
  system_prompt?: string;
  user_template?: string;
  log_comparison?: {
    test_item: string;
    log_path: string;
    original_lines: number;
    kept_lines: number;
    removed_lines: number;
    removal_rate: number;
    preprocessing_applied: boolean;
    recognized_level_lines: number;
    anomaly_entries: number;
    source_size?: number;
    downloaded_size?: number;
    source_line_count?: number;
    source_truncated?: boolean;
    truncation_strategy?: string;
  };
}

export const diagnosisApi = {
  async diagnoseBySN(sn: string, factory: string) {
    return fetchApi<DiagnosisResult>('/api/diagnosis/sn', { method: 'POST', body: JSON.stringify({ sn, factory }) });
  },
  async analyzeErrorLog(errorLogId: string) {
    return fetchApi<ErrorAnalysis>(`/api/diagnosis/error-log/${errorLogId}`, { method: 'POST' });
  },
  async analyzeErrorLogWithKB(errorLogId: string, logBaseUrl?: string) {
    const params = logBaseUrl ? `?log_base_url=${encodeURIComponent(logBaseUrl)}` : '';
    return fetchApi<DiagnosisCache>(`/api/diagnosis/error-log/${encodeURIComponent(errorLogId)}/analyze${params}`, { method: 'POST' });
  },
  async diagnoseBySNAnalyze(
    sn: string,
    factory: string,
    onProgress?: (
      stage: string,
      detail: string,
      status: 'running' | 'skipped',
      meta: DiagnosisProgressMeta,
    ) => void,
    signal?: AbortSignal,
  ): Promise<ApiResponse<DiagnosisResult>> {
    const token = getAccessToken();
    const response = await fetch(`${API_BASE_URL}/api/diagnosis/sn/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ sn, factory }),
      signal,
    });
    if (!response.ok || !response.body) {
      try {
        return await response.json() as ApiResponse<DiagnosisResult>;
      } catch {
        return { success: false, error: `诊断请求失败（HTTP ${response.status}）` };
      }
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? '';
      for (const frame of frames) {
        const data = frame.split(/\r?\n/)
          .filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).trim())
          .join('\n');
        if (!data) continue;
        const event = JSON.parse(data) as {
          type: 'progress' | 'result' | 'error';
          stage?: string;
          detail?: string;
          status?: 'running' | 'skipped';
          meta?: DiagnosisProgressMeta;
          data?: DiagnosisResult;
          error?: string;
          error_detail?: string;
          error_code?: string;
        };
        if (event.type === 'progress') {
          onProgress?.(
            event.stage ?? '',
            event.detail ?? '',
            event.status ?? 'running',
            event.meta ?? {},
          );
        } else if (event.type === 'result' && event.data) {
          return { success: true, data: event.data };
        } else if (event.type === 'error') {
          return {
            success: false,
            error: event.error || '诊断失败',
            errorDetail: event.error_detail,
            errorCode: event.error_code,
            stage: event.stage,
          };
        }
      }
      if (done) break;
    }
    return { success: false, error: '诊断连接已结束，但未收到分析结果' };
  },
  async analyzeErrorLogKB(
    errorLogId: string,
    logBaseUrl?: string,
    context?: Record<string, string>,
  ) {
    const params = logBaseUrl ? `?log_base_url=${encodeURIComponent(logBaseUrl)}` : '';
    return fetchApi<DiagnosisCache>(
      `/api/diagnosis/error-log/${encodeURIComponent(errorLogId)}/analyze${params}`,
      { method: 'POST', ...(context ? { body: JSON.stringify(context) } : {}) },
    );
  },
  async reAnalyzeErrorLog(
    errorLogId: string,
    logBaseUrl?: string,
    context?: Record<string, string>,
  ) {
    const params = logBaseUrl ? `?log_base_url=${encodeURIComponent(logBaseUrl)}` : '';
    return fetchApi<DiagnosisCache>(
      `/api/diagnosis/error-log/${encodeURIComponent(errorLogId)}/re-analyze${params}`,
      { method: 'POST', ...(context ? { body: JSON.stringify(context) } : {}) },
    );
  },
  async followUp(sn: string, question: string, diagnosisContext: string) {
    return fetchApi<{ answer: string }>('/api/diagnosis/sn/follow-up', {
      method: 'POST', body: JSON.stringify({ sn, question, diagnosis_context: diagnosisContext }),
    });
  },
  async getLogContent(sn: string, factory: string, logPath: string) {
    return fetchApi<{ content: string }>(`/api/diagnosis/sn/log-content?log_path=${encodeURIComponent(logPath)}`, {
      method: 'POST', body: JSON.stringify({ sn, factory }),
    });
  },
  async saveSnHistory(sn: string, factory: string, diagnosisResult: object) {
    return fetchApi<{ id: string }>('/api/diagnosis/sn/save-history', {
      method: 'POST', body: JSON.stringify({ sn, factory, diagnosis_result: diagnosisResult }),
    });
  },
  async appendChatMessage(historyId: string, role: 'user' | 'assistant', content: string) {
    return fetchApi<void>(`/api/diagnosis/sn/history/${historyId}/chat`, {
      method: 'PUT', body: JSON.stringify({ role, content }),
    });
  },
  async getSnHistoryList(params: { sn?: string; factory?: string; page?: number; limit?: number }) {
    const query = new URLSearchParams();
    if (params.sn) query.set('sn', params.sn);
    if (params.factory) query.set('factory', params.factory);
    if (params.page) query.set('page', String(params.page));
    if (params.limit) query.set('limit', String(params.limit));
    return fetchApi<{ items: SnHistoryItem[]; total: number; page: number; limit: number }>(`/api/diagnosis/sn/history?${query.toString()}`);
  },
  async getSnHistoryDetail(historyId: string) {
    return fetchApi<SnHistoryDetail>(`/api/diagnosis/sn/history/${historyId}`);
  },
  async submitFeedback(params: {
    history_id?: string;
    sn: string;
    factory: string;
    rating: 'solved' | 'partially' | 'unsolved';
    comment?: string;
    diagnosis_context?: string;
  }) {
    return fetchApi<{ id: string }>('/api/diagnosis/feedback', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },
  async getFeedbackList(params: {
    factory?: string;
    rating?: DiagnosisRating | '';
    status?: FeedbackStatus | '';
    keyword?: string;
    page?: number;
    limit?: number;
  }) {
    const query = new URLSearchParams();
    if (params.factory) query.set('factory', params.factory);
    if (params.rating) query.set('rating', params.rating);
    if (params.status) query.set('status', params.status);
    if (params.keyword) query.set('keyword', params.keyword);
    if (params.page) query.set('page', String(params.page));
    if (params.limit) query.set('limit', String(params.limit));
    return fetchApi<FeedbackListResponse>(`/api/diagnosis/feedback?${query.toString()}`);
  },
  async updateFeedback(
    feedbackId: string,
    params: { status: FeedbackStatus; resolution_note?: string },
  ) {
    return fetchApi<import('./types').DiagnosisFeedback>(
      `/api/diagnosis/feedback/${encodeURIComponent(feedbackId)}`,
      { method: 'PATCH', body: JSON.stringify(params) },
    );
  },
  async linkFeedbackKnowledge(
    feedbackId: string,
    params: { document_ids: string[]; knowledge_title: string },
  ) {
    return fetchApi<import('./types').DiagnosisFeedback>(
      `/api/diagnosis/feedback/${encodeURIComponent(feedbackId)}/knowledge`,
      { method: 'POST', body: JSON.stringify(params) },
    );
  },
};
