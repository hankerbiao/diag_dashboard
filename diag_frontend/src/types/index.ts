export type NavigationTab = 'diagnosis' | 'error_logs' | 'settings';
export type FactoryLocation = '天津' | '天津三期' | '盘锦一期' | '盘锦二期' | '昆山' | '太原' | '安阳' | '桐乡' | '青岛' | '大同';

export interface AppSettings {
  aiApiUrl: string;
  aiApiKey: string;
  aiModel: string;
  aiTemperature: number;
  activeKBs: string[];
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

export const FACTORY_LOCATIONS: FactoryLocation[] = [
  '天津', '天津三期', '盘锦一期', '盘锦二期', '昆山', '太原', '安阳', '桐乡', '青岛', '大同'
];

export const DEFAULT_SETTINGS: AppSettings = {
  aiApiUrl: 'https://api.openai.com/v1',
  aiApiKey: '',
  aiModel: 'gpt-4-turbo',
  aiTemperature: 0.7,
  activeKBs: ['MES', 'SIMS', 'Case Library']
};