import { fetchApi, API_BASE_URL } from './fetch';
import { getAccessToken } from './auth';
import type {
  GlobalAiConfig,
  KnowledgeDoc,
  LogExtractionPrompt,
  LogExtractionPromptsResponse,
  MachineModelsResponse,
  RagflowDocumentsResponse,
  RuntimeConfig,
  RuntimeConfigResponse,
} from './types';

export interface SearchReference { chunk_id: string; content: string; similarity: number; doc_name: string; }
export interface KnowledgeSearchResult { references: SearchReference[]; }
export interface AiConfigDraft {
  api_key?: string;
  base_url?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  chat_template_kwargs?: { enable_thinking: boolean };
  timeout?: number;
  extraction_api_key?: string;
  extraction_base_url?: string;
  extraction_model?: string;
  extraction_max_tokens?: number;
  extraction_timeout?: number;
}
export interface AiConnectivityResult {
  service: 'answer' | 'extraction';
  label: string;
  success: boolean;
  model: string;
  base_url: string;
  latency_ms?: number;
  error?: string;
  reused_answer?: boolean;
}

export const knowledgeBaseApi = {
  async upload(
    file: File,
    title?: string,
    description?: string,
    tags?: string,
    knowledgeType?: 'troubleshooting' | 'repair_case' | 'operation_guide' | 'faq',
  ) {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    if (description) formData.append('description', description);
    if (tags) formData.append('tags', tags);
    if (knowledgeType) formData.append('knowledge_type', knowledgeType);
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
  async getRagflowStatus() {
    type DatasetSummary = { id: string; name: string; document_count: number; chunk_count: number };
    return fetchApi<{
      enabled: boolean;
      dataset: DatasetSummary | null;
      datasets?: DatasetSummary[];
    }>('/api/knowledge-base/ragflow/status');
  },
  async listRagflowDocuments() {
    return fetchApi<RagflowDocumentsResponse>('/api/knowledge-base/ragflow/documents');
  },
};

export const settingsApi = {
  async getAiConfig() { return fetchApi<GlobalAiConfig>('/api/settings/ai-config'); },
  async updateAiConfig(config: AiConfigDraft) {
    return fetchApi<void>('/api/settings/ai-config', { method: 'PUT', body: JSON.stringify(config) });
  },
  async testAiConfig(config: AiConfigDraft) {
    return fetchApi<{ all_connected: boolean; results: AiConnectivityResult[] }>(
      '/api/settings/ai-config/test',
      { method: 'POST', body: JSON.stringify(config) },
    );
  },
  async getMachineModels() { return fetchApi<MachineModelsResponse>('/api/settings/machine-models'); },
  async getRuntimeConfig() { return fetchApi<RuntimeConfigResponse>('/api/settings/runtime-config'); },
  async updateRuntimeConfig(body: Partial<RuntimeConfig>) {
    return fetchApi<{ config: RuntimeConfig }>('/api/settings/runtime-config', { method: 'PUT', body: JSON.stringify(body) });
  },
  async getExtractionPrompts() { return fetchApi<LogExtractionPromptsResponse>('/api/settings/log-extraction/prompts'); },
  async upsertExtractionPrompt(body: { model: string; system_prompt: string; user_template: string }) {
    return fetchApi<void>('/api/settings/log-extraction/prompts', { method: 'PUT', body: JSON.stringify(body) });
  },
  async deleteExtractionPrompt(model: string) {
    return fetchApi<void>(`/api/settings/log-extraction/prompts/${encodeURIComponent(model)}`, { method: 'DELETE' });
  },
};

export type { LogExtractionPrompt };
