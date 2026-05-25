import type { ErrorLogRow } from '../types';

export const trendDataDaily = [
  { time: '05-16', issues: 12 },
  { time: '05-17', issues: 19 },
  { time: '05-18', issues: 15 },
  { time: '05-19', issues: 22 },
  { time: '05-20', issues: 8 },
  { time: '05-21', issues: 14 },
  { time: '05-22', issues: 28 },
];

export const trendDataWeekly = [
  { time: 'W1', issues: 120 },
  { time: 'W2', issues: 95 },
  { time: 'W3', issues: 140 },
  { time: 'W4', issues: 110 },
];

export const trendDataMonthly = [
  { time: 'Feb', issues: 450 },
  { time: 'Mar', issues: 400 },
  { time: 'Apr', issues: 520 },
  { time: 'May', issues: 380 },
];

export const issueTypeData = [
  { name: '阻抗异常', count: 45 },
  { name: '内存自检', count: 32 },
  { name: '固件缺失', count: 28 },
  { name: '通讯超时', count: 18 },
  { name: '总线电压', count: 12 },
];

export const modelStatsData = [
  { model: '2U Rack Server', total: 420, failed: 24, yield: 94.2 },
  { model: 'FortFirm-H1075', total: 650, failed: 18, yield: 97.2 },
  { model: '6610 X2', total: 320, failed: 35, yield: 89.0 },
  { model: '6U GPU Server', total: 180, failed: 12, yield: 93.3 },
  { model: 'R620 G50', total: 290, failed: 8, yield: 97.2 },
  { model: '3215 C3', total: 410, failed: 22, yield: 94.6 },
];

export const defectDistributionData = [
  { name: '内存检测不通过', value: 35 },
  { name: '主板阻抗异常', value: 28 },
  { name: '网络通讯超时', value: 22 },
  { name: '固件版本不匹配', value: 15 },
  { name: '传感器未响应', value: 10 },
];

export const yieldTrendData = [
  { date: '05-16', yield: 92.5 },
  { date: '05-17', yield: 93.1 },
  { date: '05-18', yield: 91.8 },
  { date: '05-19', yield: 95.4 },
  { date: '05-20', yield: 96.2 },
  { date: '05-21', yield: 94.8 },
  { date: '05-22', yield: 96.5 },
];

export const lineIssuesData = [
  { line: 'L1线体', issues: 12 },
  { line: 'L2线体', issues: 19 },
  { line: 'L3线体', issues: 8 },
  { line: 'L4线体', issues: 24 },
  { line: 'L5线体', issues: 15 },
];

export const COLORS = ['#ef4444', '#f97316', '#f59e0b', '#3b82f6', '#8b5cf6'];

export const errorLogTableData: ErrorLogRow[] = [
  {
    id: '1',
    sn: '6102263004319419',
    testItem: 'Stress Check',
    testTime: '2026-05-14 21:27:48',
    status: '失败',
    decision: '跳过',
    faultTypes: '阻抗异常, 内存自检',
    logPath: '/var/log/diag/stress_0x822.log',
    mesRecord: 'MES-20260514-001',
  },
  {
    id: '2',
    sn: '6102263012999411',
    testItem: 'BIOS Flash',
    testTime: '2026-05-14 21:30:12',
    status: '失败',
    decision: '-',
    faultTypes: '固件缺失',
    logPath: '/var/log/diag/bios_ver.log',
    mesRecord: '',
  },
];

export const DEFAULT_SN = 'CN-0M3821-72911-39A-0021';

export const DEFAULT_ANALYSIS_RESULT = '基于知识图谱深度分析与大模型聚类反馈：该测试节点的离群异常与已知高频缺陷簇表现出关键特征维度的吻合。系统推荐最优处置策略为主板阻抗微调或执行诊断框架 `diag --verify` 命令进行边界校验验证。';