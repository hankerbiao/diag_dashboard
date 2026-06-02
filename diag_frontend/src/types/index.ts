export type NavigationTab = 'diagnosis' | 'error_logs' | 'knowledge_base' | 'settings';

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
