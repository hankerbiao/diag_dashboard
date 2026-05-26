/**
 * 服务器状态映射工具
 */

export interface ServerStateInfo {
  label: string;
  color: string;
  bg: string;
}

/**
 * 将服务器状态码映射为显示信息
 * @param state - 状态码 ('0' | '1' | '2')
 */
export function mapServerState(state: string | null | undefined): ServerStateInfo {
  const s = String(state ?? '').trim();

  if (s === '2') {
    return { label: '测试失败', color: '#dc2626', bg: 'rgba(239,68,68,0.1)' };
  }
  if (s === '1') {
    return { label: '测试成功', color: '#16a34a', bg: 'rgba(22,163,74,0.1)' };
  }
  if (s === '0') {
    return { label: '正在测试', color: '#d97706', bg: 'rgba(245,158,11,0.1)' };
  }

  return { label: s || '-', color: '#64748b', bg: 'rgba(100,116,139,0.1)' };
}