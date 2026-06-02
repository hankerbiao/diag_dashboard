import type { TestLogItem } from '../api/fastapi';

const FAIL_HINTS = ['失败', 'fail', 'failed', 'ng', 'error', '不通过', '未通过', '不合格', '异常', '超时', 'abort'];
const PASS_HINTS = ['成功', 'pass', 'passed', 'ok'];

/** 与后端 is_test_passed 对齐 */
export function isTestPassed(status: string): boolean {
  const lower = (status ?? '').trim().toLowerCase();
  if (!lower) return false;
  if (FAIL_HINTS.some((k) => lower.includes(k))) return false;
  return PASS_HINTS.some((k) => lower.includes(k)) || lower.includes('通过');
}

/** 与后端 is_test_failed 对齐 */
export function isTestFailed(status: string): boolean {
  const s = (status ?? '').trim();
  if (!s) return false;
  if (isTestPassed(s)) return false;
  const lower = s.toLowerCase();
  return FAIL_HINTS.some((k) => lower.includes(k));
}

/** 单条 SIMS 测试记录是否失败（含故障类型） */
export function isSimsLogFailed(log: Pick<TestLogItem, 'fail_details' | 'fault_type1' | 'fault_type2' | 'fault_type3' | 'decision'>): boolean {
  const status = (log.fail_details || log.decision || '').trim();
  if (isTestFailed(status)) return true;
  if (isTestPassed(status)) return false;
  const hasFault = [log.fault_type1, log.fault_type2, log.fault_type3].some((ft) => ft?.trim());
  return hasFault;
}

export function collectFailedTestLogs(result: {
  failed_test_logs?: TestLogItem[];
  test_logs?: TestLogItem[];
}): TestLogItem[] {
  const fromApi = result.failed_test_logs ?? [];
  if (fromApi.length > 0) return fromApi;
  return (result.test_logs ?? []).filter(isSimsLogFailed);
}
