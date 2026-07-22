import { fetchApi, API_BASE_URL, type ApiResponse } from './fetch';
import { getAccessToken } from './auth';
import type {
  DiagnosisResult, DiagnosisCache, ErrorAnalysis, SnHistoryItem, SnHistoryDetail
} from './types';

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
    onProgress?: (stage: string, detail: string) => void,
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
          data?: DiagnosisResult;
          error?: string;
        };
        if (event.type === 'progress') {
          onProgress?.(event.stage ?? '', event.detail ?? '');
        } else if (event.type === 'result' && event.data) {
          return { success: true, data: event.data };
        } else if (event.type === 'error') {
          return { success: false, error: event.error || '诊断失败' };
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
};
