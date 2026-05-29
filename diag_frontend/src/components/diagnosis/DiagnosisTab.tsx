import { useState, useCallback, useEffect, useRef, type KeyboardEvent } from 'react';
import { Bot, RefreshCw, Clock, ChevronRight } from 'lucide-react';
import type { FactorySite, DiagnosisResult as DiagnosisResultType, SnHistoryItem as SnHistoryItemType } from '../../api/fastapi';
import { diagnosisApi } from '../../api/fastapi';
import DiagnosisInput from './DiagnosisInput';
import DiagnosisResult from './DiagnosisResult';
import DiagnosisChat, { type ChatMessage } from './DiagnosisChat';
import DiagnosisHistoryModal from './DiagnosisHistoryModal';
import ProgressIndicator from '../common/ProgressIndicator';

const SN_STAGES = ['device', 'logs', 'cases', 'ragflow', 'llm'] as const;
const SN_STAGE_LABELS: Record<string, string> = {
  device: '查询设备信息', logs: '检索测试日志', cases: '匹配历史案例',
  ragflow: '检索知识库文档', llm: '大模型深度诊断推理',
};

function buildDiagnosisContext(result: DiagnosisResultType) {
  return `设备 SN: ${result.sn}\n故障类别: ${result.category}\n置信度: ${Math.round(result.confidence * 100)}%\n诊断摘要: ${result.summary}\n建议措施: ${result.suggestions.join('; ')}`;
}

export default function DiagnosisTab({ factory }: { factory: string; factorySites: FactorySite[] }) {
  const [sn, setSn] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosisResultType | null>(null);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState<{ stage: string; detail: string } | null>(null);
  const [streamingToken, setStreamingToken] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [historyList, setHistoryList] = useState<SnHistoryItemType[]>([]);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchHistory = useCallback(async () => {
    const res = await diagnosisApi.getSnHistoryList({ limit: 20 });
    if (res.success && res.data) setHistoryList(res.data.items);
  }, []);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);
  useEffect(() => () => { abortRef.current?.abort(); }, []);

  const persistDiagnosis = useCallback(async (snVal: string, factoryVal: string, data: DiagnosisResultType) => {
    const saveRes = await diagnosisApi.saveSnHistory(snVal, factoryVal, data as unknown as Record<string, unknown>);
    if (saveRes.success && saveRes.data) {
      setHistoryId(saveRes.data.id);
      setActiveHistoryId(saveRes.data.id);
    }
    fetchHistory();
  }, [fetchHistory]);

  const handleDiagnose = useCallback(() => {
    if (!sn.trim()) return;
    abortRef.current?.abort();
    setLoading(true); setError(''); setResult(null); setProgress(null);
    setStreamingToken(''); setChatMessages([]); setHistoryId(null); setActiveHistoryId(null);

    diagnosisApi.diagnoseBySNSse(
      sn.trim(), factory,
      (stage, detail) => { setProgress({ stage, detail }); if (stage !== 'llm') setStreamingToken(''); },
      async (data) => { setResult(data); setLoading(false); setProgress(null); persistDiagnosis(sn.trim(), factory, data as unknown as Record<string, unknown>); },
      (msg) => { setError(msg); setLoading(false); setProgress(null); },
      (token) => setStreamingToken(prev => prev + token),
    ).then(ctrl => { abortRef.current = ctrl; });
  }, [sn, factory, persistDiagnosis]);

  const handleChatSend = useCallback(async (question: string) => {
    if (!result) return;
    const userMsg: ChatMessage = { role: 'user', content: question };
    setChatMessages(prev => [...prev, userMsg]);
    setChatLoading(true);
    try {
      const res = await diagnosisApi.followUp(sn.trim(), question, buildDiagnosisContext(result));
      if (res.success && res.data) {
        const assistantMsg: ChatMessage = { role: 'assistant', content: res.data.answer };
        setChatMessages(prev => [...prev, assistantMsg]);
        if (historyId) {
          diagnosisApi.appendChatMessage(historyId, 'user', question).catch(() => {});
          diagnosisApi.appendChatMessage(historyId, 'assistant', res.data.answer).catch(() => {});
        }
      } else {
        setChatMessages(prev => [...prev, { role: 'assistant', content: res.error || '追问失败' }]);
      }
    } catch { setChatMessages(prev => [...prev, { role: 'assistant', content: '网络请求失败' }]); }
    finally { setChatLoading(false); }
  }, [result, sn, historyId]);

  const handleHistoryClick = async (item: SnHistoryItemType) => {
    if (item.id === activeHistoryId) return;
    const res = await diagnosisApi.getSnHistoryDetail(item.id);
    if (res.success && res.data) {
      setResult(res.data.diagnosis_result);
      setChatMessages(res.data.chat_messages as ChatMessage[]);
      setActiveHistoryId(item.id); setHistoryId(item.id);
      setError(''); setLoading(false); setProgress(null); setStreamingToken('');
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0" style={{ backgroundColor: 'var(--color-bg-primary)' }}>
      <DiagnosisInput sn={sn} onSnChange={setSn} onDiagnose={handleDiagnose} loading={loading} onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && handleDiagnose()} />

      {historyList.length > 0 && !loading && (
        <div className="px-6 py-2 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
          <button onClick={() => setHistoryExpanded(true)} className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-secondary)' }}>
            <Clock className="w-3.5 h-3.5" />历史诊断记录（{historyList.length}）<ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {historyExpanded && <DiagnosisHistoryModal items={historyList} activeId={activeHistoryId} onClose={() => setHistoryExpanded(false)} onSelect={handleHistoryClick} />}

      <div className="flex-1 flex min-h-0">
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <div className="w-full max-w-lg rounded-2xl border shadow-sm overflow-hidden" style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
              <div className="px-5 py-3 border-b text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-secondary)', borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>诊断分析进度</div>
              <div className="py-3"><ProgressIndicator stages={[...SN_STAGES]} labels={SN_STAGE_LABELS} currentStage={progress?.stage || null} streamingText={progress?.stage === 'llm' ? streamingToken : undefined} /></div>
            </div>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <p className="text-sm text-red-500">{error}</p>
            <button onClick={handleDiagnose} className="px-4 py-2 text-white rounded-lg text-sm font-bold shadow-sm" style={{ backgroundColor: 'var(--color-accent)' }}>重试</button>
          </div>
        ) : result ? (
          <div className="flex-1 flex min-h-0">
            <div className="flex-1 flex min-h-0 relative">
              <div className="flex-1 flex min-h-0"><DiagnosisResult result={result} factory={factory} /></div>
              <DiagnosisChat messages={chatMessages} loading={chatLoading} onSend={handleChatSend} />
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="max-w-lg w-full space-y-8">
              <div className="text-center space-y-4">
                <div className="w-16 h-16 mx-auto rounded-2xl flex items-center justify-center shadow-lg" style={{ background: 'linear-gradient(135deg, #3b82f6, #6366f1)', boxShadow: '0 8px 24px -4px rgba(59, 130, 246, 0.35)' }}>
                  <Bot className="w-8 h-8 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>AI 智能诊断</h2>
                  <p className="text-sm mt-1" style={{ color: 'var(--color-text-secondary)' }}>基于海光DCU算力，输入产品序列号一键触发全链路智能分析</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[{ icon: '🔍', title: '数据聚合', desc: '测试日志 + 维修记录' }, { icon: '🧠', title: 'AI 推理', desc: '海光DCU大模型深度诊断' }, { icon: '📋', title: '案例匹配', desc: '历史知识图谱关联' }].map(f => (
                  <div key={f.title} className="rounded-xl p-4 text-center border shadow-sm transition-all hover:shadow-md" style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
                    <div className="text-xl mb-2">{f.icon}</div>
                    <div className="text-[12px] font-bold mb-0.5" style={{ color: 'var(--color-text-primary)' }}>{f.title}</div>
                    <div className="text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>{f.desc}</div>
                  </div>
                ))}
              </div>
              <div className="rounded-xl border p-5 shadow-sm" style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
                <div className="text-[12px] font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                  {[1, 2, 3].map(n => (
                    <span key={n} className="w-5 h-5 rounded flex items-center justify-center text-white text-[10px] font-bold" style={{ backgroundColor: 'var(--color-accent)' }}>{n}</span>
                  ))}
                  <span>输入 SN 码</span><span className="text-[18px] mx-2" style={{ color: 'var(--color-text-muted)' }}>→</span>
                  <span>点击「大模型推理」</span><span className="text-[18px] mx-2" style={{ color: 'var(--color-text-muted)' }}>→</span>
                  <span>获取诊断报告</span>
                </div>
                <div className="rounded-lg px-4 py-3 text-[12px] leading-relaxed border" style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
                  系统运行在海光DCU加速服务器上，自动聚合设备测试数据、维修记录与历史案例库，通过大模型推理生成故障原因分析及标准修复建议。
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}