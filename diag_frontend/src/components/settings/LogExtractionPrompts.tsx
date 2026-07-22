import { useState, useEffect, useCallback } from 'react';
import { Loader2, CheckCircle2, AlertCircle, FileText, Trash2, RotateCcw, Pencil, Search, X } from 'lucide-react';
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
      className="rounded-full px-2 py-0.5 text-[11px] font-bold"
      style={{
        color: configured ? '#047857' : '#b45309',
        backgroundColor: configured ? '#d1fae5' : '#fef3c7',
        border: `1px solid ${configured ? '#34d399' : '#f59e0b'}`,
      }}
    >
      {configured ? '已设置' : '待设置'}
    </span>
  );
}

export default function LogExtractionPrompts({ onErrorMessage, onSuccessMessage }: LogExtractionPromptsProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [prompts, setPrompts] = useState<LogExtractionPrompt[]>([]);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [query, setQuery] = useState('');
  const [fallbackFeedback, setFallbackFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

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

  useEffect(() => { loadAll(); }, [loadAll]);

  const openDefault = () => {
    const def = prompts.find((p) => p.is_default);
    setEditor({
      model: 'default',
      is_default: true,
      system_prompt: def?.system_prompt || DEFAULT_SYSTEM,
      user_template: def?.user_template || DEFAULT_TEMPLATE,
    });
  };

  const openModel = (model: string) => {
    const existing = prompts.find((p) => !p.is_default && p.model === model);
    const template = prompts.find((p) => p.is_default);
    setEditor({
      model,
      is_default: false,
      system_prompt: existing?.system_prompt || template?.system_prompt || DEFAULT_SYSTEM,
      user_template: existing?.user_template || template?.user_template || DEFAULT_TEMPLATE,
    });
  };

  const handleSave = async () => {
    if (!editor) return;
    setSaving(true);
    try {
      const resp = await settingsApi.upsertExtractionPrompt({
        model: editor.model,
        system_prompt: editor.system_prompt,
        user_template: editor.user_template,
      });
      if (resp.success) {
        notify('success', `提取 Prompt「${editor.model}」已保存`);
        setEditor(null);
        await loadAll();
      } else {
        notify('error', resp.error || '保存失败');
      }
    } catch {
      notify('error', '网络错误，保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (model: string) => {
    if (!window.confirm(`确认删除机型「${model}」的提取 Prompt？删除后该机型会变为「待设置」。`)) return;
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

  const configuredModels = new Set(prompts.filter((p) => !p.is_default).map((p) => p.model));
  const defaultConfigured = prompts.some((p) => p.is_default);
  const filteredModels = models.filter((model) => model.toLowerCase().includes(query.trim().toLowerCase()));
  const configuredCount = models.filter((model) => configuredModels.has(model)).length;
  const pendingCount = Math.max(models.length - configuredCount, 0);

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
    <section className="overflow-hidden rounded-lg border" style={panelStyle}>
      <div className="flex flex-col gap-3 border-b px-5 py-4 lg:flex-row lg:items-center lg:justify-between" style={{ borderColor: 'var(--color-border)' }}>
        <div>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5" style={{ color: 'var(--color-accent)' }} />
            <h2 className="text-base font-bold" style={labelStyle}>
              错误日志提取 Prompt（按机型配置）
            </h2>
          </div>
          <p className="mt-1 text-xs leading-5" style={mutedStyle}>
            每个机型都需要单独保存一套 Prompt，确保日志提取规则和设备特征一致。
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:flex-row lg:w-auto">
          <div className="flex h-10 shrink-0 items-center rounded-lg border px-3 text-xs font-bold" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-bg-primary)' }}>
            已设置 {configuredCount}/{models.length}
          </div>
          <div className="flex h-10 shrink-0 items-center rounded-lg border px-3 text-xs font-bold" style={{ borderColor: pendingCount > 0 ? '#f59e0b' : 'var(--color-border)', color: pendingCount > 0 ? '#b45309' : '#047857', backgroundColor: pendingCount > 0 ? '#fef3c7' : '#d1fae5' }}>
            待设置 {pendingCount}
          </div>
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-secondary)' }} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-10 w-full rounded-lg border pl-9 pr-9 text-sm outline-none"
              style={inputStyle}
              placeholder="搜索机型"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md"
                style={{ color: 'var(--color-text-secondary)' }}
                aria-label="清空搜索"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="p-5">
        <div className="mb-4 flex flex-col gap-3 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold" style={labelStyle}>通用初始模板</span>
              <span
                className="rounded-full border px-2 py-0.5 text-[11px] font-bold"
                style={{ color: 'var(--color-accent)', borderColor: 'var(--color-accent)', backgroundColor: 'var(--color-accent-light)' }}
              >
                {defaultConfigured ? '已保存' : '系统内置'}
              </span>
            </div>
            <p className="mt-1 text-xs" style={mutedStyle}>
              只作为新机型 Prompt 的起始内容；保存后仍需逐个机型确认。
            </p>
          </div>
          <button
            type="button"
            onClick={openDefault}
            className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-bold"
            style={{ color: 'var(--color-accent)', borderColor: 'var(--color-accent)', backgroundColor: 'var(--color-bg-secondary)' }}
          >
            <RotateCcw className="h-4 w-4" />
            编辑模板
          </button>
        </div>

        {models.length === 0 ? (
          <div className="rounded-lg border border-dashed px-4 py-8 text-center text-sm" style={{ color: 'var(--color-text-muted)', borderColor: 'var(--color-border)' }}>
            暂无已同步机型。
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
            <div className="grid grid-cols-[minmax(0,1fr)_92px_124px] border-b px-4 py-2 text-[11px] font-bold" style={{ color: 'var(--color-text-muted)', borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
              <span>机型</span>
              <span>状态</span>
              <span className="text-right">操作</span>
            </div>
            <div className="max-h-[360px] divide-y overflow-y-auto custom-scrollbar" style={{ borderColor: 'var(--color-border)' }}>
              {filteredModels.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm" style={mutedStyle}>
                  没有匹配的机型。
                </div>
              ) : (
                filteredModels.map((modelName) => {
                  const configured = configuredModels.has(modelName);
                  return (
                    <div
                      key={modelName}
                      className="grid grid-cols-[minmax(0,1fr)_92px_124px] items-center gap-3 px-4 py-3"
                      style={{ borderColor: 'var(--color-border)' }}
                    >
                      <span className="truncate text-sm font-semibold" style={labelStyle}>
                        {modelName}
                      </span>
                      <PromptStatus configured={configured} />
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => openModel(modelName)}
                          title="编辑 Prompt"
                          className="inline-flex h-8 items-center justify-center gap-1 rounded-md border px-2 text-xs font-bold"
                          style={{ color: 'var(--color-accent)', borderColor: 'var(--color-border)' }}
                        >
                          <Pencil className="h-4 w-4" />
                          {configured ? '编辑' : '设置'}
                        </button>
                        {configured && (
                          <button
                            type="button"
                            onClick={() => handleDelete(modelName)}
                            title="删除 Prompt"
                            className="flex h-8 w-8 items-center justify-center rounded-md border"
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
        )}

        {editor && (
          <div className="mt-5 rounded-lg border" style={{ borderColor: 'var(--color-accent)', backgroundColor: 'var(--color-bg-primary)' }}>
            <div className="flex items-center justify-between gap-3 border-b px-4 py-3" style={{ borderColor: 'var(--color-border)' }}>
              <div className="min-w-0">
                <h3 className="truncate text-sm font-bold" style={labelStyle}>
                  {editor.is_default ? '编辑通用初始模板' : `设置机型 Prompt：${editor.model}`}
                </h3>
                <p className="mt-1 text-xs" style={mutedStyle}>
                  支持 {'{log_text}'}、{'{total_lines}'}、{'{total_chars}'}、{'{matched_lines}'}、{'{paragraphs}'}。
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEditor(null)}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md"
                style={{ color: 'var(--color-text-secondary)' }}
                aria-label="关闭编辑器"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid gap-4 p-4 lg:grid-cols-2">
              <label className="block space-y-2">
                <span className="text-xs font-bold" style={labelStyle}>System Prompt</span>
                <textarea
                  value={editor.system_prompt}
                  onChange={(e) => setEditor({ ...editor, system_prompt: e.target.value })}
                  rows={8}
                  className="min-h-44 w-full resize-y rounded-lg border px-3 py-2 text-xs font-mono leading-5 outline-none"
                  style={{ ...inputStyle, backgroundColor: 'var(--color-bg-secondary)' }}
                />
              </label>
              <label className="block space-y-2">
                <span className="text-xs font-bold" style={labelStyle}>User Prompt 模板</span>
                <textarea
                  value={editor.user_template}
                  onChange={(e) => setEditor({ ...editor, user_template: e.target.value })}
                  rows={8}
                  className="min-h-44 w-full resize-y rounded-lg border px-3 py-2 text-xs font-mono leading-5 outline-none"
                  style={{ ...inputStyle, backgroundColor: 'var(--color-bg-secondary)' }}
                />
              </label>
            </div>

            <div className="flex justify-end gap-3 border-t px-4 py-3" style={{ borderColor: 'var(--color-border)' }}>
              <button
                type="button"
                onClick={() => setEditor(null)}
                className="h-9 rounded-lg border px-4 text-sm font-bold"
                style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-bg-secondary)' }}
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-lg px-4 text-sm font-bold text-white disabled:opacity-60"
                style={{ backgroundColor: 'var(--color-accent)' }}
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                {saving ? '保存中...' : '保存 Prompt'}
              </button>
            </div>
          </div>
        )}

        {fallbackFeedback && (
          <div
            className="mt-4 flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium"
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
      </div>
    </section>
  );
}
