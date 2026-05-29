import { fetchApi, API_BASE_URL } from './fetch';
import { getAccessToken } from './auth';
import type { KnowledgeDoc, GlobalAiConfig } from './types';

export interface SearchReference { chunk_id: string; content: string; similarity: number; doc_name: string; }
export interface KnowledgeSearchResult { references: SearchReference[]; }

export const knowledgeBaseApi = {
  async upload(file: File, title?: string, description?: string, tags?: string) {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    if (description) formData.append('description', description);
    if (tags) formData.append('tags', tags);
    const token = getAccessToken();
    const response = await fetch(`${API_BASE_URL}/api/knowledge-base/documents`, {
      method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: formData,
    });
    return response.json() as Promise<{ success: boolean; data?: KnowledgeDoc; error?: string }>;
  },
  async list(params?: { search?: string; format?: string; tag?: string; page?: number; limit?: number; sync_status?: boolean }) {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.format) query.set('format', params.format);
    if (params?.tag) query.set('tag', params.tag);
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.sync_status) query.set('sync_status', 'true');
    const qs = query.toString();
    return fetchApi<{ items: KnowledgeDoc[]; total: number; page: number; limit: number }>(`/api/knowledge-base/documents${qs ? `?${qs}` : ''}`);
  },
  async delete(docId: string) { return fetchApi<void>(`/api/knowledge-base/documents/${docId}`, { method: 'DELETE' }); },
  async update(docId: string, data: { title?: string; description?: string; tags?: string[] }) {
    return fetchApi<KnowledgeDoc>(`/api/knowledge-base/documents/${docId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async search(question: string) { return fetchApi<KnowledgeSearchResult>('/api/knowledge-base/search', { method: 'POST', body: JSON.stringify({ question }) }); },
  async getFormats() { return fetchApi<{ formats: string[] }>('/api/knowledge-base/formats'); },
  async getRagflowStatus() { return fetchApi<{ enabled: boolean; dataset: { id: string; name: string; document_count: number; chunk_count: number } | null }>('/api/knowledge-base/ragflow/status'); },
};

export const settingsApi = {
  async getAiConfig() { return fetchApi<GlobalAiConfig>('/api/settings/ai-config'); },
  async updateAiConfig(config: { api_key?: string; base_url?: string; model?: string; temperature?: number }) {
    return fetchApi<void>('/api/settings/ai-config', { method: 'PUT', body: JSON.stringify(config) });
  },
};