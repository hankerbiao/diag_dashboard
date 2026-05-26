import { useState } from 'react';
import type { ReactNode, CSSProperties } from 'react';
import { X, FileText, Save, Trash2, CheckCircle, Clock, RefreshCw, AlertCircle } from 'lucide-react';
import { KnowledgeDoc, knowledgeBaseApi } from '../../api/fastapi';

interface DocDetailDrawerProps {
  doc: KnowledgeDoc | null;
  onClose: () => void;
  onDeleted: (id: string) => void;
  onUpdated: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function formatDate(iso: string): string {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso.slice(0, 16).replace('T', ' ');
  }
}

const STATUS_CONFIG: Record<string, { icon: ReactNode; label: string; color: string }> = {
  active:    { icon: <CheckCircle className="w-4 h-4" />,   label: '知识入库生效', color: '#22c55e' },
  parsed:   { icon: <CheckCircle className="w-4 h-4" />,    label: '知识入库生效',  color: '#22c55e' },
  processing: { icon: <RefreshCw className="w-4 h-4" />,    label: '切片与向量化中', color: '#3b82f6' },
  parsing:  { icon: <RefreshCw className="w-4 h-4" />,      label: '切片与向量化中', color: '#3b82f6' },
  queued:   { icon: <Clock className="w-4 h-4" />,          label: '等待调度...',   color: '#94a3b8' },
  ready:    { icon: <Clock className="w-4 h-4" />,          label: '等待调度...',   color: '#94a3b8' },
  failed:   { icon: <AlertCircle className="w-4 h-4" />,    label: '解析失败',     color: '#ef4444' },
};

export default function DocDetailDrawer({ doc, onClose, onDeleted, onUpdated }: DocDetailDrawerProps) {
  const [title, setTitle] = useState(doc?.title ?? '');
  const [description, setDescription] = useState(doc?.description ?? '');
  const [tagsInput, setTagsInput] = useState(doc?.tags?.join(', ') ?? '');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  if (!doc) return null;

  // Sync internal state when the document changes
  if (doc.title !== title && !saving) {
    setTitle(doc.title);
    setDescription(doc.description ?? '');
    setTagsInput(doc.tags?.join(', ') ?? '');
  }

  const status = STATUS_CONFIG[doc.status] || STATUS_CONFIG.parsed;

  const handleSave = async () => {
    setSaving(true);
    try {
      const tags = tagsInput.split(',').map((t) => t.trim()).filter(Boolean);
      await knowledgeBaseApi.update(doc.id, { title, description, tags });
      onUpdated();
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await knowledgeBaseApi.delete(doc.id);
      onDeleted(doc.id);
    } catch {
      // silent
    } finally {
      setDeleting(false);
    }
  };

  const inputStyle: CSSProperties = {
    padding: '6px 10px',
    fontSize: 13,
    borderRadius: 6,
    outline: 'none',
    border: '1px solid var(--color-border)',
    backgroundColor: 'var(--color-bg-primary)',
    color: 'var(--color-text-primary)',
    width: '100%',
  };

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-30"
        style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className="fixed top-0 right-0 h-full w-96 z-40 shadow-2xl overflow-y-auto"
        style={{ backgroundColor: 'var(--color-bg-primary)', borderLeft: '1px solid var(--color-border)' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 border-b sticky top-0 z-10"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}
        >
          <h3 className="text-sm font-bold" style={{ color: 'var(--color-text-primary)' }}>
            文档详情
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:opacity-70 border-0 bg-transparent cursor-pointer"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Icon + format */}
          <div className="flex items-center gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ backgroundColor: 'var(--color-accent-light)' }}
            >
              <FileText className="w-6 h-6" style={{ color: 'var(--color-accent)' }} />
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                {doc.format.toUpperCase()}
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
                {doc.id}
              </p>
            </div>
          </div>

          {/* Editable fields */}
          <div className="space-y-3">
            <div>
              <label className="text-[11px] font-medium block mb-1" style={{ color: 'var(--color-text-secondary)' }}>标题</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                style={inputStyle}
              />
            </div>
            <div>
              <label className="text-[11px] font-medium block mb-1" style={{ color: 'var(--color-text-secondary)' }}>描述</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                style={{ ...inputStyle, resize: 'none' }}
              />
            </div>
            <div>
              <label className="text-[11px] font-medium block mb-1" style={{ color: 'var(--color-text-secondary)' }}>标签（逗号分隔）</label>
              <input
                type="text"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                style={inputStyle}
                placeholder="标签1, 标签2, ..."
              />
              {doc.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {doc.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 rounded text-[11px]"
                      style={{ backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)' }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* File info */}
          <div className="rounded-lg p-3 space-y-1.5" style={{ backgroundColor: 'var(--color-bg-secondary)' }}>
            <p className="text-[11px] font-medium mb-2" style={{ color: 'var(--color-text-secondary)' }}>文件信息</p>
            <InfoRow label="格式" value={doc.format.toUpperCase()} />
            <InfoRow label="大小" value={formatSize(doc.size_bytes)} />
            <InfoRow label="上传时间" value={formatDate(doc.uploaded_at)} />
          </div>

          {/* AI Status */}
          <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--color-bg-secondary)' }}>
            <p className="text-[11px] font-medium mb-2" style={{ color: 'var(--color-text-secondary)' }}>AI 学习状态</p>
            <div className="flex items-center gap-2 text-[13px]" style={{ color: status.color }}>
              {status.icon}
              <span>{status.label}</span>
            </div>
            {(doc.status === 'parsed' || doc.status === 'active') && (
              <p className="text-[11px] mt-1.5" style={{ color: 'var(--color-text-muted)' }}>
                已完成解析，内容可供 AI 参考
              </p>
            )}
            {(doc.status === 'parsing' || doc.status === 'processing') && (
              <p className="text-[11px] mt-1.5" style={{ color: 'var(--color-text-muted)' }}>
                文档正在解析中，稍后即可使用
              </p>
            )}
            {(doc.status === 'queued' || doc.status === 'ready') && (
              <p className="text-[11px] mt-1.5" style={{ color: 'var(--color-text-muted)' }}>
                文档等待调度，将在队列中依次处理
              </p>
            )}
            {doc.status === 'failed' && (
              <p className="text-[11px] mt-1.5" style={{ color: 'var(--color-text-muted)' }}>
                解析失败，可尝试重新解析
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 h-9 text-white text-[13px] font-bold rounded-lg flex items-center justify-center gap-2 border-0 cursor-pointer disabled:opacity-50"
              style={{ backgroundColor: 'var(--color-accent)' }}
            >
              {saving ? (
                <div className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: '#fff', borderTopColor: 'transparent' }} />
              ) : (
                <Save className="w-4 h-4" />
              )}
              保存修改
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="h-9 px-4 text-[13px] font-bold rounded-lg flex items-center gap-2 border cursor-pointer disabled:opacity-50"
              style={{
                borderColor: 'var(--color-border)',
                color: '#ef4444',
                backgroundColor: 'transparent',
              }}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-[12px]">
      <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
      <span style={{ color: 'var(--color-text-primary)' }}>{value}</span>
    </div>
  );
}
