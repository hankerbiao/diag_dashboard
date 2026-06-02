import { useMemo, useState } from 'react';
import { X, Server, Cpu, MapPin, Clock, Hash, Activity, Router, XCircle, Search } from 'lucide-react';
import type { ErrorLogRow } from '../../types';
import type { SyncServer, DiagnosisCache } from '../../api/fastapi';
import ErrorTable from './ErrorTable';

interface ServerDetailModalProps {
  server: SyncServer;
  detailRows: ErrorLogRow[];
  detailsLoading: boolean;
  detailsError?: string;
  analyzingId: string | null;
  analysisResult: Record<string, DiagnosisCache>;
  onAnalyze: (id: string) => void;
  onClose: () => void;
  logBaseUrl?: string;
}

function mapServerState(state: string): { label: string; color: string; bg: string } {
  const s = String(state).trim();
  if (s === '2') return { label: '测试失败', color: '#dc2626', bg: 'rgba(239,68,68,0.1)' };
  if (s === '1') return { label: '测试成功', color: '#16a34a', bg: 'rgba(22,163,74,0.1)' };
  if (s === '0') return { label: '正在测试', color: '#d97706', bg: 'rgba(245,158,11,0.1)' };
  return { label: s || '-', color: '#64748b', bg: 'rgba(100,116,139,0.1)' };
}

export default function ServerDetailModal({
  server,
  detailRows,
  detailsLoading,
  detailsError = '',
  analyzingId,
  analysisResult,
  onAnalyze,
  onClose,
  logBaseUrl = '',
}: ServerDetailModalProps) {
  const stateInfo = mapServerState(server.server_state);
  const [searchKeyword, setSearchKeyword] = useState('');

  const filteredRows = useMemo(() => {
    if (!searchKeyword.trim()) return detailRows;
    const kw = searchKeyword.trim().toLowerCase();
    return detailRows.filter((r) => (r.testItem || '').toLowerCase().includes(kw));
  }, [detailRows, searchKeyword]);

  const failCount = useMemo(() => {
    return filteredRows.filter((r) => {
      const lower = (r.status || '').toLowerCase();
      return ['失败', 'fail', 'failed', 'ng', 'error'].some((k) => lower.includes(k));
    }).length;
  }, [filteredRows]);

  const infoItems = [
    { icon: <Hash className="w-3.5 h-3.5" />, label: 'SN', value: server.server_sn, mono: true },
    { icon: <Server className="w-3.5 h-3.5" />, label: '型号', value: server.model },
    { icon: <Cpu className="w-3.5 h-3.5" />, label: '产品型号', value: server.product_models },
    { icon: <Router className="w-3.5 h-3.5" />, label: 'IP 地址', value: server.host_ip, mono: true },
    { icon: <MapPin className="w-3.5 h-3.5" />, label: '坐标位置', value: server.position, mono: true },
    { icon: <Activity className="w-3.5 h-3.5" />, label: '下一步骤', value: server.next_item },
    { icon: <Clock className="w-3.5 h-3.5" />, label: '同步时间', value: server.synced_at ? new Date(server.synced_at).toLocaleString('zh-CN') : '-' },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-[95vw] h-[92vh] rounded-2xl shadow-2xl border flex flex-col overflow-hidden"
        style={{
          backgroundColor: 'var(--color-bg-primary)',
          borderColor: 'var(--color-border)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b flex-none"
          style={{ borderColor: 'var(--color-border)' }}
        >
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold" style={{ color: 'var(--color-text-primary)' }}>
              {server.server_sn} 测试详情
            </h2>
            <span
              className="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold"
              style={{ backgroundColor: stateInfo.bg, color: stateInfo.color }}
            >
              {stateInfo.label}
            </span>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors hover:opacity-70"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Server Info Bar */}
        <div
          className="px-6 py-3 border-b flex-none flex flex-wrap gap-x-6 gap-y-2"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}
        >
          {infoItems.map((item, i) => (
            <div key={i} className="flex items-center gap-1.5 text-[12px]">
              <span style={{ color: 'var(--color-text-muted)' }}>{item.icon}</span>
              <span style={{ color: 'var(--color-text-secondary)' }}>{item.label}:</span>
              <span
                className={`font-medium ${item.mono ? 'font-mono' : ''}`}
                style={{ color: 'var(--color-text-primary)' }}
              >
                {item.value || '-'}
              </span>
            </div>
          ))}
        </div>

        {/* Detail count + Table */}
        <div className="flex-1 flex flex-col min-h-0">
          <div
            className="h-9 px-6 border-b flex items-center justify-between flex-none gap-4 text-[12px]"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
          >
            <span className="flex items-center gap-3">
              <span>
                共 <span className="font-bold" style={{ color: 'var(--color-accent)' }}>{detailRows.length}</span> 条
              </span>
              {failCount > 0 && (
                <span className="inline-flex items-center gap-1">
                  <XCircle className="w-3 h-3" style={{ color: '#dc2626' }} />
                  <span style={{ color: '#dc2626' }}>
                    失败 <span className="font-bold">{failCount}</span> 条
                  </span>
                </span>
              )}
              {searchKeyword.trim() && (
                <span style={{ color: 'var(--color-text-muted)' }}>
                  筛选 <span className="font-bold" style={{ color: 'var(--color-accent)' }}>{filteredRows.length}</span> 条
                </span>
              )}
            </span>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3" style={{ color: 'var(--color-text-muted)' }} />
              <input
                type="text"
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                placeholder="搜索测试项…"
                className="h-7 pl-7 pr-3 rounded-md text-[12px] outline-none border w-44 transition-colors"
                style={{
                  backgroundColor: 'var(--color-bg-primary)',
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)',
                }}
              />
            </div>
          </div>
          <div className="flex-1 min-h-0 overflow-auto custom-scrollbar">
            <ErrorTable
              data={filteredRows}
              loading={detailsLoading}
              emptyHint={detailsError || undefined}
              analyzingId={analyzingId}
              analysisResult={analysisResult}
              onAnalyze={onAnalyze}
              logBaseUrl={logBaseUrl}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
