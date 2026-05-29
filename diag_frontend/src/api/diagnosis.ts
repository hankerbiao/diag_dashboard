import { fetchApi, API_BASE_URL } from './fetch';
import { getAccessToken } from './auth';
import type {
  DiagnosisResult, DiagnosisCache, ErrorAnalysis, SnHistoryItem, SnHistoryDetail
} from './types';

interface SSECallbacks<T> {
  onProgress: (stage: string, detail: string) => void;
  onComplete: (data: T) => void;
  onError: (message: string) => void;
  onToken?: (text: string) => void;
}

async function consumeSSE<T>(resp: Response, callbacks: SSECallbacks<T>, signal?: AbortSignal): Promise<void> {
  if (!resp.ok || !resp.body) { callbacks.onError(`请求失败: ${resp.status}`); return; }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const { onProgress, onComplete, onError, onToken } = callbacks;
  signal?.addEventListener('abort', () => reader.cancel());

  try {
    while (true) {
      if (signal?.aborted) { callbacks.onError('请求已取消'); break; }
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      let currentEvent = '';
      for (const line of lines) {
        if (line.startsWith('event: ')) currentEvent = line.slice(7).trim();
        else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (currentEvent === 'progress') onProgress(data.stage, data.detail);
            else if (currentEvent === 'token') onToken?.(data.text);
            else if (currentEvent === 'done') {
              if (data.success && data.data) onComplete(data.data);
              else onError(data.message || '分析失败');
            } else if (currentEvent === 'error') onError(data.message || '未知错误');
          } catch { /* skip malformed */ }
        }
      }
    }
  } catch (e) { onError(e instanceof Error ? e.message : '网络连接中断'); }
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
    return fetchApi<DiagnosisCache>(`/api/diagnosis/error-log/${errorLogId}/analyze${params}`, { method: 'POST' });
  },
  async analyzeSSE(endpoint: string, onProgress: SSECallbacks<DiagnosisCache>['onProgress'],
    onComplete: SSECallbacks<DiagnosisCache>['onComplete'], onError: SSECallbacks<DiagnosisCache>['onError'],
    onToken?: SSECallbacks<DiagnosisCache>['onToken']) {
    const token = getAccessToken();
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    await consumeSSE(resp, { onProgress, onComplete, onError, onToken });
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
  async diagnoseBySNSse(sn: string, factory: string,
    onProgress: SSECallbacks<DiagnosisResult>['onProgress'], onComplete: SSECallbacks<DiagnosisResult>['onComplete'],
    onError: SSECallbacks<DiagnosisResult>['onError'], onToken?: SSECallbacks<DiagnosisResult>['onToken']): Promise<AbortController> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 600_000);
    try {
      const token = getAccessToken();
      const resp = await fetch(`${API_BASE_URL}/api/diagnosis/sn/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ sn, factory }), signal: controller.signal,
      });
      await consumeSSE(resp, { onProgress, onComplete, onError, onToken }, controller.signal);
    } finally { clearTimeout(timeoutId); }
    return controller;
  },
  async reAnalyzeErrorLog(errorLogId: string, logBaseUrl?: string) {
    const params = logBaseUrl ? `?log_base_url=${encodeURIComponent(logBaseUrl)}` : '';
    return fetchApi<DiagnosisCache>(`/api/diagnosis/error-log/${errorLogId}/re-analyze${params}`, { method: 'POST' });
  },
  async saveSnHistory(sn: string, factory: string, diagnosisResult: object) {
    return fetchApi<{ id: string }>('/api/diagnosis/sn/save-history', {
      method: 'POST', body: JSON.stringify({ sn, factory, diagnosis_result: diagnosisResult }),
    });
  },
  async appendChatMessage(historyId: string, role: string, content: string) {
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
};