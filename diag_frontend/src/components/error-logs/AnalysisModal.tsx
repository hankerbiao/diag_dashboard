import { useState, useMemo } from 'react';
import { Bot, Sparkles, AlertTriangle, Wrench, Terminal, RefreshCw, X, BookOpen, FileText } from 'lucide-react';
import type { ErrorLogRow } from '../../types';
import type { DiagnosisCache } from '../../api/fastapi';

interface AnalysisModalProps {
  selectedLog: ErrorLogRow | null;
  analyzingId: string | null;
  analysisResult: Record<string, DiagnosisCache>;
  analyzingProgress?: { stage: string; detail: string } | null;
  streamingText?: string;
  onClose: () => void;
  onReAnalyze: (id: string) => void;
}

type Stage = 'download' | 'ragflow' | 'llm';
const STAGES: Stage[] = ['download', 'ragflow', 'llm'];
const STAGE_LABELS: Record<Stage, string> = {
  download: '下载日志文件',
  ragflow: '查询知识库参考文档',
  llm: '大模型深度诊断推理',
};

const S = {
  card: { backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' },
  mono: { backgroundColor: '#1a1b26', borderColor: '#334155', color: '#e2e8f0' },
  muted: { color: 'var(--color-text-muted)' },
  accent: { color: 'var(--color-accent)' },
};

function StageItem({ stage, progress }: { stage: Stage; progress?: { stage: string; detail: string } | null }) {
  const idx = STAGES.indexOf(stage);
  const curIdx = progress ? STAGES.indexOf(progress.stage as Stage) : 0;
  const done = idx < curIdx, cur = idx === curIdx;

  return (
    <div className="flex items-center gap-3 py-2.5 px-4 rounded-lg">
      <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
        style={{ backgroundColor: done ? '#10b981' : cur ? 'var(--color-accent)' : 'var(--color-border)' }}>
        {done ? (
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        ) : cur ? (
          <RefreshCw className="w-3.5 h-3.5 animate-spin text-white" />
        ) : (
          <div className="w-2 h-2 rounded-full" style={S.muted} />
        )}
      </div>
      <span className={`text-[13px] flex-1 ${cur ? 'font-semibold' : done ? 'font-medium' : ''}`}
        style={{ color: done ? '#10b981' : cur ? 'var(--color-accent)' : 'var(--color-text-muted)' }}>
        {STAGE_LABELS[stage]}
      </span>
      {cur && progress && <span className="text-[11px] animate-pulse" style={S.accent}>{progress.detail}</span>}
    </div>
  );
}

export default function AnalysisModal({
  selectedLog, analyzingId, analysisResult, analyzingProgress, streamingText, onClose, onReAnalyze,
}: AnalysisModalProps) {
  if (!selectedLog) return null;

  const isAnalyzing = analyzingId === selectedLog.id;
  const result = analysisResult[selectedLog.id];
  const [showRawLog, setShowRawLog] = useState(false);

  const analysisSegments = useMemo(() => {
    if (!result?.analysis) return null;
    const refs = result.knowledge_refs || [];
    const parts: Array<{ type: 'text' | 'ref'; key: string; content: string; refSource?: string }> = [];
    const pattern = /\[参考\s*(\d+)\]/g;
    let last = 0, match: RegExpExecArray | null;
    while ((match = pattern.exec(result.analysis)) !== null) {
      if (match.index > last) parts.push({ type: 'text', key: `t-${last}`, content: result.analysis.slice(last, match.index) });
      const ref = refs[parseInt(match[1], 10) - 1];
      parts.push({ type: 'ref', key: `ref-${match[1]}`, content: `[参考 ${match[1]}]`, refSource: ref?.source });
      last = match.index + match[0].length;
    }
    if (last < result.analysis.length) parts.push({ type: 'text', key: `t-${last}`, content: result.analysis.slice(last) });
    return parts;
  }, [result?.analysis, result?.knowledge_refs]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
      style={{ backdropFilter: 'blur(4px)', backgroundColor: 'rgba(15, 23, 42, 0.12)' }}>
      <div className="w-full max-w-4xl max-h-[85vh] shadow-2xl rounded-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-300 border"
        style={S.card}>
        {/* Header */}
        <div className="h-[65px] px-6 border-b flex items-center justify-between shrink-0"
          style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}>
          <h3 className="font-bold flex items-center gap-2.5 text-base" style={{ color: 'var(--color-text-primary)' }}>
            <span className="w-8 h-8 rounded-lg flex items-center justify-center shadow-sm"
              style={{ backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)' }}>
              <Bot className="w-5 h-5" />
            </span>
            大模型缺陷诊断与修复研判中心
          </h3>
          <div className="flex items-center gap-3">
            {result && !isAnalyzing && (
              <>
                <button onClick={() => setShowRawLog(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-bold transition-colors active:scale-95 border"
                  style={{ backgroundColor: '#1a1b26', color: '#f87171', borderColor: '#334155' }}>
                  <FileText className="w-3.5 h-3.5" /> 查看原始日志
                </button>
                <button onClick={() => onReAnalyze(selectedLog.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-bold transition-colors active:scale-95 border"
                  style={{ backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)', borderColor: 'var(--color-border)' }}>
                  <RefreshCw className="w-3.5 h-3.5" /> 重新生成
                </button>
              </>
            )}
            {isAnalyzing && !!result && (
              <div className="flex items-center gap-2 text-xs font-medium" style={S.accent}>
                <RefreshCw className="w-4 h-4 animate-spin" /> 重新生成中...
              </div>
            )}
            <button onClick={onClose} className="p-2 rounded-full transition-colors active:scale-95" style={{ color: 'var(--color-text-secondary)' }}>
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 min-h-0 p-6 md:p-8 flex flex-col md:flex-row gap-8">
          {/* Left: Snapshot */}
          <div className="w-full md:w-1/3 space-y-5 flex flex-col min-h-0 overflow-y-auto custom-scrollbar">
            <h4 className="text-[12px] font-bold uppercase tracking-widest border-b pb-2"
              style={{ color: 'var(--color-text-secondary)', borderColor: 'var(--color-border)' }}>异常追踪快照</h4>

            <div className="space-y-4">
              <div>
                <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>被测对象 SN</div>
                <div className="text-sm font-mono font-semibold px-2.5 py-1 rounded border inline-flex shadow-sm"
                  style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}>
                  {selectedLog.sn}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>测试项目</div>
                  <div className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>{selectedLog.testItem}</div>
                </div>
                <div>
                  <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>拦截状态</div>
                  <div className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold shadow-sm border"
                    style={{ backgroundColor: 'rgba(239,68,68,0.1)', color: '#dc2626', borderColor: 'rgba(239,68,68,0.2)' }}>
                    {selectedLog.status}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>发生时间</div>
                  <div className="text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>{selectedLog.testTime}</div>
                </div>
                <div>
                  <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>判定结论</div>
                  <div className="text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>{selectedLog.decision}</div>
                </div>
              </div>
            </div>

            {result?.knowledge_refs?.length ? (
              <div>
                <div className="text-[11px] mb-2 font-semibold" style={{ color: 'var(--color-text-secondary)' }}>知识库参考文档</div>
                <ul className="space-y-2">
                  {result.knowledge_refs.map((ref, i) => (
                    <li key={i}>
                      <details className="group">
                        <summary className="text-[11px] px-2 py-1.5 rounded-lg border cursor-pointer hover:opacity-80 transition-colors list-none flex items-center gap-1.5"
                          style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-accent)' }}>
                          <svg className="w-3 h-3 shrink-0 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                          </svg>
                          <span className="truncate flex-1">{ref.source}</span>
                        </summary>
                        {ref.content && (
                          <div className="mt-1 text-[11px] leading-relaxed p-2.5 rounded-lg border whitespace-pre-wrap max-h-32 overflow-y-auto custom-scrollbar"
                            style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
                            {ref.content}
                          </div>
                        )}
                      </details>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>

          {/* Right: Analysis Result */}
          <div className="w-full md:w-2/3 flex flex-col min-h-0 border-l pl-0 md:pl-8" style={{ borderColor: 'var(--color-border)' }}>
            <h4 className="text-[12px] font-bold uppercase tracking-widest border-b pb-2 flex items-center gap-2 mb-4 flex-none"
              style={{ color: 'var(--color-text-secondary)', borderColor: 'var(--color-border)' }}>
              <Sparkles className="w-4 h-4" style={{ color: 'var(--color-accent)' }} /> 高维图谱聚类分析结果
              {result?.is_cached && <span className="text-[11px] font-normal text-slate-400 ml-auto">（缓存结果）</span>}
            </h4>

            <div className="rounded-xl p-6 relative overflow-y-auto transition-all shadow-sm flex-1 flex flex-col min-h-0 border"
              style={{ backgroundColor: 'var(--color-accent-light)', borderColor: 'var(--color-border)' }}>
              {isAnalyzing && <div className="absolute top-0 left-0 w-full h-1 animate-pulse" style={{ backgroundColor: 'var(--color-accent)' }} />}

              {isAnalyzing && !result ? (
                <div className="flex flex-col justify-center flex-1 py-8 gap-1">
                  {STAGES.map((s) => <StageItem stage={s} progress={analyzingProgress} />)}
                  {analyzingProgress?.stage === 'llm' && streamingText && (
                    <pre className="mt-4 rounded-lg p-4 border max-h-64 overflow-y-auto custom-scrollbar font-mono text-[12px] leading-relaxed whitespace-pre-wrap break-words"
                      style={S.mono}>{streamingText}</pre>
                  )}
                </div>
              ) : result ? (
                <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
                  <div className="space-y-3">
                    <h5 className="flex items-center gap-1.5 text-xs font-bold" style={{ color: 'var(--color-accent)' }}>
                      <AlertTriangle className="w-3.5 h-3.5" /> 核心诱因推盘
                    </h5>
                    <div className="text-[13px] leading-relaxed p-3.5 rounded-lg border shadow-sm" style={S.card}>
                      {result.root_cause}
                    </div>
                  </div>

                  {result.evidence?.length ? (
                    <div className="space-y-3">
                      <h5 className="flex items-center gap-1.5 text-xs font-bold" style={{ color: '#d97706' }}>
                        <Terminal className="w-3.5 h-3.5" /> 关键证据
                      </h5>
                      <ul className="text-[12px] space-y-3 p-3.5 rounded-lg border shadow-sm font-mono" style={S.mono}>
                        {result.evidence.map((e, i) => (
                          <li key={i} className="leading-relaxed">
                            <div className="flex gap-2">
                              <span className="text-amber-400 font-bold shrink-0">[{i + 1}]</span>
                              <span>{e.log_line}</span>
                            </div>
                            {e.conclusion && (
                              <div className="mt-1 ml-5 text-[11px] text-slate-400">→ {e.conclusion}</div>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  <div className="space-y-3">
                    <h5 className="flex items-center gap-1.5 text-xs font-bold" style={{ color: '#2563eb' }}>
                      <Sparkles className="w-3.5 h-3.5" /> 详细分析
                    </h5>
                    <div className="text-[13px] leading-relaxed p-3.5 rounded-lg border shadow-sm whitespace-pre-wrap" style={S.card}>
                      {analysisSegments ? analysisSegments.map((seg) =>
                        seg.type === 'ref' ? (
                          <span key={seg.key}
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-bold cursor-help mx-0.5 border"
                            style={{ backgroundColor: 'rgba(99,102,241,0.15)', color: '#818cf8', borderColor: 'rgba(99,102,241,0.25)' }}
                            title={seg.refSource ? `来源: ${seg.refSource}` : '参考来源'}>
                            <BookOpen className="w-3 h-3" />{seg.content}
                          </span>
                        ) : <span key={seg.key}>{seg.content}</span>
                      ) : result.analysis}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h5 className="flex items-center gap-1.5 text-xs font-bold text-emerald-700">
                      <Wrench className="w-3.5 h-3.5" /> 修复工程指引
                    </h5>
                    <ul className="text-[13px] space-y-2 p-4 rounded-lg border shadow-sm"
                      style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'rgba(16,185,129,0.2)', color: 'var(--color-text-primary)' }}>
                      {result.repair_suggestions.map((s, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-emerald-500 font-bold shrink-0">{i + 1}.</span>
                          <span>{s}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {/* Raw Log Modal */}
      {showRawLog && result && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-8 animate-in fade-in duration-200"
          style={{ backgroundColor: 'rgba(0,0,0,0.6)' }} onClick={() => setShowRawLog(false)}>
          <div className="w-full max-w-3xl max-h-[80vh] rounded-xl shadow-2xl flex flex-col overflow-hidden border animate-in zoom-in-95 duration-200"
            style={S.mono} onClick={(e) => e.stopPropagation()}>
            <div className="h-12 px-5 border-b flex items-center justify-between shrink-0" style={{ borderColor: '#334155' }}>
              <div className="flex items-center gap-2 text-[13px] font-bold" style={{ color: '#f87171' }}>
                <Terminal className="w-4 h-4" />
                原始日志{result.log_content ? `（尾部 ${result.log_content.split('\n').length} 行）` : ''}
              </div>
              <button onClick={() => setShowRawLog(false)} className="p-1.5 rounded-lg transition-colors hover:bg-slate-700/50"
                style={{ color: '#64748b' }}><X className="w-4 h-4" /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 custom-scrollbar">
              {result.log_content ? (
                <pre className="font-mono text-[13px] leading-relaxed whitespace-pre-wrap break-words" style={S.mono}>
                  {result.log_content}
                </pre>
              ) : (
                <div className="flex items-center justify-center h-32 text-sm" style={{ color: '#64748b' }}>
                  日志内容不可用，请点击「重新生成」获取最新分析
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}