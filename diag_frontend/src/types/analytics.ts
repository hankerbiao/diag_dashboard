/**
 * 数据分析模块类型定义
 */

// API 响应类型（snake_case）
export interface FaultCategoryItemApi {
  name: string;
  count: number;
}

export interface YieldTrendItemApi {
  date: string;
  total: number;
  passed: number;
  failed: number;
  yield: number;
}

export interface StationFailureItemApi {
  station: string;
  count: number;
}

export interface DecisionDistributionItemApi {
  decision: string;
  count: number;
}

export interface ModelDefectItemApi {
  model: string;
  total: number;
  failed: number;
  yield: number;
}

export interface DashboardInsightsApi {
  fault_categories: FaultCategoryItemApi[];
  fault_subcategories: FaultCategoryItemApi[];
  yield_trend: YieldTrendItemApi[];
  station_failures: StationFailureItemApi[];
  decision_distribution: DecisionDistributionItemApi[];
  model_defects: ModelDefectItemApi[];
}

// 内部使用类型（camelCase）
export interface FaultCategoryItem {
  name: string;
  count: number;
}

export interface YieldTrendItem {
  date: string;
  total: number;
  passed: number;
  failed: number;
  yield: number;
}

export interface StationFailureItem {
  station: string;
  count: number;
}

export interface DecisionDistributionItem {
  decision: string;
  count: number;
}

export interface ModelDefectItem {
  model: string;
  total: number;
  failed: number;
  yield: number;
}

export interface DashboardInsights {
  faultCategories: FaultCategoryItem[];
  faultSubcategories: FaultCategoryItem[];
  yieldTrend: YieldTrendItem[];
  stationFailures: StationFailureItem[];
  decisionDistribution: DecisionDistributionItem[];
  modelDefects: ModelDefectItem[];
}

// API 到内部的转换函数
export function toDashboardInsights(api: DashboardInsightsApi): DashboardInsights {
  return {
    faultCategories: api.fault_categories,
    faultSubcategories: api.fault_subcategories,
    yieldTrend: api.yield_trend,
    stationFailures: api.station_failures,
    decisionDistribution: api.decision_distribution,
    modelDefects: api.model_defects,
  };
}