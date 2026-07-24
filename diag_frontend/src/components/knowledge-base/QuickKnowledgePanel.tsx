import { useEffect, useMemo, useState } from 'react';
import { BookPlus, Loader2, X } from 'lucide-react';
import { knowledgeBaseApi } from '../../api/fastapi';
import { useToast } from '../../contexts/ToastContext';

interface QuickKnowledgePanelProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

const KNOWLEDGE_TYPES = [
  { value: 'troubleshooting', label: '故障排查' },
  { value: 'repair_case', label: '维修案例' },
  { value: 'operation_guide', label: '操作规范' },
  { value: 'faq', label: '常见问答' },
] as const;

const VERIFICATION_OPTIONS = [
  { value: 'verified', label: '已验证有效' },
  { value: 'pending', label: '待验证' },
] as const;

const initialForm = {
  title: '',
  knowledgeType: 'troubleshooting',
  verificationStatus: 'verified',
  machineModel: '',
  problem: '',
  rootCause: '',
  solution: '',
  verificationResult: '',
  tags: '',
};

function markdownSection(title: string, content: string): string[] {
  return content.trim() ? [`## ${title}`, '', content.trim(), ''] : [];
}

export default function QuickKnowledgePanel({
  open,
  onClose,
  onCreated,
}: QuickKnowledgePanelProps) {
  const { toast } = useToast();
  const [form, setForm] = useState(initialForm);
  const [saving, setSaving] = useState(false);

  const knowledgeTypeLabel = useMemo(
    () => KNOWLEDGE_TYPES.find((option) => option.value === form.knowledgeType)?.label ?? '故障排查',
    [form.knowledgeType],
  );
  const verificationLabel = useMemo(
    () => VERIFICATION_OPTIONS.find((option) => option.value === form.verificationStatus)?.label ?? '已验证有效',
    [form.verificationStatus],
  );

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !saving) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, open, saving]);

  if (!open) return null;

  const updateField = (field: keyof typeof initialForm, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSave = async () => {
    const title = form.title.trim();
    const problem = form.problem.trim();
    const solution = form.solution.trim();
    if (!title || !problem || !solution || saving) {
      toast('error', '请填写知识标题、问题现象和解决方案');
      return;
    }

    const tags = Array.from(new Set([
      '快速录入',
      knowledgeTypeLabel,
      form.machineModel.trim(),
      ...form.tags.split(/[,，]/).map((tag) => tag.trim()),
    ].filter(Boolean)));
    const markdown = [
      `# ${title}`,
      '',
      '## 知识信息',
      '',
      `- 知识类型：${knowledgeTypeLabel}`,
      `- 验证状态：${verificationLabel}`,
      `- 适用机型：${form.machineModel.trim() || '全部'}`,
      '',
      ...markdownSection('问题现象', problem),
      ...markdownSection('根本原因', form.rootCause),
      ...markdownSection('解决方案', solution),
      ...markdownSection('验证结果', form.verificationResult),
      '## 检索关键词',
      '',
      tags.join('，'),
      '',
    ].join('\n');

    setSaving(true);
    try {
      const safeTitle = title.replace(/[^a-zA-Z0-9_-]/g, '_').replace(/_+/g, '_');
      const file = new File(
        [markdown],
        `quick_knowledge_${safeTitle || Date.now()}.md`,
        { type: 'text/markdown;charset=utf-8' },
      );
      const response = await knowledgeBaseApi.upload(
        file,
        title,
        `快速录入 · ${knowledgeTypeLabel} · ${verificationLabel}`,
        tags.join(','),
        form.knowledgeType as 'troubleshooting' | 'repair_case' | 'operation_guide' | 'faq',
      );
      if (!response.success || !response.data?.id) {
        throw new Error(response.error || '知识录入失败');
      }
      toast('success', '知识已提交，正在进行解析和向量化');
      setForm(initialForm);
      onClose();
      onCreated();
    } catch (error) {
      toast('error', error instanceof Error ? error.message : '知识录入失败');
    } finally {
      setSaving(false);
    }
  };

  const inputClass = 'h-9 w-full rounded-md border px-3 text-[12px] outline-none focus:ring-2 focus:ring-blue-500/20';
  const inputStyle = {
    borderColor: 'var(--color-border)',
    backgroundColor: 'var(--color-bg-secondary)',
    color: 'var(--color-text-primary)',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/45 sm:items-center sm:p-5">
      <button
        type="button"
        onClick={() => { if (!saving) onClose(); }}
        className="absolute inset-0"
        aria-label="关闭快速录入面板"
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="quick-knowledge-title"
        className="relative flex max-h-[92vh] w-full max-w-[720px] flex-col overflow-hidden rounded-t-lg border shadow-2xl sm:rounded-lg"
        style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}
      >
        <header className="flex h-14 shrink-0 items-center justify-between border-b px-5" style={{ borderColor: 'var(--color-border)' }}>
          <div className="flex items-center gap-2">
            <BookPlus className="h-4 w-4 text-blue-600" />
            <h2 id="quick-knowledge-title" className="text-[14px] font-bold">新建知识条目</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="flex h-8 w-8 items-center justify-center rounded-md disabled:opacity-40"
            title="关闭"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5">
          <div>
            <label htmlFor="quick-title" className="mb-1.5 block text-[11px] font-semibold">知识标题 <span className="text-red-500">*</span></label>
            <input id="quick-title" value={form.title} onChange={(event) => updateField('title', event.target.value)} maxLength={200} className={inputClass} style={inputStyle} placeholder="例如：GPU 压力测试超时的排查与处理" autoFocus />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="quick-type" className="mb-1.5 block text-[11px] font-semibold">知识类型</label>
              <select id="quick-type" value={form.knowledgeType} onChange={(event) => updateField('knowledgeType', event.target.value)} className={inputClass} style={inputStyle}>
                {KNOWLEDGE_TYPES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="quick-verification" className="mb-1.5 block text-[11px] font-semibold">验证状态</label>
              <select id="quick-verification" value={form.verificationStatus} onChange={(event) => updateField('verificationStatus', event.target.value)} className={inputClass} style={inputStyle}>
                {VERIFICATION_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="quick-model" className="mb-1.5 block text-[11px] font-semibold">适用机型</label>
            <input id="quick-model" value={form.machineModel} onChange={(event) => updateField('machineModel', event.target.value)} className={inputClass} style={inputStyle} placeholder="不填写表示全部机型" />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="quick-problem" className="mb-1.5 block text-[11px] font-semibold">问题现象 <span className="text-red-500">*</span></label>
              <textarea id="quick-problem" value={form.problem} onChange={(event) => updateField('problem', event.target.value)} rows={7} maxLength={5000} className="w-full resize-y rounded-md border p-3 text-[12px] leading-5 outline-none focus:ring-2 focus:ring-blue-500/20" style={inputStyle} placeholder="粘贴问题描述、错误码或关键日志" />
            </div>
            <div>
              <label htmlFor="quick-solution" className="mb-1.5 block text-[11px] font-semibold">解决方案 <span className="text-red-500">*</span></label>
              <textarea id="quick-solution" value={form.solution} onChange={(event) => updateField('solution', event.target.value)} rows={7} maxLength={8000} className="w-full resize-y rounded-md border p-3 text-[12px] leading-5 outline-none focus:ring-2 focus:ring-blue-500/20" style={inputStyle} placeholder="粘贴处理步骤、命令和注意事项" />
            </div>
          </div>

          <div>
            <label htmlFor="quick-root-cause" className="mb-1.5 block text-[11px] font-semibold">根本原因</label>
            <textarea id="quick-root-cause" value={form.rootCause} onChange={(event) => updateField('rootCause', event.target.value)} rows={3} maxLength={3000} className="w-full resize-y rounded-md border p-3 text-[12px] leading-5 outline-none focus:ring-2 focus:ring-blue-500/20" style={inputStyle} placeholder="可选：填写最终确认的原因和判断依据" />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="quick-result" className="mb-1.5 block text-[11px] font-semibold">验证结果</label>
              <input id="quick-result" value={form.verificationResult} onChange={(event) => updateField('verificationResult', event.target.value)} className={inputClass} style={inputStyle} placeholder="例如：复测 10 次全部通过" />
            </div>
            <div>
              <label htmlFor="quick-tags" className="mb-1.5 block text-[11px] font-semibold">补充标签</label>
              <input id="quick-tags" value={form.tags} onChange={(event) => updateField('tags', event.target.value)} className={inputClass} style={inputStyle} placeholder="错误码、部件、现象，逗号分隔" />
            </div>
          </div>
        </div>

        <footer className="flex shrink-0 items-center justify-end gap-2 border-t px-5 py-3" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
          <button type="button" onClick={onClose} disabled={saving} className="h-9 rounded-md border px-4 text-[12px] font-semibold disabled:opacity-40" style={{ borderColor: 'var(--color-border)' }}>取消</button>
          <button type="button" onClick={() => void handleSave()} disabled={saving || !form.title.trim() || !form.problem.trim() || !form.solution.trim()} className="inline-flex h-9 items-center gap-2 rounded-md bg-blue-600 px-4 text-[12px] font-semibold text-white disabled:opacity-45">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <BookPlus className="h-4 w-4" />}
            {saving ? '正在提交' : '保存到知识库'}
          </button>
        </footer>
      </section>
    </div>
  );
}
