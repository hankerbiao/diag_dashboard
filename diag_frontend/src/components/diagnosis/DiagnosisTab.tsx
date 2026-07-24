import { useState, useCallback, useEffect, useRef, type KeyboardEvent } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  Bot,
  Building2,
  ChevronRight,
  Clock,
  Cpu,
  Database,
  FileSearch,
  Loader2,
  RefreshCw,
  SearchCheck,
  Square,
} from 'lucide-react';
import type { FactorySite, DiagnosisResult as DiagnosisResultType, SnHistoryItem as SnHistoryItemType } from '../../api/fastapi';
import { diagnosisApi } from '../../api/fastapi';
import { useToast } from '../../contexts/ToastContext';
import DiagnosisInput from './DiagnosisInput';
import DiagnosisResult from './DiagnosisResult';
import DiagnosisChat, { type ChatMessage } from './DiagnosisChat';
import DiagnosisHistoryModal from './DiagnosisHistoryModal';
import ProgressIndicator from '../common/ProgressIndicator';
import SupportHint from '../common/SupportHint';
import { collectFailedTestLogs } from '../../utils/testStatus';

const SN_STAGES = [
  'device',
  'prompt',
  'sims',
  'log_download',
  'log_split',
  'log_extract',
  'log_merge',
  'cases',
  'ragflow',
  'llm',
] as const;
const SN_STAGE_LABELS: Record<string, string> = {
  device: '查询设备信息',
  prompt: '加载机型日志提取 Prompt',
  sims: 'SIMS 实时查询测试数据',
  log_download: '下载失败项原文日志',
  log_split: '自适应拆分错误日志',
  log_extract: '调用 AI 提取错误日志',
  log_merge: '聚合全部错误日志',
  cases: '匹配历史案例',
  ragflow: '检索知识库文档',
  llm: '大模型深度诊断推理',
};

interface PromptDetails {
  machineModel: string;
  promptModel: string;
  systemPrompt: string;
  userTemplate: string;
}

interface LogComparisonSummary {
  testItem: string;
  logPath: string;
  originalLines: number;
  keptLines: number;
  removedLines: number;
  removalRate: number;
  preprocessingApplied: boolean;
  recognizedLevelLines: number;
  anomalyEntries: number;
  sourceSize?: number;
  downloadedSize?: number;
  sourceLineCount?: number;
  sourceTruncated?: boolean;
}

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

interface DiagnosisTabProps {
  factory: string;
  factorySites: FactorySite[];
  onFactoryChange: (factoryId: string) => void;
}

function formatHistoryTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function DiagnosisTab({
  factory,
  factorySites,
  onFactoryChange,
}: DiagnosisTabProps) {
  const { toast, dismiss } = useToast();
  const toastRef = useRef<string | null>(null);
  const [sn, setSn] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosisResultType | null>(null);
  const [error, setError] = useState('');
  const [persistWarning, setPersistWarning] = useState('');
  const [progress, setProgress] = useState<{ stage: string; detail: string } | null>(null);
  const [streamingToken, setStreamingToken] = useState('');
  const [skippedStages, setSkippedStages] = useState<Record<string, string>>({});
  const [analysisFileCount, setAnalysisFileCount] = useState<number | null>(null);
  const [promptDetails, setPromptDetails] = useState<PromptDetails | null>(null);
  const [logComparisonSummaries, setLogComparisonSummaries] = useState<LogComparisonSummary[]>([]);
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
  const previousFactoryRef = useRef(factory);

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
  useEffect(() => {
    const previousFactory = previousFactoryRef.current;
    previousFactoryRef.current = factory;
    if (!previousFactory || previousFactory === factory) return;
    requestIdRef.current += 1;
    setResult(null);
    setError('');
    setPersistWarning('');
    setProgress(null);
    setStreamingToken('');
    setChatMessages([]);
    setHistoryId(null);
    setActiveHistoryId(null);
  }, [factory]);

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

    // 显示发送提示
    if (toastRef.current) dismiss(toastRef.current);
    toastRef.current = toast('loading', '正在诊断中...');

    setLoading(true);
    setError('');
    setPersistWarning('');
    setResult(null);
    setProgress({ stage: 'device', detail: '正在查询设备信息...' });
    setSkippedStages({});
    setAnalysisFileCount(null);
    setPromptDetails(null);
    setLogComparisonSummaries([]);
    setStreamingToken('');
    setChatMessages([]);
    setHistoryId(null);
    setActiveHistoryId(null);

    const controller = new AbortController();
    abortRef.current = controller;

    diagnosisApi.diagnoseBySNAnalyze(
      snVal,
      factory,
      (stage, detail, status, meta) => {
        if (reqId === requestIdRef.current) {
          if (typeof meta.file_count === 'number') {
            setAnalysisFileCount(meta.file_count);
          }
          if (meta.system_prompt !== undefined && meta.user_template !== undefined) {
            setPromptDetails({
              machineModel: meta.machine_model || 'default',
              promptModel: meta.prompt_model || 'default',
              systemPrompt: meta.system_prompt,
              userTemplate: meta.user_template,
            });
          }
          if (meta.log_comparison) {
            const comparison = meta.log_comparison;
            const nextSummary: LogComparisonSummary = {
              testItem: comparison.test_item,
              logPath: comparison.log_path,
              originalLines: comparison.original_lines,
              keptLines: comparison.kept_lines,
              removedLines: comparison.removed_lines,
              removalRate: comparison.removal_rate,
              preprocessingApplied: comparison.preprocessing_applied,
              recognizedLevelLines: comparison.recognized_level_lines,
              anomalyEntries: comparison.anomaly_entries,
              sourceSize: comparison.source_size,
              downloadedSize: comparison.downloaded_size,
              sourceLineCount: comparison.source_line_count,
              sourceTruncated: comparison.source_truncated,
            };
            setLogComparisonSummaries((previous) => [
              ...previous.filter((item) => item.logPath !== nextSummary.logPath),
              nextSummary,
            ]);
          }
          if (status === 'skipped') {
            setSkippedStages((previous) => ({ ...previous, [stage]: detail }));
          }
          setProgress({ stage, detail });
        }
      },
      controller.signal,
    ).then((res) => {
      if (reqId !== requestIdRef.current) return;
      if (toastRef.current) {
        dismiss(toastRef.current);
        toastRef.current = null;
      }
      if (res.success && res.data) {
        toast('success', '诊断分析完成');
        setResult(res.data);
        setLoading(false);
        setProgress(null);
        setStreamingToken('');
        setPersistWarning('');
        void persistDiagnosis(reqId, snVal, factory, res.data);
      } else {
        const errorMsg = res.error || '分析失败';
        toast('error', `诊断失败：${errorMsg}`);
        setError(errorMsg);
        setLoading(false);
        setProgress(null);
      }
    }).catch((e) => {
      if (reqId !== requestIdRef.current) return;
      if (toastRef.current) {
        dismiss(toastRef.current);
        toastRef.current = null;
      }
      const errorMsg = controller.signal.aborted ? '诊断已取消'
        : e instanceof Error ? e.message : '网络连接中断';
      toast('error', `诊断失败：${errorMsg}`);
      setError(errorMsg);
      setLoading(false);
      setProgress(null);
    });
  }, [sn, factory, persistDiagnosis, toast, dismiss]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !loading && sn.trim() && factoryReady) handleDiagnose();
  }, [loading, sn, factoryReady, handleDiagnose]);

  const handleChatSend = useCallback(async (question: string) => {
    if (!result) return;
    const userMsg: ChatMessage = { role: 'user', content: question };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatLoading(true);

    const chatToastId = toast('loading', '正在追问...');

    try {
      const res = await diagnosisApi.followUp(result.sn, question, buildDiagnosisContext(result));
      dismiss(chatToastId);
      if (res.success && res.data) {
        const assistantMsg: ChatMessage = { role: 'assistant', content: res.data.answer };
        setChatMessages((prev) => [...prev, assistantMsg]);
        toast('success', '追问回复完成');
        if (historyId) {
          await diagnosisApi.appendChatMessage(historyId, 'user', question).catch(() => {});
          await diagnosisApi.appendChatMessage(historyId, 'assistant', res.data.answer).catch(() => {});
        }
      } else {
        setChatMessages((prev) => [...prev, { role: 'assistant', content: res.error || '追问失败' }]);
        toast('error', res.error || '追问失败');
      }
    } catch {
      dismiss(chatToastId);
      setChatMessages((prev) => [...prev, { role: 'assistant', content: '网络请求失败' }]);
      toast('error', '网络请求失败');
    } finally {
      setChatLoading(false);
    }
  }, [result, historyId, toast, dismiss]);

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

  const hasActiveWorkspace = loading || Boolean(error) || Boolean(result);
  const currentStageIndex = progress?.stage ? SN_STAGES.indexOf(progress.stage as typeof SN_STAGES[number]) : 0;
  const completedStageCount = Math.max(0, currentStageIndex);
  const historyButton = (
    <button
      type="button"
      onClick={() => setHistoryExpanded(true)}
      className="inline-flex items-center gap-2 text-[11px] font-semibold hover:opacity-80"
      style={{ color: 'var(--color-text-secondary)' }}
    >
      {historyLoading ? (
        <>
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          历史记录加载中
        </>
      ) : (
        <>
          <Clock className="h-3.5 w-3.5" />
          历史诊断
          {historyTotal > 0 && ` ${historyTotal}`}
          <ChevronRight className="h-3.5 w-3.5" />
        </>
      )}
    </button>
  );

  return (
    <div className="flex-1 flex flex-col min-h-0" style={{ backgroundColor: 'var(--color-bg-primary)' }}>
      {hasActiveWorkspace && (
        <DiagnosisInput
          sn={sn}
          factory={factory}
          factorySites={factorySites}
          factoryReady={factoryReady}
          onFactoryChange={onFactoryChange}
          onSnChange={setSn}
          onDiagnose={handleDiagnose}
          loading={loading}
          onKeyDown={handleKeyDown}
        />
      )}

      {!loading && factoryReady && hasActiveWorkspace && (
        <div className="shrink-0 border-b px-6 py-2" style={{ borderColor: 'var(--color-border)' }}>
          {historyButton}
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
          <div className="custom-scrollbar flex-1 overflow-y-auto px-4 py-7 sm:px-6 sm:py-9">
            <div
              className="mx-auto w-full max-w-[760px] overflow-hidden rounded-lg border shadow-sm"
              style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
            >
              <div
                className="flex items-start justify-between gap-4 border-b px-5 py-5 sm:px-6"
                style={{ borderColor: 'var(--color-border)' }}
              >
                <div className="flex min-w-0 items-start gap-3">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-600 text-white">
                    <Activity className="h-4 w-4 animate-pulse" />
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-mono text-[15px] font-bold" style={{ color: 'var(--color-text-primary)' }}>{sn.trim()}</h2>
                      <span className="rounded-sm px-2 py-0.5 text-[10px] font-bold" style={{ color: '#2563eb', backgroundColor: 'rgba(37,99,235,0.09)' }}>
                        分析中
                      </span>
                    </div>
                    <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
                      {factoryLabel} · {SN_STAGE_LABELS[progress?.stage ?? 'device']}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleCancel}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border hover:bg-black/5"
                  style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
                  aria-label="取消诊断"
                  title="取消诊断"
                >
                  <Square className="h-3.5 w-3.5" fill="currentColor" />
                </button>
              </div>
              <div className="border-b px-5 py-3 text-[11px] sm:px-6" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)', backgroundColor: 'var(--color-bg-primary)' }}>
                已完成 {completedStageCount} / {SN_STAGES.length} 个分析阶段
              </div>
              <div className="py-3 sm:px-2">
                <ProgressIndicator
                  stages={[...SN_STAGES]}
                  labels={{
                    ...SN_STAGE_LABELS,
                    ...(analysisFileCount !== null
                      ? { log_download: `下载失败项原文日志（${analysisFileCount} 个文件）` }
                      : {}),
                  }}
                  currentStage={progress?.stage || null}
                  currentDetail={progress?.detail}
                  skippedStages={skippedStages}
                  stageDetails={{
                    ...(promptDetails ? {
                      prompt: [
                        { label: '设备机型', value: promptDetails.machineModel },
                        { label: '使用 Prompt', value: promptDetails.promptModel },
                        { label: 'System Prompt', value: promptDetails.systemPrompt, multiline: true },
                        { label: 'User Template', value: promptDetails.userTemplate, multiline: true },
                      ],
                    } : {}),
                    ...(logComparisonSummaries.length > 0 ? {
                      log_split: logComparisonSummaries.map((item) => ({
                        label: item.testItem || item.logPath,
                        value: item.sourceTruncated
                          ? `源文件约 ${item.sourceLineCount ?? 0} 行 / ${Math.round((item.sourceSize ?? 0) / 1024)} KB，按头尾保留 ${Math.round((item.downloadedSize ?? 0) / 1024)} KB；采样内容 ${item.originalLines} 行，清洗后 ${item.keptLines} 行`
                          : item.preprocessingApplied
                            ? `原文件 ${item.originalLines} 行，清洗后 ${item.keptLines} 行，过滤 ${item.removedLines} 行（${(item.removalRate * 100).toFixed(1)}%）；识别 ${item.recognizedLevelLines} 个级别标记、${item.anomalyEntries} 个异常事件`
                            : `原文件 ${item.originalLines} 行，未触发规则清洗，全文进入后续提取`,
                      })),
                    } : {}),
                  }}
                  streamingText={progress?.stage === 'llm' ? streamingToken : undefined}
                />
              </div>
            </div>
          </div>
        ) : error ? (
          <div className="custom-scrollbar flex-1 overflow-y-auto px-4 py-10 sm:px-6">
            <section
              className="mx-auto w-full max-w-[620px] rounded-lg border p-6 shadow-sm sm:p-8"
              style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
            >
              <div className="flex items-start gap-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md" style={{ color: '#dc2626', backgroundColor: 'rgba(239,68,68,0.09)' }}>
                  <AlertCircle className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-[15px] font-bold" style={{ color: 'var(--color-text-primary)' }}>诊断未完成</h2>
                  <p className="mt-2 text-[13px] leading-6" style={{ color: '#dc2626' }}>{error}</p>
                  <div className="mt-4"><SupportHint extra="详细说明见系统设置 → 使用文档" /></div>
                  <button
                    type="button"
                    onClick={handleDiagnose}
                    disabled={!factoryReady || !sn.trim()}
                    className="mt-5 inline-flex h-10 items-center gap-2 rounded-md bg-blue-600 px-4 text-[12px] font-bold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
                  >
                    <RefreshCw className="h-4 w-4" />
                    重新诊断
                  </button>
                </div>
              </div>
            </section>
          </div>
        ) : result ? (
          <div className="flex-1 flex min-h-0 flex-col">
            {persistWarning && (
              <div className="px-6 py-2 text-[12px] shrink-0" style={{ color: '#d97706', backgroundColor: 'rgba(251,191,36,0.1)' }}>
                {persistWarning}
              </div>
            )}
            <div className="flex-1 flex min-h-0">
              <div className="relative flex min-h-0 flex-1 flex-col xl:flex-row">
                <div className="flex min-h-0 min-w-0 flex-1">
                  <DiagnosisResult result={result} factory={factory} historyId={historyId} />
                </div>
                <DiagnosisChat messages={chatMessages} loading={chatLoading} onSend={handleChatSend} />
              </div>
            </div>
          </div>
        ) : (
          <div className="custom-scrollbar flex-1 overflow-y-auto">
            <div className="mx-auto min-h-full w-full max-w-[1080px] px-4 py-8 sm:px-6 sm:py-10 lg:px-8 lg:py-12">
              <header className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
                <div>
                  <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase" style={{ color: 'var(--color-accent)' }}>
                    <Activity className="h-3.5 w-3.5" />
                    Single Device Diagnosis
                  </div>
                  <h2 className="text-[26px] font-bold sm:text-[30px]" style={{ color: 'var(--color-text-primary)', letterSpacing: 0 }}>
                    定位一台设备，从 SN 开始
                  </h2>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                  <span className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
                    <Building2 className="h-3.5 w-3.5" />
                    {factoryLabel || '厂区加载中'}
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
                    <SearchCheck className="h-3.5 w-3.5" />
                    {SN_STAGES.length} 项分析流程
                  </span>
                </div>
              </header>

              <div className="space-y-6">
                <section
                  className="overflow-hidden rounded-lg border shadow-sm"
                  style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
                >
                  <div className="flex items-center justify-between gap-4 border-b px-5 py-5 sm:px-8" style={{ borderColor: 'var(--color-border)' }}>
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-600 text-white">
                        <Bot className="h-5 w-5" />
                      </span>
                      <div>
                        <h3 className="text-[15px] font-bold" style={{ color: 'var(--color-text-primary)' }}>发起深度诊断</h3>
                        <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>当前厂区：{factoryLabel || '正在加载'}</p>
                      </div>
                    </div>
                    <span className="hidden text-[10px] font-semibold sm:inline" style={{ color: 'var(--color-text-muted)' }}>AI ENGINE READY</span>
                  </div>

                  <div className="px-5 py-8 sm:px-8 sm:py-10 lg:px-10">
                    <DiagnosisInput
                      sn={sn}
                      factory={factory}
                      factorySites={factorySites}
                      factoryReady={factoryReady}
                      onFactoryChange={onFactoryChange}
                      onSnChange={setSn}
                      onDiagnose={handleDiagnose}
                      loading={loading}
                      onKeyDown={handleKeyDown}
                      centered
                    />
                  </div>

                  <div
                    className="grid border-t sm:grid-cols-3"
                    style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}
                  >
                    {[
                      { icon: Database, label: 'SIMS 测试数据' },
                      { icon: FileSearch, label: '错误日志提取' },
                      { icon: Cpu, label: 'AI 根因推理' },
                    ].map(({ icon: Icon, label }, index) => (
                      <div
                        key={label}
                        className={`flex items-center gap-2.5 px-5 py-4 text-[12px] sm:px-8 ${index > 0 ? 'border-t sm:border-l sm:border-t-0' : ''}`}
                        style={{ borderColor: 'var(--color-border)' }}
                      >
                        <Icon className="h-3.5 w-3.5" style={{ color: 'var(--color-accent)' }} />
                        {label}
                      </div>
                    ))}
                  </div>
                </section>

                <section
                  className="overflow-hidden rounded-lg border shadow-sm"
                  style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
                >
                  <div className="flex h-[68px] items-center justify-between gap-3 border-b px-5 sm:px-8" style={{ borderColor: 'var(--color-border)' }}>
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4" style={{ color: 'var(--color-accent)' }} />
                      <h3 className="text-[14px] font-bold" style={{ color: 'var(--color-text-primary)' }}>最近诊断</h3>
                    </div>
                    {historyTotal > 0 && (
                      <button
                        type="button"
                        onClick={() => setHistoryExpanded(true)}
                        className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-semibold hover:bg-black/5"
                        style={{ color: 'var(--color-text-secondary)' }}
                        aria-label="查看全部历史诊断"
                        title="查看全部"
                      >
                        全部 {historyTotal}
                        <ArrowUpRight className="h-4 w-4" />
                      </button>
                    )}
                  </div>

                  <div className="min-h-[116px]">
                    {historyLoading ? (
                      <div className="flex h-[116px] items-center justify-center gap-2 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        加载中
                      </div>
                    ) : historyList.length === 0 ? (
                      <div className="flex h-[116px] flex-col items-center justify-center px-6 text-center">
                        <Clock className="mb-3 h-5 w-5" style={{ color: 'var(--color-text-muted)' }} />
                        <p className="text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>当前厂区暂无诊断记录</p>
                      </div>
                    ) : (
                      <div className="grid gap-px sm:grid-cols-2 xl:grid-cols-4" style={{ backgroundColor: 'var(--color-border)' }}>
                        {historyList.slice(0, 4).map((item) => (
                          <button
                            key={item.id}
                            type="button"
                            onClick={() => void handleHistoryClick(item)}
                            className="group relative block min-h-[116px] w-full px-5 py-4 pr-10 text-left transition hover:brightness-[0.98] dark:hover:brightness-110 sm:px-6 sm:pr-10"
                            style={{ backgroundColor: 'var(--color-bg-secondary)' }}
                          >
                            <span className="block text-[10px] font-semibold" style={{ color: 'var(--color-text-muted)' }}>
                              设备 SN
                            </span>
                            <span className="mt-1 block whitespace-nowrap font-mono text-[12px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
                              {item.sn}
                            </span>
                            <span className="mt-3 flex items-center justify-between gap-2 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                              <span className="truncate">{item.category || '未分类'}</span>
                              <span className="shrink-0">{formatHistoryTime(item.created_at)}</span>
                            </span>
                            <ChevronRight className="absolute right-4 top-[43px] h-4 w-4 opacity-50 transition-transform group-hover:translate-x-0.5" style={{ color: 'var(--color-text-muted)' }} />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                </section>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
