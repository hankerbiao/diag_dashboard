// ============ Shared Types ============
export interface TestLogItem {
  id: string; test_item: string; test_time: string; fail_details: string;
  fault_type1: string; fault_type2: string; fault_type3: string; decision: string;
  big_flow: string; log_path: string;
}

export interface SimilarCaseItem {
  id: string; title: string; root_cause: string; similarity: number;
}

export interface DiagnosisResult {
  sn: string; category: string; summary: string; confidence: number;
  root_cause_detail: string; affected_components: string[]; suggestions: string[];
  preventive_measures: string[];
  reference_logs: Array<{ id: string; source: string; timestamp: string; content: string }>;
  maintenance_history: Array<{ id: string; date: string; component: string; action: string }>;
  test_logs: TestLogItem[];
  failed_test_logs?: TestLogItem[];
  failed_log_files?: FailedLogFile[];
  merged_error_log?: string;
  similar_cases: SimilarCaseItem[];
}

export interface FailedLogFile {
  test_item: string;
  test_time: string;
  log_path: string;
  extracted_content: string;
  matched_lines: number;
  total_lines: number;
  ai_extracted: boolean;
  processing_mode:
    | 'single'
    | 'chunked'
    | 'prefiltered_chunked'
    | 'prefiltered_empty'
    | 'regex_fallback'
    | string;
  segment_count: number;
  successful_segments: number;
  failed_segments: number;
  extraction_duration_ms: number;
  model_used: string;
  prompt_model?: string;
  preprocessing_applied?: boolean;
  preprocessing_original_lines?: number;
  preprocessing_kept_lines?: number;
  preprocessing_removed_lines?: number;
  preprocessing_retention_ratio?: number;
  preprocessing_level_lines?: number;
  preprocessing_anomaly_entries?: number;
  source_size?: number;
  downloaded_size?: number;
  source_line_count?: number;
  source_truncated?: boolean;
  truncation_strategy?: string;
  retry_count?: number;
}

export interface SnHistoryItem {
  id: string; sn: string; factory: string; category: string;
  confidence: number; summary: string; created_at: string;
  user_id?: string; user_itcode?: string; user_name?: string;
}

export interface SnHistoryDetail {
  id: string; sn: string; factory: string; diagnosis_result: DiagnosisResult;
  chat_messages: Array<{ role: string; content: string }>;
  created_at: string; updated_at: string;
  feedback_rating?: DiagnosisRating;
  feedback_comment?: string;
  user_id?: string; user_itcode?: string; user_name?: string;
}

export interface ErrorAnalysis {
  error_log: { id: string; sn: string; test_item: string; test_time: string; fail_details: string };
  analysis: string; root_cause: string; repair_suggestions: string[];
  similar_cases: Array<{ id: string; title: string; root_cause: string }>;
}

export interface DiagnosisCache {
  id: string; error_log_id: string; sn: string; test_item: string; root_cause: string;
  evidence: Array<{ log_line: string; conclusion: string }>; analysis: string;
  repair_suggestions: string[]; knowledge_refs: Array<{ source: string; content: string }>;
  log_content: string; created_at: string; is_cached: boolean;
}

export interface FactorySite {
  id?: string; factory_id: string; name: string; base_url: string; log_base_url?: string;
}

export interface SyncServer {
  id: string; server_sn: string; order_id: string; model: string; product_models: string;
  host_ip: string; server_state: string; test_items: string; next_item: string; position: string;
  customer_name: string; alarm: number; synced_at: string;
}

export interface SyncTestDetail {
  id: string; server_sn: string; big_flow: string; detailed_flow: string; decision: string;
  server_test_result: string; test_time: string; fault_type1: string; fault_type2: string;
  fault_type3: string; log_path: string; mes_record: string;
}

export interface PaginatedResponse<T> { items: T[]; total: number; page: number; limit: number; }

export interface FaultCategoryItem { name: string; count: number; }
export interface YieldTrendItem { date: string; total: number; passed: number; failed: number; yield: number; }
export interface StationFailureItem { station: string; count: number; }
export interface DecisionDistributionItem { decision: string; count: number; }
export interface ModelDefectItem { model: string; total: number; failed: number; yield: number; }

export interface DashboardInsights {
  fault_categories: FaultCategoryItem[]; fault_subcategories: FaultCategoryItem[];
  yield_trend: YieldTrendItem[]; station_failures: StationFailureItem[];
  decision_distribution: DecisionDistributionItem[]; model_defects: ModelDefectItem[];
}

export interface KnowledgeDoc {
  id: string; title: string; description: string; format: string; size_bytes: number;
  status: string; tags: string[]; uploaded_at: string;
}

export interface RagflowDatasetSummary {
  id: string;
  name: string;
  document_count: number;
  chunk_count: number;
}

export interface RagflowDocument {
  id: string;
  dataset_id: string;
  dataset_name: string;
  name: string;
  format: string;
  size_bytes: number;
  chunk_count: number;
  token_count: number;
  status: string;
  progress: number;
  created_at: string;
  updated_at: string;
}

export interface RagflowDocumentsResponse {
  enabled: boolean;
  datasets: RagflowDatasetSummary[];
  items: RagflowDocument[];
  total: number;
}

export interface GlobalAiConfig {
  api_key: string; base_url: string; model: string;
  temperature: number | null; max_tokens: number | null;
  provider: string; chat_template_kwargs: { enable_thinking: boolean } | null;
  timeout: number | null; updated_at: string; updated_by: string;
  // 错误日志提取模型（快速）—— 留空表示复用上方回答模型配置
  extraction_api_key: string; extraction_base_url: string; extraction_model: string;
  extraction_max_tokens: number | null; extraction_timeout: number | null;
}

export interface LogExtractionPrompt {
  model: string;
  is_default: boolean;
  system_prompt: string;
  user_template: string;
  updated_at: string;
  updated_by: string;
}

export interface MachineModelsResponse {
  models: string[];
}

export interface LogExtractionPromptsResponse {
  prompts: LogExtractionPrompt[];
}

export type DiagnosisRating = 'solved' | 'partially' | 'unsolved';
export type FeedbackStatus = 'pending' | 'processing' | 'resolved' | 'ignored';

export interface DiagnosisFeedback {
  id: string;
  history_id?: string;
  sn: string;
  factory: string;
  rating: DiagnosisRating;
  comment?: string;
  diagnosis_context?: string;
  status: FeedbackStatus;
  resolution_note?: string;
  knowledge_document_ids?: string[];
  knowledge_title?: string;
  knowledge_uploaded_at?: string;
  submitter?: {
    id: string;
    email: string;
  };
  created_at: string;
  updated_at?: string;
}

export interface FeedbackSummary {
  total: number;
  solved: number;
  partially: number;
  unsolved: number;
  pending: number;
  processing: number;
  solved_rate: number;
}

export interface FeedbackListResponse {
  items: DiagnosisFeedback[];
  total: number;
  page: number;
  limit: number;
  summary: FeedbackSummary;
}

export interface DiagnosisFeedbackParams {
  history_id?: string;
  sn: string;
  factory: string;
  rating: DiagnosisRating;
  comment?: string;
  diagnosis_context?: string;
}
