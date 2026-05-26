import { Trash2, FileImage } from 'lucide-react';
import { KnowledgeDoc } from '../../api/fastapi';

interface DocCardProps {
  doc: KnowledgeDoc;
  deleting: boolean;
  onDelete: (id: string) => void;
}

const FORMAT_ICONS: Record<string, string> = {
  pdf: 'PDF',
  docx: 'DOC',
  md: 'MD',
  txt: 'TXT',
  pptx: 'PPT',
  xlsx: 'XLS',
  csv: 'CSV',
  html: 'HTM',
  json: 'JSON',
  xml: 'XML',
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function formatTime(iso: string): string {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diff = now - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return '刚刚';
    if (mins < 60) return `${mins}分钟前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}小时前`;
    if (hours < 48) return '昨天';
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}天前`;
    return d.toLocaleDateString('zh-CN');
  } catch {
    return iso.slice(0, 10);
  }
}

export default function DocCard({ doc, deleting, onDelete }: DocCardProps) {
  const formatLabel = FORMAT_ICONS[doc.format] || doc.format.toUpperCase();

  return (
    <div
      className="rounded-xl border p-4 flex flex-col gap-3 transition-shadow hover:shadow-md"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* Icon + Format Badge */}
      <div className="flex items-start justify-between">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: 'var(--color-accent-light)' }}
        >
          <FileImage className="w-5 h-5" style={{ color: 'var(--color-accent)' }} />
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide"
            style={{ backgroundColor: 'var(--color-bg-primary)', color: 'var(--color-text-secondary)' }}
          >
            {formatLabel}
          </span>
          <button
            onClick={() => onDelete(doc.id)}
            disabled={deleting}
            className="p-1 rounded hover:opacity-70 border-0 bg-transparent cursor-pointer disabled:opacity-40"
            style={{ color: 'var(--color-text-muted)' }}
            title="删除"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Title */}
      <div className="flex-1 min-w-0">
        <h3 className="text-[13px] font-semibold leading-snug line-clamp-2" style={{ color: 'var(--color-text-primary)' }}>
          {doc.title}
        </h3>
        {doc.description && (
          <p className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>
            {doc.description}
          </p>
        )}
      </div>

      {/* Meta */}
      <div className="flex items-center justify-between text-[11px]">
        <span style={{ color: 'var(--color-text-muted)' }}>{formatSize(doc.size_bytes)}</span>
        <div className="flex items-center gap-2">
          {doc.tags.length > 0 && (
            <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)' }}>
              {doc.tags[0]}
            </span>
          )}
          <span style={{ color: 'var(--color-text-muted)' }}>{formatTime(doc.uploaded_at)}</span>
        </div>
      </div>
    </div>
  );
}
