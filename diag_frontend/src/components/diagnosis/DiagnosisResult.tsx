import { useState } from 'react';
import { Bot, Activity, AlertTriangle, Wrench, Terminal, ChevronDown, ChevronRight, Loader2, Cpu, Shield, History, BookOpen, Download } from 'lucide-react';
import type { DiagnosisResult as DiagnosisResultType, TestLogItem, FailedLogFile } from '../../api/fastapi';
import { diagnosisApi } from '../../api/fastapi';
import ResultBadge from '../common/ResultBadge';
import FeedbackPanel from '../common/FeedbackPanel';
import { collectFailedTestLogs, isSimsLogFailed } from '../../utils/testStatus';

interface DiagnosisResultProps {
  result: DiagnosisResultType;
  factory: string;
  historyId?: string;
}

const CATEGORY_COLORS: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  'hardware': {
    bg: 'linear-gradient(135deg, rgba(254, 243, 199, 0.8), rgba(254, 226, 154, 0.3))',
    border: 'rgba(251, 191, 36, 0.3)',
    text: '#92400e',
    badge: '#f59e0b',
  },
};

function getCategoryStyle(category: string) {
  const cat = category.toLowerCase();
  if (cat.includes('hardware') || cat.includes('硬件')) return CATEGORY_COLORS.hardware;
  return CATEGORY_COLORS.hardware;
}

/** 构建诊断上下文摘要，用于反馈记录 */
function buildDiagnosisContext(result: DiagnosisResultType): string {
  const parts: string[] = [];
  if (result.category) parts.push(`故障类别: ${result.category}`);
  if (result.confidence) parts.push(`置信度: ${Math.round(result.confidence * 100)}%`);
  if (result.summary) parts.push(`诊断摘要: ${result.summary}`);
  if (result.root_cause_detail) parts.push(`根因分析: ${result.root_cause_detail}`);
  if (result.suggestions?.length) parts.push(`建议: ${result.suggestions.join('; ')}`);
  return parts.join('\n');
}

function RawLogRow({ log, factory, sn }: { log: TestLogItem; factory: string; sn: string; key?: string }) {
  const [expanded, setExpanded] = useState(false);
  const [logContent, setLogContent] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLoadLog = async () => {
    if (!log.log_path) return;
    setLoading(true);
    try {
      const res = await diagnosisApi.getLogContent(sn, factory, log.log_path);
      setLogContent(res.success && res.data ? res.data.content : '下载失败');
    } catch {
      setLogContent('网络请求失败');
    } finally {
      setLoading(false);
      setExpanded(true);
    }
  };

  return (
    <div className="border-b last:border-b-0" style={{ borderColor: 'var(--color-border)' }}>
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:opacity-80 transition-opacity"
        onClick={() => !expanded && setExpanded(!expanded)}
        style={{ backgroundColor: expanded ? 'var(--color-bg-secondary)' : 'transparent' }}
      >
        <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
          className="p-0.5 rounded" style={{ color: 'var(--color-text-secondary)' }}>
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
        <span className="text-[12px] font-mono" style={{ color: 'var(--color-text-muted)' }}>{log.test_time}</span>
        <span className="text-[12px] font-medium truncate flex-1" style={{ color: 'var(--color-text-primary)' }}>{log.test_item}</span>
        <ResultBadge status={log.fail_details || '-'} />
      </div>
      {expanded && (
        <div className="px-5 py-3 space-y-2 text-[12px] font-mono" style={{ color: 'var(--color-text-secondary)' }}>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1">
            {log.big_flow && <><span className="opacity-60">大流程</span><span>{log.big_flow}</span></>}
            {log.test_item && <><span className="opacity-60">测试项</span><span>{log.test_item}</span></>}
            {log.fail_details && <><span className="opacity-60">测试结果</span><span className="text-red-400">{log.fail_details}</span></>}
            {log.decision && <><span className="opacity-60">判定</span><span>{log.decision}</span></>}
          </div>
          {(log.fault_type1 || log.fault_type2 || log.fault_type3) && (
            <div className="flex gap-2 pt-1">
              {[log.fault_type1, log.fault_type2, log.fault_type3].filter(Boolean).map((ft, i) => (
                <span key={i} className="text-[11px] px-2 py-0.5 rounded-full border"
                  style={{ borderColor: 'rgba(239,68,68,0.25)', color: '#dc2626', backgroundColor: 'rgba(239,68,68,0.06)' }}>
                  {ft}
                </span>
              ))}
            </div>
          )}
          {log.log_path && (
            <div className="pt-1">
              <button
                onClick={(e) => { e.stopPropagation(); handleLoadLog(); }}
                disabled={loading}
                className="text-[11px] px-2.5 py-1 rounded-lg border font-bold transition-colors flex items-center gap-1.5"
                style={{ borderColor: 'var(--color-border)', color: 'var(--color-accent)', backgroundColor: 'var(--color-bg-primary)' }}
              >
                {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Terminal className="w-3 h-3" />}
                {loading ? '下载中...' : '下载完整日志'}
              </button>
              {logContent && (
                <pre className="mt-2 rounded-lg p-3 border max-h-64 overflow-y-auto custom-scrollbar text-[11px] leading-relaxed whitespace-pre-wrap break-all"
                  style={{ backgroundColor: '#1a1b26', borderColor: '#334155', color: '#94a3b8' }}>
                  {logContent}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


/** 被 AI 分析的日志文件下载行 */
function LogFileDownloadRow({ logFile }: { logFile: FailedLogFile }) {
  const filename = `${logFile.test_time.replace(/[/\\:]/g, '-')}_${logFile.test_item.replace(/[/\\:]/g, '_')}.log`;
  return (
    <div className="flex items-center justify-between px-4 py-3 text-[12px]">
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>{logFile.test_item}</div>
        <div className="mt-0.5 flex items-center gap-3" style={{ color: 'var(--color-text-muted)' }}>
          <span className="font-mono">{logFile.test_time}</span>
          <span>{logFile.matched_lines} 个错误行 / {logFile.total_lines} 行</span>
        </div>
      </div>
      <button
        onClick={() => downloadTextAsFile(logFile.extracted_content, filename)}
        className="shrink-0 text-[11px] px-3 py-1.5 rounded-lg border font-bold transition-colors flex items-center gap-1.5 hover:opacity-80"
        style={{ borderColor: 'var(--color-border)', color: 'var(--color-accent)', backgroundColor: 'var(--color-bg-secondary)' }}
      >
        <Download className="w-3.5 h-3.5" />
        下载
      </button>
    </div>
  );
}


/** 将文本内容作为文件下载 */
function downloadTextAsFile(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}


export default function DiagnosisResult({ result, factory, historyId }: DiagnosisResultProps) {
  const catStyle = getCategoryStyle(result.category);
  const failedLogs = collectFailedTestLogs(result);
  const recentLogs = result.test_logs ?? [];
  const diagnosisContext = buildDiagnosisContext(result);

  return (
    <div
      className="flex-1 border-r flex flex-col min-h-0 relative"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div className="p-8 flex-1 overflow-y-auto w-full mx-auto flex flex-col gap-8 custom-scrollbar">
        <div className="flex items-start gap-4">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0"
            style={{
              background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
              boxShadow: '0 4px 12px -2px rgba(59, 130, 246, 0.4)',
            }}
          >
            <Bot className="w-5 h-5" />
          </div>
          <div className="flex-1 space-y-5 mt-1">
            <div
              className="p-5 rounded-2xl text-sm leading-relaxed shadow-sm border"
              style={{
                backgroundColor: 'var(--color-bg-primary)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            >
              海光DCU算力平台针对序列号{' '}
              <strong
                className="font-mono px-1 py-0.5 rounded shadow-sm"
                style={{
                  backgroundColor: 'var(--color-accent-light)',
                  color: 'var(--color-accent)',
                }}
              >
                {result.sn}
              </strong>{' '}
              的图谱推理分析已完成。系统已交叉比对 SIMS 测试日志与历史维修记录，并调用了相应的故障知识经验库。
              {failedLogs.length > 0 && (
                <span className="block mt-2 font-medium" style={{ color: '#dc2626' }}>
                  共识别 {failedLogs.length} 条失败测试项，可在下方查看日志详情。
                </span>
              )}
            </div>

            {result.summary && (
              <div className="space-y-3">
                <h3
                  className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <Activity className="w-4 h-4 text-amber-500" /> 智能诊断结果
                </h3>
                <div
                  className="p-5 border rounded-2xl shadow-sm relative overflow-hidden"
                  style={{
                    background: catStyle.bg,
                    borderColor: catStyle.border,
                    color: catStyle.text,
                  }}
                >
                  <div
                    className="absolute top-0 right-0 px-3 py-1 text-white rounded-bl-xl text-[10px] font-bold shadow-sm"
                    style={{ backgroundColor: catStyle.badge }}
                  >
                    置信度: {Math.round(result.confidence * 100)}%
                  </div>
                  <div className="flex items-center gap-2 font-bold mb-3 text-[15px]">
                    <AlertTriangle className="w-5 h-5 text-amber-500" />{' '}
                    {result.category}
                  </div>
                  <p className="text-[13px] leading-relaxed opacity-90">
                    {result.summary}
                  </p>
                </div>
              </div>
            )}

            {result.root_cause_detail && (
              <div className="space-y-3 pt-2">
                <h3
                  className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <Cpu className="w-4 h-4 text-blue-500" /> 根因分析
                </h3>
                <div
                  className="p-4 rounded-xl border shadow-sm text-[13px] leading-relaxed"
                  style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
                >
                  {result.root_cause_detail}
                </div>
              </div>
            )}

            {result.affected_components.length > 0 && (
              <div className="space-y-2 pt-2">
                <h3 className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}>
                  <AlertTriangle className="w-4 h-4 text-red-400" /> 受影响组件
                </h3>
                <div className="flex flex-wrap gap-2">
                  {result.affected_components.map((comp, i) => (
                    <span
                      key={i}
                      className="text-[12px] px-3 py-1 rounded-full border font-mono font-medium"
                      style={{ borderColor: 'rgba(239,68,68,0.25)', color: '#dc2626', backgroundColor: 'rgba(239,68,68,0.06)' }}
                    >
                      {comp}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {result.suggestions.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3
                  className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <Wrench className="w-4 h-4 text-emerald-500" /> 维修建议
                </h3>
                <ul className="space-y-3">
                  {result.suggestions.map((suggestion, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-4 text-[13px] p-4 rounded-xl border shadow-sm transition-colors"
                      style={{
                        backgroundColor: 'var(--color-bg-secondary)',
                        borderColor: 'var(--color-border)',
                        color: 'var(--color-text-secondary)',
                      }}
                    >
                      <span
                        className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 shadow-sm"
                        style={{
                          backgroundColor: 'rgba(16, 185, 129, 0.1)',
                          color: '#059669',
                        }}
                      >
                        {i + 1}
                      </span>
                      <div className="flex-1">
                        <span className="block font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          {suggestion}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.preventive_measures.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3
                  className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <Shield className="w-4 h-4 text-indigo-400" /> 预防措施
                </h3>
                <ul className="space-y-2">
                  {result.preventive_measures.map((measure, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-3 text-[13px] p-3 rounded-xl border"
                      style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
                    >
                      <span
                        className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5"
                        style={{ backgroundColor: 'rgba(99,102,241,0.1)', color: '#6366f1' }}
                      >
                        {i + 1}
                      </span>
                      <span>{measure}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.maintenance_history.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3
                  className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <History className="w-4 h-4 text-slate-400" /> 历史维修记录
                </h3>
                <ul className="space-y-2">
                  {result.maintenance_history.map((item) => (
                    <li
                      key={item.id || `${item.date}-${item.component}`}
                      className="text-[13px] p-3 rounded-xl border"
                      style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
                    >
                      <span className="font-mono text-[11px]" style={{ color: 'var(--color-text-muted)' }}>{item.date}</span>
                      <span className="mx-2">·</span>
                      <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{item.component}</span>
                      <span className="mx-2">—</span>
                      <span>{item.action}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.similar_cases.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3
                  className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <BookOpen className="w-4 h-4 text-violet-400" /> 相似历史案例
                </h3>
                <ul className="space-y-2">
                  {result.similar_cases.map((item) => (
                    <li
                      key={item.id || item.title}
                      className="text-[13px] p-3 rounded-xl border"
                      style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
                    >
                      <div className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{item.title || item.root_cause}</div>
                      {item.root_cause && item.title && (
                        <div className="mt-1 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>{item.root_cause}</div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {failedLogs.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3
                  className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <Terminal className="w-4 h-4 text-red-400" /> 失败项日志详情（可下载原文）
                </h3>
                <div
                  className="rounded-xl border overflow-hidden shadow-sm"
                  style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}
                >
                  {failedLogs.map((log) => (
                    <RawLogRow key={log.id} log={log} factory={factory} sn={result.sn} />
                  ))}
                </div>
              </div>
            )}

            {/* 被 AI 分析的日志文件下载 */}
            {result.failed_log_files && result.failed_log_files.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3
                  className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <Download className="w-4 h-4 text-blue-400" /> 被 AI 分析的日志文件
                </h3>
                <div
                  className="rounded-xl border overflow-hidden shadow-sm divide-y"
                  style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}
                >
                  {result.merged_error_log && (
                    <div className="flex items-center justify-between px-4 py-3 text-[12px]">
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                          聚合错误日志
                        </div>
                        <div className="mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                          已整合 {result.failed_log_files.length} 份日志，内容与本次诊断输入一致
                        </div>
                      </div>
                      <button
                        onClick={() => downloadTextAsFile(result.merged_error_log!, `${result.sn}_aggregated_errors.txt`)}
                        className="shrink-0 text-[11px] px-3 py-1.5 rounded-lg border font-bold transition-colors flex items-center gap-1.5 hover:opacity-80"
                        style={{ borderColor: 'var(--color-border)', color: '#059669', backgroundColor: 'rgba(16,185,129,0.08)' }}
                      >
                        <Download className="w-3.5 h-3.5" />
                        下载聚合结果
                      </button>
                    </div>
                  )}
                  {result.failed_log_files.map((lf, idx) => (
                    <LogFileDownloadRow key={lf.log_path || idx} logFile={lf} />
                  ))}
                </div>
              </div>
            )}

            {recentLogs.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3
                  className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <Terminal className="w-4 h-4 text-slate-400" /> SIMS 最近测试记录（{recentLogs.length}）
                </h3>
                <div
                  className="rounded-xl border overflow-hidden shadow-sm"
                  style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}
                >
                  {recentLogs.map((log) => (
                    <div
                      key={`recent-${log.id}`}
                      className="flex items-center gap-3 px-4 py-2.5 border-b last:border-b-0 text-[12px]"
                      style={{
                        borderColor: 'var(--color-border)',
                        backgroundColor: isSimsLogFailed(log) ? 'rgba(239,68,68,0.04)' : 'transparent',
                      }}
                    >
                      <span className="font-mono shrink-0" style={{ color: 'var(--color-text-muted)' }}>
                        {log.test_time}
                      </span>
                      <span className="font-medium flex-1 truncate" style={{ color: 'var(--color-text-primary)' }}>
                        {log.test_item}
                      </span>
                      <ResultBadge status={log.fail_details || log.decision || '-'} />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="h-4 shrink-0" />
      </div>

      {/* 诊断反馈面板 */}
      <FeedbackPanel
        historyId={historyId}
        sn={result.sn}
        factory={factory}
        diagnosisContext={diagnosisContext}
      />
    </div>
  );
}
