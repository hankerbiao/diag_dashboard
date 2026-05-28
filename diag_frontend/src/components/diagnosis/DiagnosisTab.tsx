import { useState, useCallback, type KeyboardEvent } from 'react';
import { Bot, RefreshCw } from 'lucide-react';
import type { FactorySite, DiagnosisResult as DiagnosisResultType } from '../../api/fastapi';
import { diagnosisApi } from '../../api/fastapi';
import DiagnosisInput from './DiagnosisInput';
import DiagnosisResult from './DiagnosisResult';
import DiagnosisChat from './DiagnosisChat';

interface DiagnosisTabProps {
  factory: string;
  factorySites: FactorySite[];
}

type SnStage = 'device' | 'logs' | 'cases' | 'ragflow' | 'llm';
const SN_STAGES: SnStage[] = ['device', 'logs', 'cases', 'ragflow', 'llm'];
const SN_STAGE_LABELS: Record<SnStage, string> = {
  device: '查询设备信息',
  logs: '检索测试日志',
  cases: '匹配历史案例',
  ragflow: '检索知识库文档',
  llm: '大模型深度诊断推理',
};

interface SnStageItemProps { stage: SnStage; progress: { stage: string; detail: string } | null; key?: string }
function SnStageItem({ stage, progress }: SnStageItemProps) {
  const idx = SN_STAGES.indexOf(stage);
  const curIdx = progress ? SN_STAGES.indexOf(progress.stage as SnStage) : 0;
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
          <div className="w-2 h-2 rounded-full" style={{ color: 'var(--color-text-muted)' }} />
        )}
      </div>
      <span className={`text-[13px] flex-1 ${cur ? 'font-semibold' : done ? 'font-medium' : ''}`}
        style={{ color: done ? '#10b981' : cur ? 'var(--color-accent)' : 'var(--color-text-muted)' }}>
        {SN_STAGE_LABELS[stage]}
      </span>
      {cur && progress && <span className="text-[11px] animate-pulse" style={{ color: 'var(--color-accent)' }}>{progress.detail}</span>}
    </div>
  );
}

function buildDiagnosisContext(result: DiagnosisResultType): string {
  return `设备 SN: ${result.sn}
故障类别: ${result.category}
置信度: ${Math.round(result.confidence * 100)}%
诊断摘要: ${result.summary}
建议措施: ${result.suggestions.join('; ')}`;
}

export default function DiagnosisTab({ factory, factorySites }: DiagnosisTabProps) {
  const [sn, setSn] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosisResultType | null>(null);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState<{ stage: string; detail: string } | null>(null);
  const [streamingToken, setStreamingToken] = useState('');

  const handleDiagnose = useCallback(() => {
    if (!sn.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    setProgress(null);
    setStreamingToken('');

    diagnosisApi.diagnoseBySNSse(
      sn.trim(),
      factory,
      (stage, detail) => {
        setProgress({ stage, detail });
        if (stage !== 'llm') setStreamingToken('');
      },
      (data) => {
        setResult(data);
        setLoading(false);
        setProgress(null);
      },
      (msg) => {
        setError(msg);
        setLoading(false);
        setProgress(null);
      },
      (token) => {
        setStreamingToken((prev) => prev + token);
      },
    );
  }, [sn, factory]);

  const handleSnKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleDiagnose();
  };

  return (
    <div
      className="flex-1 flex flex-col min-h-0"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <DiagnosisInput
        sn={sn}
        onSnChange={setSn}
        onDiagnose={handleDiagnose}
        loading={loading}
        onKeyDown={handleSnKeyDown}
      />

      <div className="flex-1 flex min-h-0">
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <div className="w-full max-w-lg rounded-2xl border shadow-sm overflow-hidden"
              style={{
                backgroundColor: 'var(--color-bg-secondary)',
                borderColor: 'var(--color-border)',
              }}>
              <div className="px-5 py-3 border-b text-xs font-bold uppercase tracking-widest"
                style={{
                  color: 'var(--color-text-secondary)',
                  borderColor: 'var(--color-border)',
                  backgroundColor: 'var(--color-bg-primary)',
                }}>
                诊断分析进度
              </div>
              <div className="py-3">
                {SN_STAGES.map((s) => (
                  <SnStageItem key={s} stage={s} progress={progress} />
                ))}
              </div>
              {progress?.stage === 'llm' && streamingToken && (
                <div className="px-5 pb-4">
                  <pre className="rounded-lg p-4 border max-h-48 overflow-y-auto custom-scrollbar font-mono text-[12px] leading-relaxed whitespace-pre-wrap break-words"
                    style={{
                      backgroundColor: '#1a1b26',
                      borderColor: '#334155',
                      color: '#e2e8f0',
                    }}>{streamingToken}</pre>
                </div>
              )}
            </div>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <p className="text-sm text-red-500">{error}</p>
            <button
              onClick={handleDiagnose}
              className="px-4 py-2 text-white rounded-lg text-sm font-bold shadow-sm"
              style={{ backgroundColor: 'var(--color-accent)' }}
            >
              重试
            </button>
          </div>
        ) : result ? (
          <div className="flex-1 flex min-h-0">
            <div className="flex-1 flex min-h-0">
              <DiagnosisResult result={result} factory={factory} />
            </div>
            <DiagnosisChat sn={sn} diagnosisContext={buildDiagnosisContext(result)} />
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="max-w-lg w-full space-y-8">
              <div className="text-center space-y-4">
                <div
                  className="w-16 h-16 mx-auto rounded-2xl flex items-center justify-center shadow-lg"
                  style={{
                    background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
                    boxShadow: '0 8px 24px -4px rgba(59, 130, 246, 0.35)',
                  }}
                >
                  <Bot className="w-8 h-8 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>
                    AI 智能诊断
                  </h2>
                  <p className="text-sm mt-1" style={{ color: 'var(--color-text-secondary)' }}>
                    输入产品序列号，一键触发全链路智能分析
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                {[
                  { icon: '🔍', title: '数据聚合', desc: '测试日志 + 维修记录' },
                  { icon: '🧠', title: 'AI 推理', desc: '大模型深度诊断分析' },
                  { icon: '📋', title: '案例匹配', desc: '历史知识图谱关联' },
                ].map((f) => (
                  <div
                    key={f.title}
                    className="rounded-xl p-4 text-center border shadow-sm transition-all hover:shadow-md"
                    style={{
                      backgroundColor: 'var(--color-bg-secondary)',
                      borderColor: 'var(--color-border)',
                    }}
                  >
                    <div className="text-xl mb-2">{f.icon}</div>
                    <div className="text-[12px] font-bold mb-0.5" style={{ color: 'var(--color-text-primary)' }}>
                      {f.title}
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                      {f.desc}
                    </div>
                  </div>
                ))}
              </div>

              <div
                className="rounded-xl border p-5 shadow-sm"
                style={{
                  backgroundColor: 'var(--color-bg-secondary)',
                  borderColor: 'var(--color-border)',
                }}
              >
                <div className="text-[12px] font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                  <span
                    className="w-5 h-5 rounded flex items-center justify-center text-white text-[10px] font-bold"
                    style={{ backgroundColor: 'var(--color-accent)' }}
                  >
                    1
                  </span>
                  输入 SN 码
                  <span className="text-[18px] mx-2" style={{ color: 'var(--color-text-muted)' }}>→</span>
                  <span
                    className="w-5 h-5 rounded flex items-center justify-center text-white text-[10px] font-bold"
                    style={{ backgroundColor: 'var(--color-accent)' }}
                  >
                    2
                  </span>
                  点击「大模型推理」
                  <span className="text-[18px] mx-2" style={{ color: 'var(--color-text-muted)' }}>→</span>
                  <span
                    className="w-5 h-5 rounded flex items-center justify-center text-white text-[10px] font-bold"
                    style={{ backgroundColor: 'var(--color-accent)' }}
                  >
                    3
                  </span>
                  获取诊断报告
                </div>
                <div
                  className="rounded-lg px-4 py-3 text-[12px] leading-relaxed border"
                  style={{
                    backgroundColor: 'var(--color-bg-primary)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  系统将自动聚合设备测试数据、维修记录与历史案例库，通过大模型推理生成故障原因分析及标准修复建议。
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
