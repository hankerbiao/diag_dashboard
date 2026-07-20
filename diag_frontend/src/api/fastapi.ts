// Backward compatibility - re-exports from split modules
export { fetchApi, API_BASE_URL, type ApiResponse } from './fetch';
export { getAccessToken } from './auth';
export type {
  TestLogItem, SimilarCaseItem, DiagnosisResult, FailedLogFile, SnHistoryItem, SnHistoryDetail,
  ErrorAnalysis, DiagnosisCache, FactorySite, SyncServer, SyncTestDetail,
  PaginatedResponse,
  FaultCategoryItem, YieldTrendItem, StationFailureItem, DecisionDistributionItem,
  ModelDefectItem, DashboardInsights, KnowledgeDoc, GlobalAiConfig,
  DiagnosisFeedback, DiagnosisFeedbackParams, DiagnosisRating
} from './types';
export { diagnosisApi } from './diagnosis';
export { factoryApi, syncApi } from './sync';
export { analyticsApi } from './analytics';
export { knowledgeBaseApi, settingsApi, type SearchReference, type KnowledgeSearchResult } from './knowledgeBase';