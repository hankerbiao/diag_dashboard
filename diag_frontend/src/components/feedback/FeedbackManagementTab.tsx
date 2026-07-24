import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDot,
  Clock3,
  Loader2,
  MessageSquareText,
  Paperclip,
  RefreshCw,
  Search,
  X,
} from 'lucide-react';
import {
  diagnosisApi,
  knowledgeBaseApi,
  type DiagnosisFeedback,
  type DiagnosisRating,
  type FactorySite,
  type FeedbackStatus,
  type FeedbackSummary,
} from '../../api/fastapi';
import { useToast } from '../../contexts/ToastContext';

interface FeedbackManagementTabProps {
  factory: string;
  factorySites: FactorySite[];
}

const PAGE_SIZE = 20;
const MAX_KNOWLEDGE_ATTACHMENTS = 19;
const MAX_KNOWLEDGE_FILE_SIZE = 50 * 1024 * 1024;
const EMPTY_SUMMARY: FeedbackSummary = {
  total: 0,
  solved: 0,
  partially: 0,
  unsolved: 0,
  pending: 0,
  processing: 0,
  solved_rate: 0,
};

const RATING_LABELS: Record<DiagnosisRating, string> = {
  solved: '可以解决',
  partially: '部分解决',
  unsolved: '未解决',
};

const STATUS_OPTIONS: Array<{
  value: FeedbackStatus;
  label: string;
  icon: typeof Clock3;
}> = [
  { value: 'pending', label: '待处理', icon: Clock3 },
  { value: 'processing', label: '处理中', icon: CircleDot },
  { value: 'resolved', label: '已关闭', icon: CheckCircle2 },
  { value: 'ignored', label: '已忽略', icon: X },
];

function formatTime(value: string): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.replace('T', ' ').slice(0, 19);
  return date.toLocaleString('zh-CN', { hour12: false });
}

function ratingStyle(rating: DiagnosisRating) {
  if (rating === 'solved') return { color: '#047857', backgroundColor: 'rgba(5,150,105,0.10)' };
  if (rating === 'partially') return { color: '#a16207', backgroundColor: 'rgba(202,138,4,0.11)' };
  return { color: '#b91c1c', backgroundColor: 'rgba(220,38,38,0.09)' };
}

function statusStyle(status: FeedbackStatus) {
  if (status === 'processing') return { color: '#1d4ed8', backgroundColor: 'rgba(37,99,235,0.10)' };
  if (status === 'resolved') return { color: '#047857', backgroundColor: 'rgba(5,150,105,0.10)' };
  if (status === 'ignored') return { color: 'var(--color-text-muted)', backgroundColor: 'var(--color-bg-tertiary)' };
  return { color: '#a16207', backgroundColor: 'rgba(202,138,4,0.11)' };
}

function buildKnowledgeMarkdown(
  feedback: DiagnosisFeedback,
  title: string,
  resolutionNote: string,
): string {
  return [
    `# ${title}`,
    '',
    '## 来源信息',
    `- 设备 SN: ${feedback.sn}`,
    `- 厂区: ${feedback.factory || '未知'}`,
    `- 反馈评价: ${RATING_LABELS[feedback.rating]}`,
    `- 反馈时间: ${formatTime(feedback.created_at)}`,
    `- 反馈记录 ID: ${feedback.id}`,
    '',
    '## 用户反馈',
    feedback.comment?.trim() || '用户未填写文字反馈。',
    '',
    '## 原诊断摘要',
    feedback.diagnosis_context?.trim() || '原诊断未保存摘要。',
    '',
    '## 处理结论',
    resolutionNote.trim() || feedback.resolution_note?.trim() || '尚未填写处理结论。',
    '',
    '## 检索关键词',
    `${feedback.sn}, ${feedback.factory}, ${RATING_LABELS[feedback.rating]}, 诊断反馈, 故障处理`,
    '',
  ].join('\n');
}

export default function FeedbackManagementTab({ factory, factorySites }: FeedbackManagementTabProps) {
  const { toast } = useToast();
  const requestIdRef = useRef(0);
  const knowledgeInputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<DiagnosisFeedback[]>([]);
  const [summary, setSummary] = useState<FeedbackSummary>(EMPTY_SUMMARY);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [rating, setRating] = useState<DiagnosisRating | ''>('');
  const [status, setStatus] = useState<FeedbackStatus | ''>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<DiagnosisFeedback | null>(null);
  const [draftStatus, setDraftStatus] = useState<FeedbackStatus>('pending');
  const [resolutionNote, setResolutionNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [knowledgeFiles, setKnowledgeFiles] = useState<File[]>([]);
  const [knowledgeTitle, setKnowledgeTitle] = useState('');
  const [knowledgeTags, setKnowledgeTags] = useState('');
  const [knowledgeUploading, setKnowledgeUploading] = useState(false);

  const factoryNames = useMemo(
    () => new Map(factorySites.map((site) => [site.factory_id, site.name])),
    [factorySites],
  );

  const loadFeedback = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError('');
    try {
      const response = await diagnosisApi.getFeedbackList({
        factory: factory || undefined,
        rating,
        status,
        keyword: keyword.trim() || undefined,
        page,
        limit: PAGE_SIZE,
      });
      if (requestId !== requestIdRef.current) return;
      if (!response.success || !response.data) {
        setError(response.error || '反馈加载失败');
        setItems([]);
        return;
      }
      setItems(response.data.items);
      setSummary(response.data.summary);
      setTotal(response.data.total);
      setSelected((current) => {
        if (!current) return null;
        return response.data?.items.find((item) => item.id === current.id) ?? current;
      });
    } catch {
      if (requestId === requestIdRef.current) {
        setError('网络错误，无法加载反馈');
        setItems([]);
      }
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [factory, keyword, page, rating, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadFeedback(), keyword ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [loadFeedback, keyword]);

  useEffect(() => {
    setPage(1);
  }, [factory]);

  const openDetail = (item: DiagnosisFeedback) => {
    setSelected(item);
    setDraftStatus(item.status || 'pending');
    setResolutionNote(item.resolution_note || '');
    setKnowledgeFiles([]);
    setKnowledgeTitle(item.knowledge_title || `反馈知识补充 - ${item.sn}`);
    setKnowledgeTags(`反馈补充,${item.factory},${item.sn}`);
  };

  const updateStatus = async () => {
    if (!selected || saving) return;
    setSaving(true);
    try {
      const response = await diagnosisApi.updateFeedback(selected.id, {
        status: draftStatus,
        resolution_note: resolutionNote.trim() || undefined,
      });
      if (!response.success || !response.data) {
        toast('error', response.error || '状态更新失败');
        return;
      }
      setSelected(response.data);
      setItems((current) => current.map((item) => (
        item.id === response.data?.id ? response.data : item
      )));
      toast('success', '反馈状态已更新');
      void loadFeedback();
    } catch {
      toast('error', '网络错误，状态更新失败');
    } finally {
      setSaving(false);
    }
  };

  const uploadFeedbackKnowledge = async () => {
    if (!selected || knowledgeUploading || !knowledgeTitle.trim()) return;
    setKnowledgeUploading(true);
    const uploadedIds: string[] = [];
    const failedFiles: string[] = [];
    const description = `来源于设备 ${selected.sn} 的诊断反馈 ${selected.id}`;
    try {
      const markdown = buildKnowledgeMarkdown(selected, knowledgeTitle.trim(), resolutionNote);
      const safeSn = selected.sn.replace(/[^a-zA-Z0-9_-]/g, '_');
      const knowledgeFile = new File(
        [markdown],
        `feedback_${safeSn}_${selected.id.slice(-6)}.md`,
        { type: 'text/markdown;charset=utf-8' },
      );
      const knowledgeResponse = await knowledgeBaseApi.upload(
        knowledgeFile,
        knowledgeTitle.trim(),
        description,
        knowledgeTags.trim() || undefined,
      );
      if (!knowledgeResponse.success || !knowledgeResponse.data?.id) {
        throw new Error(knowledgeResponse.error || '反馈知识条目上传失败');
      }
      uploadedIds.push(knowledgeResponse.data.id);

      for (const file of knowledgeFiles) {
        try {
          const response = await knowledgeBaseApi.upload(
            file,
            undefined,
            description,
            knowledgeTags.trim() || undefined,
          );
          if (response.success && response.data?.id) uploadedIds.push(response.data.id);
          else failedFiles.push(file.name);
        } catch {
          failedFiles.push(file.name);
        }
      }

      const linkResponse = await diagnosisApi.linkFeedbackKnowledge(selected.id, {
        document_ids: uploadedIds,
        knowledge_title: knowledgeTitle.trim(),
      });
      if (!linkResponse.success || !linkResponse.data) {
        throw new Error(linkResponse.error || '知识文档关联失败');
      }
      setSelected(linkResponse.data);
      setItems((current) => current.map((item) => (
        item.id === linkResponse.data?.id ? linkResponse.data : item
      )));
      setKnowledgeFiles([]);
      if (failedFiles.length) {
        toast('error', `知识条目已补充，${failedFiles.length} 个附件上传失败`);
      } else {
        toast('success', `已补充 ${uploadedIds.length} 份知识文档`);
      }
    } catch (uploadError) {
      toast(
        'error',
        uploadError instanceof Error ? uploadError.message : '补充知识库失败',
      );
    } finally {
      setKnowledgeUploading(false);
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const unresolved = summary.partially + summary.unsolved;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="grid shrink-0 grid-cols-2 border-b sm:grid-cols-4" style={{ borderColor: 'var(--color-border)' }}>
        <button
          type="button"
          onClick={() => { setRating(''); setStatus(''); setPage(1); }}
          className="flex min-h-[82px] items-center gap-3 border-r px-4 text-left sm:px-6"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}
        >
          <MessageSquareText className="h-5 w-5 text-blue-600" />
          <div><div className="text-xl font-bold">{summary.total}</div><div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>反馈总量</div></div>
        </button>
        <button
          type="button"
          onClick={() => { setRating('solved'); setPage(1); }}
          className="flex min-h-[82px] items-center gap-3 border-r px-4 text-left sm:px-6"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}
        >
          <CheckCircle2 className="h-5 w-5 text-emerald-600" />
          <div><div className="text-xl font-bold">{(summary.solved_rate * 100).toFixed(1)}%</div><div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>可解决率</div></div>
        </button>
        <div
          className="flex min-h-[82px] items-center gap-3 border-r border-t px-4 text-left sm:border-t-0 sm:px-6"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}
        >
          <AlertTriangle className="h-5 w-5 text-red-600" />
          <div><div className="text-xl font-bold">{unresolved}</div><div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>需改进反馈</div></div>
        </div>
        <button
          type="button"
          onClick={() => { setStatus('pending'); setPage(1); }}
          className="flex min-h-[82px] items-center gap-3 border-t px-4 text-left sm:border-t-0 sm:px-6"
          style={{ backgroundColor: 'var(--color-bg-secondary)' }}
        >
          <Clock3 className="h-5 w-5 text-amber-600" />
          <div><div className="text-xl font-bold">{summary.pending}</div><div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>待处理</div></div>
        </button>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b px-4 py-3 sm:px-6" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
        <div className="relative min-w-[220px] flex-1 sm:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
          <input
            value={keyword}
            onChange={(event) => { setKeyword(event.target.value); setPage(1); }}
            placeholder="搜索 SN、反馈内容或诊断摘要"
            className="h-9 w-full rounded-md border pl-9 pr-3 text-[12px] outline-none focus:ring-2 focus:ring-blue-500/20"
            style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)', color: 'var(--color-text-primary)' }}
          />
        </div>
        <select
          value={rating}
          onChange={(event) => { setRating(event.target.value as DiagnosisRating | ''); setPage(1); }}
          className="h-9 rounded-md border px-3 text-[12px] outline-none"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)', color: 'var(--color-text-primary)' }}
          aria-label="反馈评价"
        >
          <option value="">全部评价</option>
          <option value="solved">可以解决</option>
          <option value="partially">部分解决</option>
          <option value="unsolved">未解决</option>
        </select>
        <select
          value={status}
          onChange={(event) => { setStatus(event.target.value as FeedbackStatus | ''); setPage(1); }}
          className="h-9 rounded-md border px-3 text-[12px] outline-none"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)', color: 'var(--color-text-primary)' }}
          aria-label="处理状态"
        >
          <option value="">全部状态</option>
          {STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <button
          type="button"
          onClick={() => void loadFeedback()}
          disabled={loading}
          className="flex h-9 w-9 items-center justify-center rounded-md border disabled:opacity-50"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
          title="刷新反馈"
          aria-label="刷新反馈"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full min-w-[1040px] border-collapse text-left text-[12px]">
          <thead className="sticky top-0 z-[1]" style={{ backgroundColor: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)' }}>
            <tr>
              <th className="w-[170px] border-b px-5 py-3 font-semibold" style={{ borderColor: 'var(--color-border)' }}>提交时间</th>
              <th className="w-[160px] border-b px-4 py-3 font-semibold" style={{ borderColor: 'var(--color-border)' }}>设备 SN</th>
              <th className="w-[210px] border-b px-4 py-3 font-semibold" style={{ borderColor: 'var(--color-border)' }}>反馈人</th>
              <th className="w-[130px] border-b px-4 py-3 font-semibold" style={{ borderColor: 'var(--color-border)' }}>厂区</th>
              <th className="w-[110px] border-b px-4 py-3 font-semibold" style={{ borderColor: 'var(--color-border)' }}>评价</th>
              <th className="border-b px-4 py-3 font-semibold" style={{ borderColor: 'var(--color-border)' }}>反馈内容</th>
              <th className="w-[110px] border-b px-4 py-3 font-semibold" style={{ borderColor: 'var(--color-border)' }}>状态</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const statusOption = STATUS_OPTIONS.find((option) => option.value === item.status) ?? STATUS_OPTIONS[0];
              return (
                <tr
                  key={item.id}
                  onClick={() => openDetail(item)}
                  className="cursor-pointer border-b transition-colors hover:bg-blue-500/[0.04]"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  <td className="whitespace-nowrap px-5 py-3.5 font-mono" style={{ color: 'var(--color-text-muted)' }}>{formatTime(item.created_at)}</td>
                  <td className="px-4 py-3.5 font-mono font-semibold text-blue-600">
                    <button type="button" onClick={() => openDetail(item)} className="hover:underline">{item.sn}</button>
                  </td>
                  <td className="max-w-[210px] truncate px-4 py-3.5" title={item.submitter?.email || ''}>
                    {item.submitter?.email || '-'}
                  </td>
                  <td className="px-4 py-3.5">{factoryNames.get(item.factory) || item.factory || '-'}</td>
                  <td className="px-4 py-3.5"><span className="inline-flex rounded px-2 py-1 font-semibold" style={ratingStyle(item.rating)}>{RATING_LABELS[item.rating]}</span></td>
                  <td className="max-w-[420px] truncate px-4 py-3.5" style={{ color: item.comment ? 'var(--color-text-primary)' : 'var(--color-text-muted)' }}>{item.comment || '未填写文字反馈'}</td>
                  <td className="px-4 py-3.5"><span className="inline-flex rounded px-2 py-1 font-semibold" style={statusStyle(item.status)}>{statusOption.label}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {!loading && !error && items.length === 0 && (
          <div className="flex h-56 flex-col items-center justify-center gap-2" style={{ color: 'var(--color-text-muted)' }}>
            <MessageSquareText className="h-7 w-7" />
            <span className="text-[12px]">没有符合条件的反馈</span>
          </div>
        )}
        {loading && (
          <div className="flex h-56 items-center justify-center gap-2 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            <Loader2 className="h-4 w-4 animate-spin" />正在加载反馈
          </div>
        )}
        {error && !loading && (
          <div className="flex h-56 items-center justify-center text-[12px] text-red-600">{error}</div>
        )}
      </div>

      <div className="flex h-12 shrink-0 items-center justify-between border-t px-5 text-[11px]" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
        <span>共 {total} 条，第 {page} / {pageCount} 页</span>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1 || loading} className="flex h-8 w-8 items-center justify-center rounded-md border disabled:opacity-35" style={{ borderColor: 'var(--color-border)' }} aria-label="上一页"><ChevronLeft className="h-4 w-4" /></button>
          <button type="button" onClick={() => setPage((value) => Math.min(pageCount, value + 1))} disabled={page >= pageCount || loading} className="flex h-8 w-8 items-center justify-center rounded-md border disabled:opacity-35" style={{ borderColor: 'var(--color-border)' }} aria-label="下一页"><ChevronRight className="h-4 w-4" /></button>
        </div>
      </div>

      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button type="button" onClick={() => setSelected(null)} className="absolute inset-0 bg-black/35" aria-label="关闭反馈详情" />
          <aside className="relative flex h-full w-full max-w-[520px] flex-col border-l shadow-2xl" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
            <div className="flex h-[60px] shrink-0 items-center justify-between border-b px-5" style={{ borderColor: 'var(--color-border)' }}>
              <div className="min-w-0"><div className="truncate text-[14px] font-bold">{selected.sn}</div><div className="mt-0.5 text-[10px] font-mono" style={{ color: 'var(--color-text-muted)' }}>{formatTime(selected.created_at)}</div></div>
              <button type="button" onClick={() => setSelected(null)} className="flex h-8 w-8 items-center justify-center rounded-md" title="关闭" aria-label="关闭"><X className="h-4 w-4" /></button>
            </div>

            <div className="min-h-0 flex-1 space-y-6 overflow-auto px-5 py-5">
              <div className="grid grid-cols-2 gap-x-5 gap-y-4 text-[12px]">
                <div><div className="mb-1 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>评价</div><span className="inline-flex rounded px-2 py-1 font-semibold" style={ratingStyle(selected.rating)}>{RATING_LABELS[selected.rating]}</span></div>
                <div><div className="mb-1 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>厂区</div><div className="font-medium">{factoryNames.get(selected.factory) || selected.factory || '-'}</div></div>
                <div className="col-span-2"><div className="mb-1 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>反馈人</div><div className="truncate font-medium" title={selected.submitter?.email || ''}>{selected.submitter?.email || '-'}</div></div>
                <div className="col-span-2"><div className="mb-1 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>反馈内容</div><div className="whitespace-pre-wrap leading-5">{selected.comment || '未填写文字反馈'}</div></div>
              </div>

              <section className="border-t pt-5" style={{ borderColor: 'var(--color-border)' }}>
                <h3 className="mb-3 text-[12px] font-bold">诊断摘要</h3>
                <div className="max-h-56 overflow-auto whitespace-pre-wrap rounded-md border p-3 text-[11px] leading-5" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)' }}>
                  {selected.diagnosis_context || '没有保存诊断摘要'}
                </div>
              </section>

              <section className="border-t pt-5" style={{ borderColor: 'var(--color-border)' }}>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h3 className="flex items-center gap-2 text-[12px] font-bold">
                    <BookOpenCheck className="h-4 w-4 text-emerald-600" />快速补充知识库
                  </h3>
                  {(selected.knowledge_document_ids?.length ?? 0) > 0 && (
                    <span className="text-[10px] font-semibold text-emerald-600">
                      已关联 {selected.knowledge_document_ids?.length} 份
                    </span>
                  )}
                </div>
                <div className="mb-3 flex flex-wrap gap-1.5 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                  <span className="rounded border px-2 py-1" style={{ borderColor: 'var(--color-border)' }}>反馈内容</span>
                  <span className="rounded border px-2 py-1" style={{ borderColor: 'var(--color-border)' }}>诊断摘要</span>
                  <span className="rounded border px-2 py-1" style={{ borderColor: 'var(--color-border)' }}>处理备注</span>
                  <span className="rounded border px-2 py-1" style={{ borderColor: 'var(--color-border)' }}>结构化 Markdown</span>
                </div>
                <input
                  value={knowledgeTitle}
                  onChange={(event) => setKnowledgeTitle(event.target.value)}
                  maxLength={200}
                  placeholder="知识标题"
                  className="h-9 w-full rounded-md border px-3 text-[12px] outline-none focus:ring-2 focus:ring-emerald-500/20"
                  style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)', color: 'var(--color-text-primary)' }}
                />
                <input
                  value={knowledgeTags}
                  onChange={(event) => setKnowledgeTags(event.target.value)}
                  placeholder="知识标签，使用逗号分隔"
                  className="mt-2 h-9 w-full rounded-md border px-3 text-[12px] outline-none focus:ring-2 focus:ring-emerald-500/20"
                  style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)', color: 'var(--color-text-primary)' }}
                />
                <input
                  ref={knowledgeInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  accept=".pdf,.docx,.md,.txt,.pptx,.xlsx,.csv,.html,.json,.xml"
                  onChange={(event) => {
                    if (event.target.files) {
                      const selectedFiles = Array.from(event.target.files);
                      const oversizedFiles = selectedFiles.filter(
                        (file) => file.size > MAX_KNOWLEDGE_FILE_SIZE,
                      );
                      const existingKeys = new Set(
                        knowledgeFiles.map((file) => `${file.name}:${file.size}:${file.lastModified}`),
                      );
                      const validFiles = selectedFiles.filter((file) => (
                        file.size <= MAX_KNOWLEDGE_FILE_SIZE
                        && !existingKeys.has(`${file.name}:${file.size}:${file.lastModified}`)
                      ));
                      const availableSlots = MAX_KNOWLEDGE_ATTACHMENTS - knowledgeFiles.length;
                      setKnowledgeFiles([
                        ...knowledgeFiles,
                        ...validFiles.slice(0, availableSlots),
                      ]);
                      if (oversizedFiles.length) {
                        toast('error', `${oversizedFiles.length} 个文件超过 50MB，已跳过`);
                      } else if (validFiles.length > availableSlots) {
                        toast('error', `最多添加 ${MAX_KNOWLEDGE_ATTACHMENTS} 个相关文档`);
                      }
                    }
                    event.target.value = '';
                  }}
                />
                <div className="mt-3 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => knowledgeInputRef.current?.click()}
                    disabled={knowledgeFiles.length >= MAX_KNOWLEDGE_ATTACHMENTS}
                    className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-[11px] font-semibold disabled:opacity-50"
                    style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
                    title={`最多添加 ${MAX_KNOWLEDGE_ATTACHMENTS} 个相关文档`}
                  >
                    <Paperclip className="h-3.5 w-3.5" />添加相关文档
                  </button>
                  <button
                    type="button"
                    onClick={() => void uploadFeedbackKnowledge()}
                    disabled={knowledgeUploading || !knowledgeTitle.trim()}
                    className="inline-flex h-9 flex-1 items-center justify-center gap-2 rounded-md bg-emerald-600 px-3 text-[11px] font-semibold text-white disabled:opacity-50"
                  >
                    {knowledgeUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BookOpenCheck className="h-3.5 w-3.5" />}
                    {knowledgeUploading ? '正在补充知识库' : `一键补充知识库${knowledgeFiles.length ? `（${knowledgeFiles.length + 1} 份）` : ''}`}
                  </button>
                </div>
                {knowledgeFiles.length > 0 && (
                  <div className="mt-3 divide-y rounded-md border" style={{ borderColor: 'var(--color-border)' }}>
                    {knowledgeFiles.map((file, index) => (
                      <div key={`${file.name}-${file.size}-${index}`} className="flex items-center gap-2 px-3 py-2 text-[11px]" style={{ borderColor: 'var(--color-border)' }}>
                        <Paperclip className="h-3.5 w-3.5 shrink-0" style={{ color: 'var(--color-text-muted)' }} />
                        <span className="min-w-0 flex-1 truncate">{file.name}</span>
                        <button type="button" onClick={() => setKnowledgeFiles((current) => current.filter((_, fileIndex) => fileIndex !== index))} className="flex h-6 w-6 items-center justify-center rounded" title="移除附件" aria-label={`移除 ${file.name}`}><X className="h-3.5 w-3.5" /></button>
                      </div>
                    ))}
                  </div>
                )}
                {selected.knowledge_uploaded_at && (
                  <div className="mt-2 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                    最近补充：{formatTime(selected.knowledge_uploaded_at)}
                  </div>
                )}
              </section>

              <section className="border-t pt-5" style={{ borderColor: 'var(--color-border)' }}>
                <h3 className="mb-3 text-[12px] font-bold">处理状态</h3>
                <div className="grid grid-cols-2 gap-2">
                  {STATUS_OPTIONS.map((option) => {
                    const Icon = option.icon;
                    const active = draftStatus === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setDraftStatus(option.value)}
                        className="flex h-9 items-center justify-center gap-2 rounded-md border text-[11px] font-semibold"
                        style={{ borderColor: active ? '#2563eb' : 'var(--color-border)', backgroundColor: active ? 'rgba(37,99,235,0.08)' : 'transparent', color: active ? '#2563eb' : 'var(--color-text-secondary)' }}
                      >
                        <Icon className="h-3.5 w-3.5" />{option.label}
                      </button>
                    );
                  })}
                </div>
                <label className="mt-4 block text-[11px] font-semibold" htmlFor="resolution-note">处理备注</label>
                <textarea
                  id="resolution-note"
                  value={resolutionNote}
                  onChange={(event) => setResolutionNote(event.target.value)}
                  maxLength={2000}
                  rows={5}
                  placeholder="记录修复、知识库补充或模型调整结果"
                  className="mt-2 w-full resize-none rounded-md border p-3 text-[12px] leading-5 outline-none focus:ring-2 focus:ring-blue-500/20"
                  style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)', color: 'var(--color-text-primary)' }}
                />
              </section>
            </div>

            <div className="flex shrink-0 items-center justify-end gap-2 border-t px-5 py-3" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
              <button type="button" onClick={() => setSelected(null)} className="h-9 rounded-md border px-4 text-[12px] font-semibold" style={{ borderColor: 'var(--color-border)' }}>取消</button>
              <button type="button" onClick={() => void updateStatus()} disabled={saving} className="inline-flex h-9 items-center gap-2 rounded-md bg-blue-600 px-4 text-[12px] font-semibold text-white disabled:opacity-50">
                {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}保存处理结果
              </button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
