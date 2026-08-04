import { useState } from 'react';
import { Bot, Activity, AlertTriangle, Wrench, Terminal, ChevronDown, ChevronRight, Loader2, Cpu, Shield, History, BookOpen, Download, FileDown, Database } from 'lucide-react';
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
  const duration = logFile.extraction_duration_ms >= 1000
    ? `${(logFile.extraction_duration_ms / 1000).toFixed(1)} 秒`
    : `${logFile.extraction_duration_ms} 毫秒`;
  const modeLabel = logFile.ai_extracted
    ? logFile.processing_mode === 'prefiltered_chunked'
      ? '规则清洗 + AI 分块提取'
      : logFile.processing_mode === 'chunked'
        ? 'AI 分块提取'
        : 'AI 整体提取'
    : '编码级回退';
  const originalLines = logFile.preprocessing_original_lines ?? logFile.total_lines;
  const removedLines = logFile.preprocessing_removed_lines ?? 0;
  const removalRate = originalLines > 0 ? removedLines / originalLines : 0;
  return (
    <div className="flex items-center justify-between px-4 py-3 text-[12px]">
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>{logFile.test_item}</div>
        <div className="mt-0.5 flex items-center gap-3" style={{ color: 'var(--color-text-muted)' }}>
          <span className="font-mono">{logFile.test_time}</span>
          <span>{logFile.matched_lines} 个错误行 / {logFile.total_lines} 行</span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          <span style={{ color: logFile.ai_extracted ? '#059669' : '#d97706' }}>{modeLabel}</span>
          {logFile.ai_extracted && <span>模型: {logFile.model_used || 'default'}</span>}
          {logFile.segment_count > 0 && (
            <span>
              分块: {logFile.successful_segments}/{logFile.segment_count} 成功
              {logFile.failed_segments > 0 ? `，${logFile.failed_segments} 块回退` : ''}
            </span>
          )}
          {logFile.preprocessing_applied ? (
            <span>
              清洗对比: 原始 {originalLines} 行 → 保留 {logFile.preprocessing_kept_lines ?? 0} 行，
              过滤 {removedLines} 行（{(removalRate * 100).toFixed(1)}%）
            </span>
          ) : (
            <span>清洗对比: 原始 {originalLines} 行，未触发规则清洗</span>
          )}
          {logFile.source_truncated && (
            <span style={{ color: '#d97706' }}>
              大文件采样: 源文件约 {logFile.source_line_count ?? 0} 行，按头尾保留
              {' '}{Math.round((logFile.downloaded_size ?? 0) / 1024)} KB /
              {' '}{Math.round((logFile.source_size ?? 0) / 1024)} KB
            </span>
          )}
          {(logFile.retry_count ?? 0) > 0 && <span>模型重试: {logFile.retry_count} 次</span>}
          <span>耗时: {duration}</span>
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


/** 提取方式的中文描述 */
function extractionModeLabel(logFile: FailedLogFile): string {
  if (!logFile.ai_extracted) return '编码级回退';
  if (logFile.processing_mode === 'prefiltered_chunked') return '规则清洗 + AI 分块提取';
  if (logFile.processing_mode === 'chunked') return 'AI 分块提取';
  return 'AI 整体提取';
}


/** 构建 AI 深度诊断报告（Markdown），含诊断结论与完整证据链 */
function buildDiagnosisReport(result: DiagnosisResultType, factory: string): string {
  const lines: string[] = [];
  const now = new Date().toLocaleString('zh-CN', { hour12: false });

  lines.push(`# SN ${result.sn} AI 深度诊断报告`);
  lines.push('');
  lines.push(`- **序列号**: ${result.sn}`);
  lines.push(`- **厂区**: ${factory}`);
  lines.push(`- **生成时间**: ${now}`);
  lines.push(`- **故障类别**: ${result.category || '-'}`);
  lines.push(`- **置信度**: ${result.confidence != null ? `${Math.round(result.confidence * 100)}%` : '-'}`);
  lines.push('');

  lines.push('## 一、诊断摘要');
  lines.push(result.summary || '（无）');
  lines.push('');

  if (result.root_cause_detail) {
    lines.push('## 二、根因分析');
    lines.push(result.root_cause_detail);
    lines.push('');
  }

  if (result.affected_components?.length) {
    lines.push('## 三、受影响组件');
    result.affected_components.forEach((comp) => lines.push(`- ${comp}`));
    lines.push('');
  }

  if (result.suggestions?.length) {
    lines.push('## 四、维修建议');
    result.suggestions.forEach((suggestion, index) => lines.push(`${index + 1}. ${suggestion}`));
    lines.push('');
  }

  if (result.preventive_measures?.length) {
    lines.push('## 五、预防措施');
    result.preventive_measures.forEach((measure, index) => lines.push(`${index + 1}. ${measure}`));
    lines.push('');
  }

  // 证据链：AI 实际分析参考的日志与数据
  lines.push('## 六、AI 依据的参考日志（证据链）');
  const logFiles = result.failed_log_files ?? [];
  if (logFiles.length === 0) {
    lines.push('（无失败日志文件进入 AI 分析）');
  } else {
    lines.push(`本次共 ${logFiles.length} 份失败日志进入 AI 分析，AI 实际读取的内容如下：`);
    logFiles.forEach((logFile, index) => {
      lines.push('');
      lines.push(`### ${index + 1}. ${logFile.test_item}（${logFile.test_time}）`);
      lines.push(`- 日志路径: ${logFile.log_path || '-'}`);
      lines.push(`- 提取方式: ${extractionModeLabel(logFile)}`);
      lines.push(`- 提取模型: ${logFile.model_used || 'default'}${logFile.prompt_model ? `（prompt: ${logFile.prompt_model}）` : ''}`);
      lines.push(`- 错误行: ${logFile.matched_lines} / 总行数: ${logFile.total_lines}`);
      if (logFile.segment_count > 0) {
        lines.push(`- 分块: ${logFile.successful_segments}/${logFile.segment_count} 成功${logFile.failed_segments > 0 ? `，${logFile.failed_segments} 块编码级回退` : ''}`);
      }
      if (logFile.preprocessing_applied) {
        lines.push(`- 规则清洗: 原始 ${logFile.preprocessing_original_lines ?? logFile.total_lines} 行 → 保留 ${logFile.preprocessing_kept_lines ?? 0} 行，过滤 ${logFile.preprocessing_removed_lines ?? 0} 行`);
      }
      if ((logFile.retry_count ?? 0) > 0) {
        lines.push(`- 模型重试: ${logFile.retry_count} 次`);
      }
      lines.push('');
      lines.push('```log');
      lines.push(logFile.extracted_content || '（空）');
      lines.push('```');
    });
  }
  lines.push('');

  if (result.merged_error_log) {
    lines.push('## 七、AI 提取的错误日志（聚合）');
    lines.push('');
    lines.push('```log');
    lines.push(result.merged_error_log);
    lines.push('```');
    lines.push('');
  }

  const knowledgeRefs = result.knowledge_refs ?? [];
  if (knowledgeRefs.length > 0) {
    lines.push('## 八、知识库引用');
    knowledgeRefs.forEach((ref, index) => {
      const title = ref.title || ref.source || `引用 ${index + 1}`;
      lines.push(`${index + 1}. ${title}${ref.content ? ` — ${ref.content}` : ''}`);
    });
    lines.push('');
  }

  if (result.similar_cases?.length) {
    lines.push('## 九、相似历史案例');
    result.similar_cases.forEach((item) => {
      const title = item.title || item.root_cause || '未命名案例';
      const similarity = item.similarity != null ? `（相似度 ${Math.round(item.similarity * 100)}%）` : '';
      lines.push(`- ${title}${similarity}${item.root_cause && item.title ? `：${item.root_cause}` : ''}`);
    });
    lines.push('');
  }

  if (result.maintenance_history?.length) {
    lines.push('## 十、历史维修记录');
    result.maintenance_history.forEach((record) => {
      lines.push(`- ${record.date} · ${record.component} — ${record.action}`);
    });
    lines.push('');
  }

  lines.push('---');
  lines.push('本报告由 WeaveEye 智能诊断系统自动生成，供测试/维修工程师参考。');
  return lines.join('\n');
}


export default function DiagnosisResult({ result, factory, historyId }: DiagnosisResultProps) {
  const catStyle = getCategoryStyle(result.category);
  const failedLogs = collectFailedTestLogs(result);
  const recentLogs = result.test_logs ?? [];
  const diagnosisContext = buildDiagnosisContext(result);

  return (
    <div
      className="relative flex min-h-0 min-w-0 flex-1 flex-col border-b xl:border-b-0 xl:border-r"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div className="custom-scrollbar mx-auto flex w-full flex-1 flex-col gap-6 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="flex items-start gap-4">
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-600 text-white shadow-sm"
            style={{
              boxShadow: '0 4px 12px -3px rgba(37, 99, 235, 0.35)',
            }}
          >
            <Bot className="w-5 h-5" />
          </div>
          <div className="flex-1 space-y-5 mt-1">
            <div
              className="rounded-lg border p-4 text-[13px] leading-6 shadow-sm sm:p-5"
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
              {result.merged_error_log && (
                <div
                  className="mt-4 pt-3 border-t flex items-center justify-between gap-3 flex-wrap"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  <div className="min-w-0">
                    <div className="text-[12px] font-semibold">AI 提取错误日志</div>
                    <div className="text-[11px] mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                      已聚合 {result.failed_log_files?.length ?? 0} 份失败日志，与本次诊断输入一致
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => downloadTextAsFile(result.merged_error_log!, `${result.sn}_extracted_error_logs.txt`)}
                    className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[12px] font-bold transition-opacity hover:opacity-80"
                    style={{ borderColor: 'rgba(16,185,129,0.3)', color: '#059669', backgroundColor: 'rgba(16,185,129,0.08)' }}
                  >
                    <Download className="w-3.5 h-3.5" />
                    下载提取后的错误日志
                  </button>
                </div>
              )}

              {/* AI 分析报告下载：结论 + 证据链（AI 参考的日志与数据） */}
              <div
                className="mt-4 pt-3 border-t flex flex-wrap items-center justify-between gap-3"
                style={{ borderColor: 'var(--color-border)' }}
              >
                <div className="min-w-0">
                  <div className="text-[12px] font-semibold">AI 分析报告</div>
                  <div className="text-[11px] mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                    含诊断结论与 AI 依据的参考日志、知识库引用等完整证据链
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => downloadTextAsFile(buildDiagnosisReport(result, factory), `${result.sn}_AI诊断报告.md`)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[12px] font-bold transition-opacity hover:opacity-80"
                    style={{ borderColor: 'var(--color-border)', color: 'var(--color-accent)', backgroundColor: 'var(--color-bg-primary)' }}
                  >
                    <FileDown className="w-3.5 h-3.5" />
                    下载诊断报告 (Markdown)
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const payload = {
                        sn: result.sn,
                        factory,
                        generated_at: new Date().toISOString(),
                        diagnosis_result: result,
                      };
                      downloadTextAsFile(JSON.stringify(payload, null, 2), `${result.sn}_诊断原始数据.json`);
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[12px] font-bold transition-opacity hover:opacity-80"
                    style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-bg-secondary)' }}
                  >
                    <Database className="w-3.5 h-3.5" />
                    原始数据 (JSON)
                  </button>
                </div>
              </div>
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
                  className="relative overflow-hidden rounded-lg border p-4 shadow-sm sm:p-5"
                  style={{
                    background: catStyle.bg,
                    borderColor: catStyle.border,
                    color: catStyle.text,
                  }}
                >
                  <div
                    className="absolute right-0 top-0 rounded-bl-md px-3 py-1 text-[10px] font-bold text-white shadow-sm"
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
