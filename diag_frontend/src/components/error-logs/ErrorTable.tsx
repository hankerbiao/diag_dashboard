import { Bot, CheckCircle2, RefreshCw, AlertTriangle, XCircle, Info } from 'lucide-react';
import type { ErrorLogRow } from '../../types';

interface ErrorTableProps {
  data: ErrorLogRow[];
  loading: boolean;
  analyzingId: string | null;
  analysisResult: Record<string, string>;
  onAnalyze: (id: string) => void;
}

function ResultBadge({ status }: { status: string }) {
  const lower = (status || '').toLowerCase();
  const isSuccess = ['成功', 'pass', 'passed', 'ok'].some(k => lower.includes(k));
  const isFail = ['失败', 'fail', 'failed', 'ng', 'error'].some(k => lower.includes(k));

  const config = isFail
    ? { icon: <XCircle className="w-3 h-3" />, color: '#dc2626', bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.2)' }
    : isSuccess
      ? { icon: <CheckCircle2 className="w-3 h-3" />, color: '#16a34a', bg: 'rgba(22,163,74,0.1)', border: 'rgba(22,163,74,0.2)' }
      : { icon: null, color: '#64748b', bg: 'rgba(100,116,139,0.1)', border: 'rgba(100,116,139,0.2)' };

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold border"
      style={{ backgroundColor: config.bg, color: config.color, borderColor: config.border }}
    >
      {config.icon}
      {status || '-'}
    </span>
  );
}

function FaultTags({ types }: { types: string }) {
  if (!types) return <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>-</span>;
  const items = types.split(',').filter(Boolean);
  if (items.length === 0) return <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>-</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((t, i) => (
        <span
          key={i}
          className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-mono font-medium border"
          style={{
            backgroundColor: 'rgba(234,179,8,0.08)',
            color: '#b45309',
            borderColor: 'rgba(234,179,8,0.2)',
          }}
        >
          {t.trim()}
        </span>
      ))}
    </div>
  );
}

export default function ErrorTable({ data, loading, analyzingId, analysisResult, onAnalyze }: ErrorTableProps) {
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
            <th className="px-5 py-3.5 border-b text-center text-xs tracking-wider font-semibold">测试结果</th>
            <th className="px-5 py-3.5 border-b text-center text-xs tracking-wider font-semibold">判定</th>
            <th className="px-5 py-3.5 border-b text-xs tracking-wider font-semibold">故障类型</th>
            <th className="px-5 py-3.5 border-b text-xs tracking-wider font-semibold">日志路径</th>
            <th className="px-5 py-3.5 border-b text-center text-xs tracking-wider font-semibold">大模型诊断</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
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
                {row.decision || '-'}
              </td>
              <td className="px-5 py-3.5">
                <FaultTags types={row.faultTypes} />
              </td>
              <td className="px-5 py-3.5">
                <span
                  className="rounded px-2.5 py-1 text-xs font-mono shadow-sm truncate max-w-[180px] inline-block align-middle cursor-help border"
                  style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
                  title={row.logPath}
                >
                  {row.logPath || '-'}
                </span>
              </td>
              <td className="px-5 py-3.5 text-center">
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
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
