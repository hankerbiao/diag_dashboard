import { useMemo, useState } from 'react';
import { Bot, CheckCircle2, RefreshCw, ArrowUpDown, XCircle, Info, Download } from 'lucide-react';
import type { ErrorLogRow } from '../../types';
import type { DiagnosisCache } from '../../api/fastapi';
import ResultBadge, { isFailureStatus } from '../common/ResultBadge';

interface ErrorTableProps {
  data: ErrorLogRow[];
  loading: boolean;
  analyzingId: string | null;
  analysisResult: Record<string, DiagnosisCache>;
  onAnalyze: (id: string) => void;
  logBaseUrl?: string;
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

export default function ErrorTable({ data, loading, analyzingId, analysisResult, onAnalyze, logBaseUrl = '' }: ErrorTableProps) {
  const [sortField, setSortField] = useState<SortField>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

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
      <div className="flex-1 flex flex-col items-center justify-center gap-3" style={{ color: 'var(--color-text-secondary)' }}>
        <Info className="w-8 h-8 opacity-40" />
        <span className="text-sm">暂无测试详情数据</span>
      </div>
    );
  }

  return (
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
                {row.logPath && row.logPath !== '-' && logBaseUrl ? (
                  <button
                    onClick={() => {
                      const logPath = row.logPath.replace(/^\//, '');
                      window.open(`${logBaseUrl}/${logPath}`, '_blank', 'noopener,noreferrer');
                    }}
                    className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded border transition-colors hover:opacity-80"
                    style={{
                      backgroundColor: 'var(--color-bg-primary)',
                      borderColor: 'var(--color-border)',
                      color: 'var(--color-text-primary)',
                    }}
                  >
                    <Download className="w-3 h-3" />
                    下载日志
                  </button>
                ) : (
                  <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>-</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
