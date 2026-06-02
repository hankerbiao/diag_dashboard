import { useState, useCallback, useEffect, useRef, type KeyboardEvent } from 'react';
import { Bot, Clock, ChevronRight, Loader2 } from 'lucide-react';
import type { FactorySite, DiagnosisResult as DiagnosisResultType, SnHistoryItem as SnHistoryItemType } from '../../api/fastapi';
import { diagnosisApi } from '../../api/fastapi';
import DiagnosisInput from './DiagnosisInput';
import DiagnosisResult from './DiagnosisResult';
import DiagnosisChat, { type ChatMessage } from './DiagnosisChat';
import DiagnosisHistoryModal from './DiagnosisHistoryModal';
import ProgressIndicator from '../common/ProgressIndicator';
import SupportHint from '../common/SupportHint';
import { collectFailedTestLogs } from '../../utils/testStatus';

const SN_STAGES = ['device', 'sims', 'logfiles', 'cases', 'ragflow', 'llm'] as const;
const SN_STAGE_LABELS: Record<string, string> = {
  device: '查询设备信息',
  sims: 'SIMS 实时查询测试数据',
  logfiles: '下载失败项原文日志',
  cases: '匹配历史案例',
  ragflow: '检索知识库文档',
  llm: '大模型深度诊断推理',
};

function buildDiagnosisContext(result: DiagnosisResultType) {
  const lines = [
    `设备 SN: ${result.sn}`,
    `故障类别: ${result.category}`,
    `置信度: ${Math.round(result.confidence * 100)}%`,
    `诊断摘要: ${result.summary}`,
  ];
  if (result.root_cause_detail) lines.push(`根因分析: ${result.root_cause_detail}`);
  if (result.affected_components?.length) lines.push(`受影响组件: ${result.affected_components.join(', ')}`);
  if (result.suggestions?.length) lines.push(`维修建议: ${result.suggestions.join('; ')}`);
  if (result.preventive_measures?.length) lines.push(`预防措施: ${result.preventive_measures.join('; ')}`);
  const failed = collectFailedTestLogs(result);
  if (failed.length) {
    lines.push('失败测试项:');
    failed.slice(0, 10).forEach((l) => {
      lines.push(`- [${l.test_time}] ${l.test_item}: ${l.fail_details}`);
    });
  }
  return lines.join('\n');
}

export default function DiagnosisTab({ factory, factorySites }: { factory: string; factorySites: FactorySite[] }) {
  const [sn, setSn] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosisResultType | null>(null);
  const [error, setError] = useState('');
  const [persistWarning, setPersistWarning] = useState('');
  const [progress, setProgress] = useState<{ stage: string; detail: string } | null>(null);
  const [streamingToken, setStreamingToken] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [historyList, setHistoryList] = useState<SnHistoryItemType[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  const factoryLabel = factorySites.find((f) => f.factory_id === factory)?.name ?? factory;
  const factoryReady = Boolean(factory);

  const fetchHistory = useCallback(async () => {
    if (!factory) {
      setHistoryList([]);
      setHistoryTotal(0);
      setHistoryLoading(false);
      return;
    }
    setHistoryLoading(true);
    try {
      const res = await diagnosisApi.getSnHistoryList({ factory, limit: 20 });
      if (res.success && res.data) {
        setHistoryList(res.data.items);
        setHistoryTotal(res.data.total);
      } else {
        setHistoryList([]);
        setHistoryTotal(0);
      }
    } finally {
      setHistoryLoading(false);
    }
  }, [factory]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);
  useEffect(() => () => { abortRef.current?.abort(); }, []);

  const persistDiagnosis = useCallback(async (
    reqId: number,
    snVal: string,
    factoryVal: string,
    data: DiagnosisResultType,
  ) => {
    const saveRes = await diagnosisApi.saveSnHistory(snVal, factoryVal, data as unknown as Record<string, unknown>);
    if (reqId !== requestIdRef.current) return;
    if (saveRes.success && saveRes.data) {
      setHistoryId(saveRes.data.id);
      setActiveHistoryId(saveRes.data.id);
      setPersistWarning('');
    } else {
      setPersistWarning(saveRes.error || '诊断历史未保存，追问将不会持久化');
    }
    fetchHistory();
  }, [fetchHistory]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setProgress(null);
    setStreamingToken('');
    setError('诊断已取消');
  }, []);

  const handleDiagnose = useCallback(() => {
    const snVal = sn.trim();
    if (!snVal) return;
    if (!factory) {
      setError('请先选择运行厂区');
      return;
    }

    abortRef.current?.abort();
    const reqId = ++requestIdRef.current;
    const controller = diagnosisApi.diagnoseBySNSse(
      snVal,
      factory,
      (stage, detail) => {
        if (reqId !== requestIdRef.current) return;
        setProgress({ stage, detail });
        if (stage !== 'llm') setStreamingToken('');
      },
      (data) => {
        if (reqId !== requestIdRef.current) return;
        setResult(data);
        setLoading(false);
        setProgress(null);
        setPersistWarning('');
        void persistDiagnosis(reqId, snVal, factory, data);
      },
      (msg) => {
        if (reqId !== requestIdRef.current) return;
        setError(msg === '请求已取消' ? '诊断已取消' : msg);
        setLoading(false);
        setProgress(null);
      },
      (token) => {
        if (reqId !== requestIdRef.current) return;
        setStreamingToken((prev) => prev + token);
      },
    );
    abortRef.current = controller;

    setLoading(true);
    setError('');
    setPersistWarning('');
    setResult(null);
    setProgress(null);
    setStreamingToken('');
    setChatMessages([]);
    setHistoryId(null);
    setActiveHistoryId(null);
  }, [sn, factory, persistDiagnosis]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !loading && sn.trim() && factoryReady) handleDiagnose();
  }, [loading, sn, factoryReady, handleDiagnose]);

  const handleChatSend = useCallback(async (question: string) => {
    if (!result) return;
    const userMsg: ChatMessage = { role: 'user', content: question };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatLoading(true);
    try {
      const res = await diagnosisApi.followUp(result.sn, question, buildDiagnosisContext(result));
      if (res.success && res.data) {
        const assistantMsg: ChatMessage = { role: 'assistant', content: res.data.answer };
        setChatMessages((prev) => [...prev, assistantMsg]);
        if (historyId) {
          await diagnosisApi.appendChatMessage(historyId, 'user', question).catch(() => {});
          await diagnosisApi.appendChatMessage(historyId, 'assistant', res.data.answer).catch(() => {});
        }
      } else {
        setChatMessages((prev) => [...prev, { role: 'assistant', content: res.error || '追问失败' }]);
      }
    } catch {
      setChatMessages((prev) => [...prev, { role: 'assistant', content: '网络请求失败' }]);
    } finally {
      setChatLoading(false);
    }
  }, [result, historyId]);

  const handleHistoryClick = async (item: SnHistoryItemType) => {
    if (item.id === activeHistoryId) return;
    const res = await diagnosisApi.getSnHistoryDetail(item.id);
    if (res.success && res.data) {
      setSn(res.data.sn);
      setResult(res.data.diagnosis_result);
      setChatMessages(res.data.chat_messages as ChatMessage[]);
      setActiveHistoryId(item.id);
      setHistoryId(item.id);
      setError('');
      setPersistWarning('');
      setLoading(false);
      setProgress(null);
      setStreamingToken('');
      setHistoryExpanded(false);
    } else {
      setError(res.error || '加载历史记录失败');
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0" style={{ backgroundColor: 'var(--color-bg-primary)' }}>
      <DiagnosisInput
        sn={sn}
        factoryLabel={factoryLabel}
        factoryReady={factoryReady}
        onSnChange={setSn}
        onDiagnose={handleDiagnose}
        loading={loading}
        onKeyDown={handleKeyDown}
      />

      {!loading && factoryReady && (
        <div className="px-6 py-2 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
          <button
            type="button"
            onClick={() => setHistoryExpanded(true)}
            className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-widest hover:opacity-80 transition-opacity"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {historyLoading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                历史诊断记录 · 加载中…
              </>
            ) : (
              <>
                <Clock className="w-3.5 h-3.5" />
                历史诊断记录
                {historyTotal > 0
                  ? `（${historyTotal > historyList.length ? `最近 ${historyList.length} / 共 ${historyTotal}` : historyTotal}）`
                  : '（暂无）'}
                <ChevronRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      )}

      {historyExpanded && (
        <DiagnosisHistoryModal
          items={historyList}
          total={historyTotal}
          factorySites={factorySites}
          factoryLabel={factoryLabel}
          activeId={activeHistoryId}
          loading={historyLoading}
          onClose={() => setHistoryExpanded(false)}
          onSelect={handleHistoryClick}
        />
      )}

      <div className="flex-1 flex min-h-0">
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <div
              className="w-full max-w-lg rounded-2xl border shadow-sm overflow-hidden"
              style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
            >
              <div
                className="px-5 py-3 border-b text-xs font-bold uppercase tracking-widest flex items-center justify-between"
                style={{ color: 'var(--color-text-secondary)', borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}
              >
                <span>诊断分析进度</span>
                <button
                  onClick={handleCancel}
                  className="text-[11px] font-bold px-2 py-1 rounded border normal-case tracking-normal"
                  style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
                >
                  取消
                </button>
              </div>
              <div className="py-3">
                <ProgressIndicator
                  stages={[...SN_STAGES]}
                  labels={SN_STAGE_LABELS}
                  currentStage={progress?.stage || null}
                  currentDetail={progress?.detail}
                  streamingText={progress?.stage === 'llm' ? streamingToken : undefined}
                />
              </div>
            </div>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6">
            <p className="text-sm text-red-500 text-center max-w-lg">{error}</p>
            <SupportHint className="max-w-lg text-center justify-center" extra="详细说明见系统设置 → 使用文档" />
            <button
              onClick={handleDiagnose}
              disabled={!factoryReady || !sn.trim()}
              className="px-4 py-2 text-white rounded-lg text-sm font-bold shadow-sm disabled:opacity-50"
              style={{ backgroundColor: 'var(--color-accent)' }}
            >
              重试
            </button>
          </div>
        ) : result ? (
          <div className="flex-1 flex min-h-0 flex-col">
            {persistWarning && (
              <div className="px-6 py-2 text-[12px] shrink-0" style={{ color: '#d97706', backgroundColor: 'rgba(251,191,36,0.1)' }}>
                {persistWarning}
              </div>
            )}
            <div className="flex-1 flex min-h-0">
              <div className="flex-1 flex min-h-0 relative">
                <div className="flex-1 flex min-h-0">
                  <DiagnosisResult result={result} factory={factory} />
                </div>
                <DiagnosisChat messages={chatMessages} loading={chatLoading} onSend={handleChatSend} />
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center p-6 min-h-[120px]">
            <div className="max-w-md w-full text-center space-y-3">
              <div
                className="w-12 h-12 mx-auto rounded-xl flex items-center justify-center shadow-md"
                style={{ background: 'linear-gradient(135deg, #3b82f6, #6366f1)' }}
              >
                <Bot className="w-6 h-6 text-white" />
              </div>
              <h2 className="text-base font-bold" style={{ color: 'var(--color-text-primary)' }}>
                🤖 输入 SN 开始诊断
              </h2>
              {factoryReady ? (
                <>
                  <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                    当前厂区：<span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{factoryLabel}</span>
                    · 点击上方「历史诊断记录」查看
                  </p>
                </>
              ) : (
                <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>⏳ 厂区加载中…</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
