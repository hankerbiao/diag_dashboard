import { useMemo, useState } from 'react';
import { Bot, CheckCircle2, RefreshCw, ArrowUpDown, Info, Download, Loader2, X } from 'lucide-react';
import type { ErrorLogRow } from '../../types';
import { diagnosisApi, type DiagnosisCache } from '../../api/fastapi';
import ResultBadge, { isFailureStatus } from '../common/ResultBadge';
import SupportHint from '../common/SupportHint';

interface ErrorTableProps {
  data: ErrorLogRow[];
  loading: boolean;
  emptyHint?: string;
  analyzingId: string | null;
  analysisResult: Record<string, DiagnosisCache>;
  onAnalyze: (id: string) => void;
  /** 厂区 ID，走后端 /api/diagnosis/sn/log-content */
  factory?: string;
  /** 与厂区配置一致，用于判断是否具备日志下载能力 */
  logBaseUrl?: string;
  /** 测试详情所属服务器 SN（行内 sn 为空时回退） */
  serverSn?: string;
}

function hasMesLogPath(logPath?: string): boolean {
  const p = (logPath ?? '').trim();
  return p.length > 0 && p !== '-';
}

interface LogViewerState {
  title: string;
  logPath: string;
  content: string;
  error: string;
}

type SortField = 'status' | 'decision' | null;

const DECISION_MAP: Record<string, string> = {
  retry: '重试',
  continue: '继续',
};

function translateDecision(decision: string): string {
  const lower = (decision || '').toLowerCase().trim();
  return DECISION_MAP[lower] || decision || '-';
}

export default function ErrorTable({
  data,
  loading,
  emptyHint,
  analyzingId,
  analysisResult,
  onAnalyze,
  factory = '',
  logBaseUrl = '',
  serverSn = '',
}: ErrorTableProps) {
  const [sortField, setSortField] = useState<SortField>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [logViewer, setLogViewer] = useState<LogViewerState | null>(null);

  const canUseLogApi = Boolean(factory || logBaseUrl);

  const canDownloadLog = (row: ErrorLogRow) => {
    const sn = (row.sn || serverSn || '').trim();
    return Boolean(canUseLogApi && sn && hasMesLogPath(row.logPath));
  };

  const handleDownloadLog = async (row: ErrorLogRow) => {
    if (!canDownloadLog(row)) return;
    const sn = (row.sn || serverSn || '').trim();
    if (!factory) return;
    setDownloadingId(row.id);
    try {
      const res = await diagnosisApi.getLogContent(sn, factory, row.logPath.trim());
      if (res.success && res.data?.content) {
        setLogViewer({
          title: `${row.testItem || '测试日志'} · ${row.sn}`,
          logPath: row.logPath,
          content: res.data.content,
          error: '',
        });
      } else {
        setLogViewer({
          title: `${row.testItem || '测试日志'} · ${row.sn}`,
          logPath: row.logPath,
          content: '',
          error: res.error || '日志下载失败',
        });
      }
    } catch {
      setLogViewer({
        title: `${row.testItem || '测试日志'} · ${row.sn}`,
        logPath: row.logPath,
        content: '',
        error: '网络请求失败',
      });
    } finally {
      setDownloadingId(null);
    }
  };

  const toggleSort = (field: 'status' | 'decision') => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const sortedData = useMemo(() => {
    if (!sortField) return data;
    return [...data].sort((a, b) => {
      const aVal = (a[sortField] || '').toLowerCase();
      const bVal = (b[sortField] || '').toLowerCase();
      return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });
  }, [data, sortField, sortDir]);

  const sortIcon = (field: SortField) => (
    <ArrowUpDown className={`w-3 h-3 ml-1 inline-block transition-opacity ${sortField === field ? 'opacity-100' : 'opacity-30'}`} />
  );

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3" style={{ color: 'var(--color-text-secondary)' }}>
        <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-accent)', borderTopColor: 'transparent' }} />
        <span className="text-sm">加载测试详情...</span>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6 text-center" style={{ color: 'var(--color-text-secondary)' }}>
        <Info className="w-8 h-8 opacity-40" />
        <span className="text-sm">{emptyHint || '暂无测试详情数据'}</span>
        <SupportHint compact className="justify-center max-w-sm" />
      </div>
    );
  }

  return (
    <>
    <div className="flex-1 overflow-auto custom-scrollbar">
      <table className="w-full text-left border-collapse text-[13px] whitespace-nowrap min-w-max">
        <thead
          className="sticky top-0 z-10 border-b"
          style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
        >
          <tr>
            <th className="px-5 py-3.5 border-b w-16 text-center text-xs tracking-wider font-semibold">序号</th>
            <th className="px-5 py-3.5 border-b text-xs tracking-wider font-semibold">服务器 SN</th>
            <th className="px-5 py-3.5 border-b text-xs tracking-wider font-semibold">测试项</th>
            <th className="px-5 py-3.5 border-b text-xs tracking-wider font-semibold">测试时间</th>
            <th
              className="px-5 py-3.5 border-b text-center text-xs tracking-wider font-semibold cursor-pointer select-none hover:opacity-80"
              onClick={() => toggleSort('status')}
            >
              测试结果{sortIcon('status')}
            </th>
            <th
              className="px-5 py-3.5 border-b text-center text-xs tracking-wider font-semibold cursor-pointer select-none hover:opacity-80"
              onClick={() => toggleSort('decision')}
            >
              判定{sortIcon('decision')}
            </th>
            <th className="px-5 py-3.5 border-b text-xs tracking-wider font-semibold">AI 异常摘要</th>
            <th className="px-5 py-3.5 border-b text-center text-xs tracking-wider font-semibold">大模型诊断</th>
            <th className="px-5 py-3.5 border-b text-center text-xs tracking-wider font-semibold">操作</th>
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row, idx) => (
            <tr
              key={row.id}
              className="transition-colors border-b group"
              style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
            >
              <td className="px-5 py-3.5 text-center font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                {idx + 1}
              </td>
              <td className="px-5 py-3.5 font-mono text-[12px] font-semibold" style={{ color: 'var(--color-accent)' }}>
                {row.sn}
              </td>
              <td className="px-5 py-3.5 max-w-[200px] truncate font-medium" style={{ color: 'var(--color-text-primary)' }} title={row.testItem}>
                {row.testItem || '-'}
              </td>
              <td className="px-5 py-3.5 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
                {row.testTime ? new Date(row.testTime).toLocaleString('zh-CN') : '-'}
              </td>
              <td className="px-5 py-3.5 text-center">
                <ResultBadge status={row.status} />
              </td>
              <td className="px-5 py-3.5 text-center text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>
                {translateDecision(row.decision)}
              </td>
              <td className="px-5 py-3.5 max-w-[260px]">
                <span
                  className="text-xs leading-relaxed line-clamp-2 block"
                  style={{ color: 'var(--color-text-secondary)' }}
                  title={
                    analysisResult[row.id]
                      ? (analysisResult[row.id].root_cause || analysisResult[row.id].analysis || '')
                      : undefined
                  }
                >
                  {analysisResult[row.id]
                    ? (analysisResult[row.id].root_cause || analysisResult[row.id].analysis || '')
                    : row.faultTypes
                      ? `检测到异常类型 [${row.faultTypes}]，建议点击智能剖析获取根因分析。`
                      : '暂未检测到异常模式'}
                </span>
              </td>
              <td className="px-5 py-3.5 text-center">
                {isFailureStatus(row.status) || analysisResult[row.id] ? (
                  <button
                    onClick={() => onAnalyze(row.id)}
                    className="inline-flex items-center justify-center gap-1.5 transition-all text-xs font-bold px-3 py-1.5 rounded shadow-sm w-[110px] mx-auto border"
                    style={
                      analysisResult[row.id]
                        ? { backgroundColor: 'rgba(16,185,129,0.1)', color: '#059669', borderColor: 'rgba(16,185,129,0.2)' }
                        : { backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)', borderColor: 'var(--color-accent-light)' }
                    }
                  >
                    {analyzingId === row.id ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : analysisResult[row.id] ? (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    ) : (
                      <Bot className="w-3.5 h-3.5" />
                    )}
                    {analyzingId === row.id ? '分析生成中' : analysisResult[row.id] ? '查看分析' : '智能剖析'}
                  </button>
                ) : (
                  <span
                    className="inline-flex items-center justify-center gap-1.5 text-xs px-3 py-1.5 rounded w-[110px] mx-auto border"
                    style={{
                      backgroundColor: 'rgba(100,116,139,0.05)',
                      color: 'var(--color-text-muted)',
                      borderColor: 'rgba(100,116,139,0.1)',
                      cursor: 'not-allowed',
                      opacity: 0.5,
                    }}
                  >
                    <Bot className="w-3.5 h-3.5" />
                    智能剖析
                  </span>
                )}
              </td>
              <td className="px-5 py-3.5 text-center">
                {!canUseLogApi ? (
                  <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>-</span>
                ) : canDownloadLog(row) ? (
                  <button
                    type="button"
                    onClick={() => handleDownloadLog(row)}
                    disabled={downloadingId === row.id}
                    className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded border transition-colors hover:opacity-80 disabled:opacity-50"
                    style={{
                      backgroundColor: 'var(--color-bg-primary)',
                      borderColor: 'var(--color-border)',
                      color: 'var(--color-text-primary)',
                    }}
                  >
                    {downloadingId === row.id ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Download className="w-3 h-3" />
                    )}
                    {downloadingId === row.id ? '下载中' : '下载日志'}
                  </button>
                ) : (
                  <span
                    className="text-xs"
                    style={{ color: 'var(--color-text-muted)' }}
                    title="SIMS 未返回 log 字段"
                  >
                    无日志
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>

    {logViewer && (
      <div
        className="fixed inset-0 z-[60] flex items-center justify-center p-4"
        style={{ backgroundColor: 'rgba(15, 23, 42, 0.55)' }}
        onClick={() => setLogViewer(null)}
      >
        <div
          className="flex flex-col w-full max-w-3xl max-h-[80vh] rounded-xl border shadow-xl"
          style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-start justify-between gap-3 px-4 py-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold truncate" style={{ color: 'var(--color-text-primary)' }}>
                {logViewer.title}
              </h3>
              <p className="text-[11px] font-mono truncate mt-0.5" style={{ color: 'var(--color-text-muted)' }} title={logViewer.logPath}>
                {logViewer.logPath}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setLogViewer(null)}
              className="p-1 rounded-md hover:opacity-80 shrink-0"
              style={{ color: 'var(--color-text-secondary)' }}
              aria-label="关闭"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 min-h-0 overflow-auto custom-scrollbar p-4">
            {logViewer.error ? (
              <div className="space-y-3">
                <p className="text-sm" style={{ color: '#dc2626' }}>{logViewer.error}</p>
                <SupportHint compact />
              </div>
            ) : (
              <pre
                className="text-[11px] leading-relaxed whitespace-pre-wrap break-all font-mono rounded-lg p-3 border"
                style={{ backgroundColor: '#1a1b26', borderColor: '#334155', color: '#94a3b8' }}
              >
                {logViewer.content}
              </pre>
            )}
          </div>
        </div>
      </div>
    )}
    </>
  );
}
