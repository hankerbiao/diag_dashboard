import { useState, useEffect, useCallback } from 'react';
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  FileText,
  Trash2,
  RotateCcw,
  Pencil,
  Search,
  X,
  Plus,
  Cpu,
} from 'lucide-react';
import { settingsApi } from '../../api/fastapi';
import type { LogExtractionPrompt } from '../../api/fastapi';

interface LogExtractionPromptsProps {
  onErrorMessage?: (msg: string) => void;
  onSuccessMessage?: (msg: string) => void;
}

interface EditorState {
  model: string;
  system_prompt: string;
  user_template: string;
  is_default: boolean;
  is_new: boolean;
}

const DEFAULT_SYSTEM = '你是一个日志解析专家。你的任务是分析一段设备测试日志，提取其中的关键错误信息。只提取与故障相关的行和上下文，忽略 INFO/DEBUG 等非关键信息，保留错误行的上下文（前后各 2-3 行），对同类错误进行归并。';
const DEFAULT_TEMPLATE = '以下是设备测试日志的原始内容（共 {total_lines} 行）。请分析日志，按 JSON 返回结果：errors 数组（severity/line_number/line_content/context_before/context_after/analysis）、summary、has_critical_errors、suggested_root_cause。日志内容：\n```\n{log_text}\n```';

const panelStyle = {
  backgroundColor: 'var(--color-bg-secondary)',
  borderColor: 'var(--color-border)',
};

const inputStyle = {
  borderColor: 'var(--color-border)',
  backgroundColor: 'var(--color-bg-primary)',
  color: 'var(--color-text-primary)',
};

const labelStyle = { color: 'var(--color-text-primary)' };
const mutedStyle = { color: 'var(--color-text-muted)' };

function PromptStatus({ configured }: { configured: boolean }) {
  return (
    <span
      className="inline-flex w-fit items-center rounded-full px-2 py-0.5 text-[11px] font-bold"
      style={{
        color: configured ? '#047857' : '#b45309',
        backgroundColor: configured ? '#d1fae5' : '#fef3c7',
        border: `1px solid ${configured ? '#34d399' : '#f59e0b'}`,
      }}
    >
      {configured ? '已配置' : '使用默认'}
    </span>
  );
}

export default function LogExtractionPrompts({ onErrorMessage, onSuccessMessage }: LogExtractionPromptsProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [prompts, setPrompts] = useState<LogExtractionPrompt[]>([]);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [fallbackFeedback, setFallbackFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const editorOpen = editor !== null;

  const notify = useCallback((type: 'success' | 'error', message: string) => {
    if (type === 'success') {
      onSuccessMessage?.(message);
    } else {
      onErrorMessage?.(message);
    }
    if ((type === 'success' && !onSuccessMessage) || (type === 'error' && !onErrorMessage)) {
      setFallbackFeedback({ type, message });
      setTimeout(() => setFallbackFeedback(null), 3000);
    }
  }, [onErrorMessage, onSuccessMessage]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [mResp, pResp] = await Promise.all([
        settingsApi.getMachineModels(),
        settingsApi.getExtractionPrompts(),
      ]);
      if (mResp.success) setModels(mResp.data.models || []);
      if (pResp.success) setPrompts(pResp.data.prompts || []);
    } catch {
      notify('error', '加载机型 / Prompt 配置失败');
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (!editorOpen) return;

    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setEditor(null);
    };

    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [editorOpen]);

  const defaultPrompt = prompts.find((prompt) => prompt.is_default);

  const promptSeed = () => ({
    system_prompt: defaultPrompt?.system_prompt || DEFAULT_SYSTEM,
    user_template: defaultPrompt?.user_template || DEFAULT_TEMPLATE,
  });

  const openDefault = () => {
    const seed = promptSeed();
    setEditorError(null);
    setEditor({
      model: 'default',
      is_default: true,
      is_new: false,
      system_prompt: seed.system_prompt,
      user_template: seed.user_template,
    });
  };

  const openNew = () => {
    const seed = promptSeed();
    setEditorError(null);
    setEditor({
      model: '',
      is_default: false,
      is_new: true,
      system_prompt: seed.system_prompt,
      user_template: seed.user_template,
    });
  };

  const openModel = (model: string) => {
    const existing = prompts.find((prompt) => !prompt.is_default && prompt.model === model);
    const seed = promptSeed();
    setEditorError(null);
    setEditor({
      model,
      is_default: false,
      is_new: false,
      system_prompt: existing?.system_prompt || seed.system_prompt,
      user_template: existing?.user_template || seed.user_template,
    });
  };

  const handleSave = async () => {
    if (!editor) return;

    const model = editor.model.trim();
    if (!model) {
      setEditorError('请输入机型名称');
      return;
    }
    if (!editor.is_default && model.toLowerCase() === 'default') {
      setEditorError('default 为系统保留名称，请使用其他机型名称');
      return;
    }
    if (!editor.system_prompt.trim() || !editor.user_template.trim()) {
      setEditorError('System Prompt 和 User Prompt 模板不能为空');
      return;
    }
    if (!editor.user_template.includes('{log_text}')) {
      setEditorError('User Prompt 模板必须包含 {log_text}（日志内容占位符），否则模型收不到日志，提取结果为空');
      return;
    }

    const duplicate = prompts.find(
      (prompt) => !prompt.is_default && prompt.model.toLowerCase() === model.toLowerCase(),
    );
    if (editor.is_new && duplicate) {
      openModel(duplicate.model);
      setEditorError(`机型「${duplicate.model}」已有 Prompt，请直接编辑`);
      return;
    }

    setEditorError(null);
    setSaving(true);
    try {
      const resp = await settingsApi.upsertExtractionPrompt({
        model,
        system_prompt: editor.system_prompt,
        user_template: editor.user_template,
      });
      if (resp.success) {
        notify('success', `提取 Prompt「${model}」已保存`);
        setEditor(null);
        await loadAll();
      } else {
        setEditorError(resp.error || '保存失败');
        notify('error', resp.error || '保存失败');
      }
    } catch {
      setEditorError('网络错误，保存失败');
      notify('error', '网络错误，保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (model: string) => {
    if (!window.confirm(`确认删除机型「${model}」的提取 Prompt？`)) return;
    try {
      const resp = await settingsApi.deleteExtractionPrompt(model);
      if (resp.success) {
        notify('success', `提取 Prompt「${model}」已删除`);
        await loadAll();
      } else {
        notify('error', resp.error || '删除失败');
      }
    } catch {
      notify('error', '网络错误，删除失败');
    }
  };

  const promptModels = prompts.filter((prompt) => !prompt.is_default).map((prompt) => prompt.model);
  const allModels = Array.from(new Set([...models, ...promptModels])).sort((a, b) =>
    a.localeCompare(b, 'zh-CN', { numeric: true }),
  );
  const configuredModels = new Set(promptModels);
  const filteredModels = allModels.filter((model) => model.toLowerCase().includes(query.trim().toLowerCase()));
  const configuredCount = allModels.filter((model) => configuredModels.has(model)).length;
  const defaultConfigured = Boolean(defaultPrompt);
  const pendingCount = Math.max(allModels.length - configuredCount, 0);

  if (loading) {
    return (
      <section className="rounded-lg border p-6" style={panelStyle}>
        <div className="flex items-center justify-center gap-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
          <Loader2 className="h-5 w-5 animate-spin" />
          加载 Prompt 配置中...
        </div>
      </section>
    );
  }

  return (
    <>
      <section className="overflow-hidden rounded-lg border" style={panelStyle}>
        <div className="flex flex-col gap-4 border-b px-4 py-4 sm:px-5 md:flex-row md:items-center md:justify-between" style={{ borderColor: 'var(--color-border)' }}>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 shrink-0" style={{ color: 'var(--color-accent)' }} />
              <h2 className="text-base font-bold" style={labelStyle}>
                机型 Prompt 管理
              </h2>
            </div>
            <p className="mt-1 max-w-2xl text-xs leading-5" style={mutedStyle}>
              为不同机型设置日志提取规则；未单独配置的机型自动使用通用模板。
            </p>
          </div>
          <button
            type="button"
            onClick={openNew}
            className="inline-flex h-10 w-full shrink-0 items-center justify-center gap-2 rounded-lg px-4 text-sm font-bold text-white transition active:scale-[0.98] sm:w-auto"
            style={{ backgroundColor: 'var(--color-accent)' }}
          >
            <Plus className="h-4 w-4" />
            添加机型 Prompt
          </button>
        </div>

        <div className="flex flex-col gap-3 border-b px-4 py-3 sm:px-5 lg:flex-row lg:items-center lg:justify-between" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
            <span>机型总数 <strong style={labelStyle}>{allModels.length}</strong></span>
            <span>已配置 <strong style={{ color: '#047857' }}>{configuredCount}</strong></span>
            <span>使用默认 <strong style={{ color: pendingCount > 0 ? '#b45309' : 'var(--color-text-primary)' }}>{pendingCount}</strong></span>
          </div>
          <div className="relative w-full lg:w-72">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-secondary)' }} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-10 w-full rounded-lg border pl-9 pr-9 text-sm outline-none transition focus:border-blue-400"
              style={inputStyle}
              placeholder="搜索机型"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md"
                style={{ color: 'var(--color-text-secondary)' }}
                aria-label="清空搜索"
                title="清空搜索"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-3 border-b px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5" style={{ borderColor: 'var(--color-border)' }}>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-bold" style={labelStyle}>通用 Prompt 模板</span>
              <span className="rounded-full border px-2 py-0.5 text-[11px] font-bold" style={{ color: 'var(--color-accent)', borderColor: 'var(--color-accent)', backgroundColor: 'var(--color-accent-light)' }}>
                {defaultConfigured ? '已保存' : '系统内置'}
              </span>
            </div>
            <p className="mt-1 text-xs leading-5" style={mutedStyle}>
              作为未配置机型的回退规则，也是新增机型 Prompt 的初始内容。
            </p>
          </div>
          <button
            type="button"
            onClick={openDefault}
            className="inline-flex h-9 w-full shrink-0 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-bold sm:w-auto"
            style={{ color: 'var(--color-accent)', borderColor: 'var(--color-accent)', backgroundColor: 'var(--color-bg-secondary)' }}
          >
            <RotateCcw className="h-4 w-4" />
            编辑通用模板
          </button>
        </div>

        <div>
          <div className="hidden grid-cols-[minmax(0,1fr)_112px_152px] gap-4 border-b px-5 py-2 text-[11px] font-bold sm:grid" style={{ color: 'var(--color-text-muted)', borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
            <span>机型</span>
            <span>Prompt 状态</span>
            <span className="text-right">操作</span>
          </div>
          <div className="max-h-[420px] divide-y overflow-y-auto custom-scrollbar" style={{ borderColor: 'var(--color-border)' }}>
            {allModels.length === 0 ? (
              <div className="flex flex-col items-center px-4 py-10 text-center">
                <Cpu className="mb-3 h-8 w-8" style={{ color: 'var(--color-text-muted)' }} />
                <p className="text-sm font-semibold" style={labelStyle}>还没有机型配置</p>
                <p className="mt-1 text-xs" style={mutedStyle}>点击“添加机型 Prompt”创建第一条配置。</p>
              </div>
            ) : filteredModels.length === 0 ? (
              <div className="px-4 py-10 text-center text-sm" style={mutedStyle}>
                没有匹配的机型。
              </div>
            ) : (
              filteredModels.map((modelName) => {
                const configured = configuredModels.has(modelName);
                return (
                  <div key={modelName} className="flex flex-col gap-3 px-4 py-4 sm:grid sm:grid-cols-[minmax(0,1fr)_112px_152px] sm:items-center sm:gap-4 sm:px-5">
                    <div className="min-w-0">
                      <span className="break-all text-sm font-semibold" style={labelStyle}>{modelName}</span>
                    </div>
                    <PromptStatus configured={configured} />
                    <div className="flex items-center gap-2 sm:justify-end">
                      <button
                        type="button"
                        onClick={() => openModel(modelName)}
                        title={configured ? '编辑 Prompt' : '为该机型设置 Prompt'}
                        className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 text-xs font-bold sm:flex-none"
                        style={{ color: 'var(--color-accent)', borderColor: 'var(--color-border)' }}
                      >
                        <Pencil className="h-4 w-4" />
                        {configured ? '编辑' : '配置'}
                      </button>
                      {configured && (
                        <button
                          type="button"
                          onClick={() => handleDelete(modelName)}
                          title="删除 Prompt"
                          aria-label={`删除机型 ${modelName} 的 Prompt`}
                          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border"
                          style={{ color: 'var(--color-error, #dc2626)', borderColor: 'var(--color-border)' }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {fallbackFeedback && (
          <div
            className="m-4 flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium sm:m-5"
            style={{
              backgroundColor: fallbackFeedback.type === 'success' ? 'var(--color-success-bg, #ecfdf5)' : 'var(--color-error-bg, #fef2f2)',
              color: fallbackFeedback.type === 'success' ? 'var(--color-success, #059669)' : 'var(--color-error, #dc2626)',
              border: `1px solid ${fallbackFeedback.type === 'success' ? 'var(--color-success, #059669)' : 'var(--color-error, #dc2626)'}44`,
            }}
          >
            {fallbackFeedback.type === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            {fallbackFeedback.message}
          </div>
        )}
      </section>

      {editor && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-6"
          onMouseDown={() => setEditor(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="prompt-editor-title"
            className="flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-t-lg border shadow-2xl sm:rounded-lg"
            style={panelStyle}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b px-4 py-4 sm:px-6" style={{ borderColor: 'var(--color-border)' }}>
              <div className="min-w-0">
                <h3 id="prompt-editor-title" className="text-base font-bold" style={labelStyle}>
                  {editor.is_default ? '编辑通用 Prompt 模板' : editor.is_new ? '添加机型 Prompt' : '编辑机型 Prompt'}
                </h3>
                <p className="mt-1 text-xs leading-5" style={mutedStyle}>
                  {editor.is_default ? '修改后将作为所有未配置机型的默认规则。' : 'Prompt 会在该机型的错误日志提取阶段自动生效。'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEditor(null)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                style={{ color: 'var(--color-text-secondary)' }}
                aria-label="关闭编辑器"
                title="关闭"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-4 custom-scrollbar sm:p-6">
              {!editor.is_default && (
                <label className="block max-w-xl space-y-2">
                  <span className="text-xs font-bold" style={labelStyle}>机型名称</span>
                  <span className="relative block">
                    <Cpu className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-secondary)' }} />
                    <input
                      autoFocus={editor.is_new}
                      value={editor.model}
                      onChange={(event) => {
                        setEditorError(null);
                        setEditor({ ...editor, model: event.target.value });
                      }}
                      disabled={!editor.is_new}
                      className="h-11 w-full rounded-lg border pl-9 pr-3 text-sm outline-none transition focus:border-blue-400 disabled:cursor-not-allowed disabled:opacity-70"
                      style={inputStyle}
                      placeholder="例如：GServer-4280G4"
                    />
                  </span>
                </label>
              )}

              <div className={`${editor.is_default ? '' : 'mt-6'} grid min-w-0 gap-5 xl:grid-cols-2`}>
                <label className="block min-w-0 space-y-2">
                  <span className="text-xs font-bold" style={labelStyle}>System Prompt</span>
                  <textarea
                    value={editor.system_prompt}
                    onChange={(event) => setEditor({ ...editor, system_prompt: event.target.value })}
                    rows={12}
                    className="min-h-64 w-full resize-y rounded-lg border px-3 py-3 text-xs font-mono leading-5 outline-none transition focus:border-blue-400"
                    style={inputStyle}
                  />
                </label>
                <label className="block min-w-0 space-y-2">
                  <span className="text-xs font-bold" style={labelStyle}>User Prompt 模板</span>
                  <textarea
                    value={editor.user_template}
                    onChange={(event) => setEditor({ ...editor, user_template: event.target.value })}
                    rows={12}
                    className="min-h-64 w-full resize-y rounded-lg border px-3 py-3 text-xs font-mono leading-5 outline-none transition focus:border-blue-400"
                    style={inputStyle}
                  />
                </label>
              </div>

              <div className="mt-3 space-y-2 rounded-lg border px-3 py-2.5 text-[11px] leading-5" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
                <p style={mutedStyle}>
                  <code className="font-mono font-bold" style={{ color: 'var(--color-accent)' }}>{'{log_text}'}</code>
                  {' '}为日志切片内容占位符，<span className="font-bold" style={{ color: 'var(--color-warning, #b45309)' }}>必须包含</span>
                  —— 缺失时模型收不到日志，提取结果为空。
                </p>
                <p style={mutedStyle}>
                  其他可用变量：{'{total_lines}'}、{'{total_chars}'}、{'{matched_lines}'}、{'{paragraphs}'}、{'{segment_index}'}、{'{segment_count}'}、{'{segment_start_line}'}、{'{segment_end_line}'}
                </p>
              </div>
            </div>

            <div className="border-t px-4 py-4 sm:px-6" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
              {editorError && (
                <div className="mb-3 flex items-start gap-2 text-xs font-semibold" style={{ color: 'var(--color-error, #dc2626)' }}>
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{editorError}</span>
                </div>
              )}
              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => setEditor(null)}
                  className="h-10 rounded-lg border px-4 text-sm font-bold"
                  style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-bg-secondary)' }}
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-bold text-white disabled:opacity-60"
                  style={{ backgroundColor: 'var(--color-accent)' }}
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  {saving ? '保存中...' : '保存 Prompt'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
