// Backward compatibility - re-exports from split modules
export { fetchApi, API_BASE_URL, type ApiResponse } from './fetch';
export { getAccessToken } from './auth';
export type {
  TestLogItem, SimilarCaseItem, DiagnosisResult, FailedLogFile, SnHistoryItem, SnHistoryDetail,
  ErrorAnalysis, DiagnosisCache, FactorySite, SyncServer, SyncTestDetail,
  PaginatedResponse,
  FaultCategoryItem, YieldTrendItem, StationFailureItem, DecisionDistributionItem,
  ModelDefectItem, DashboardInsights, KnowledgeDoc, RagflowDatasetSummary,
  RagflowDocument, RagflowDocumentsResponse, GlobalAiConfig,
  RuntimeConfig, RuntimeConfigResponse,
  DiagnosisFeedback, DiagnosisFeedbackParams, DiagnosisRating, FeedbackStatus,
  FeedbackSummary, FeedbackListResponse,
  LogExtractionPrompt, MachineModelsResponse, LogExtractionPromptsResponse
} from './types';
export { diagnosisApi } from './diagnosis';
export { factoryApi, syncApi } from './sync';
export { analyticsApi } from './analytics';
export { userAnalyticsApi } from './userAnalytics';
export type {
  UserAnalyticsOverview,
  UserAnalyticsSummary,
  UserDailyUsage,
  FeatureUsage,
  UserUsageRow,
  UserFeature,
} from './userAnalytics';
export {
  knowledgeBaseApi,
  settingsApi,
  type AiConfigDraft,
  type AiConnectivityResult,
  type KnowledgeSearchResult,
  type SearchReference,
} from './knowledgeBase';
