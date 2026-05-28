export type NavigationTab = 'diagnosis' | 'error_logs' | 'knowledge_base' | 'settings';
export type FactoryLocation = string;

export interface GlobalAiConfig {
  api_key: string;
  base_url: string;
  model: string;
  temperature: number;
  provider: string;
  updated_at: string;
  updated_by: string;
}

export interface SNAnalysisResult {
  sn: string;
  category: string;
  summary: string;
  suggestions: string[];
  referenceLogs: {
    id: string;
    source: string;
    timestamp: string;
    content: string;
  }[];
  maintenanceHistory: {
    id: string;
    date: string;
    component: string;
    action: string;
  }[];
}

export interface ErrorLogRow {
  id: string;
  sn: string;
  testItem: string;
  testTime: string;
  status: string;
  decision: string;
  faultTypes: string;
  logPath: string;
  mesRecord: string;
}


export type {
  FaultCategoryItem,
  YieldTrendItem,
  StationFailureItem,
  DecisionDistributionItem,
  ModelDefectItem,
  DashboardInsights,
} from '../api/fastapi';