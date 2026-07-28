import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Database,
  FileArchive,
  RefreshCw,
  Search,
} from 'lucide-react';
import {
  knowledgeBaseApi,
  type RagflowDatasetSummary,
  type RagflowDocument,
} from '../../api/fastapi';

interface ConfiguredKnowledgeDocumentsProps {
  refreshKey: number;
  onChunkCountChange: (count: number) => void;
}

const FORMAT_COLORS: Record<string, string> = {
  pdf: '#f43f5e',
  docx: '#3b82f6',
  doc: '#3b82f6',
  xlsx: '#22c55e',
  xls: '#22c55e',
  csv: '#22c55e',
  md: '#a855f7',
  txt: '#64748b',
  pptx: '#f97316',
  html: '#06b6d4',
  json: '#eab308',
  xml: '#eab308',
};

function formatSize(bytes: number): string {
  if (!bytes) return '-';
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function formatTime(value: string): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function DocumentStatus({ document }: { document: RagflowDocument }) {
  if (document.status === 'parsed' || document.status === 'active') {
    return (
      <span className="inline-flex items-center gap-1.5 text-[12px] font-bold text-emerald-600">
        <CheckCircle2 className="h-3.5 w-3.5" /> 已生效
      </span>
    );
  }
  if (document.status === 'parsing' || document.status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1.5 text-[12px] font-bold" style={{ color: 'var(--color-accent)' }}>
        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
        解析中 {Math.round(document.progress * 100)}%
      </span>
    );
  }
  if (document.status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 text-[12px] font-bold text-red-500">
        <AlertCircle className="h-3.5 w-3.5" /> 解析失败
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-bold" style={{ color: 'var(--color-text-secondary)' }}>
      <Clock className="h-3.5 w-3.5" /> 等待解析
    </span>
  );
}

export default function ConfiguredKnowledgeDocuments({
  refreshKey,
  onChunkCountChange,
}: ConfiguredKnowledgeDocumentsProps) {
  const [documents, setDocuments] = useState<RagflowDocument[]>([]);
  const [datasets, setDatasets] = useState<RagflowDatasetSummary[]>([]);
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [datasetId, setDatasetId] = useState('all');

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await knowledgeBaseApi.listRagflowDocuments();
      if (response.success && response.data) {
        setDocuments(response.data.items);
        setDatasets(response.data.datasets);
        setEnabled(response.data.enabled);
        onChunkCountChange(
          response.data.datasets.reduce((sum, dataset) => sum + dataset.chunk_count, 0),
        );
      } else {
        setError(response.error || '当前知识库集合加载失败');
      }
    } catch {
      setError('当前知识库集合加载失败');
    } finally {
      setLoading(false);
    }
  }, [onChunkCountChange]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments, refreshKey]);

  useEffect(() => {
    const hasPendingDocument = documents.some((document) =>
      ['queued', 'parsing', 'processing'].includes(document.status),
    );
    if (!hasPendingDocument) return;
    const timer = window.setInterval(() => void loadDocuments(), 15000);
    return () => window.clearInterval(timer);
  }, [documents, loadDocuments]);

  const filteredDocuments = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return documents.filter((document) => {
      if (datasetId !== 'all' && document.dataset_id !== datasetId) return false;
      if (!normalizedQuery) return true;
      return `${document.name} ${document.dataset_name}`.toLocaleLowerCase().includes(normalizedQuery);
    });
  }, [datasetId, documents, query]);

  return (
    <section
      className="flex min-h-[340px] flex-col overflow-hidden rounded-lg border shadow-sm"
      style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
    >
      <div className="flex flex-col gap-3 border-b px-5 py-4 lg:flex-row lg:items-center lg:justify-between" style={{ borderColor: 'var(--color-border)' }}>
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-[14px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
            <Database className="h-4 w-4" style={{ color: 'var(--color-accent)' }} />
            当前配置知识库集合
            <span className="font-normal" style={{ color: 'var(--color-text-muted)' }}>({documents.length})</span>
          </h3>
          <p className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
            展示诊断检索实际使用的 RAGFlow 集合及文档，只读同步自当前服务配置。
          </p>
        </div>

        <div className="flex w-full flex-col gap-2 sm:flex-row lg:w-auto">
          <select
            value={datasetId}
            onChange={(event) => setDatasetId(event.target.value)}
            className="h-9 min-w-44 rounded-md border px-3 text-[12px] outline-none"
            style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
            aria-label="筛选知识库集合"
          >
            <option value="all">全部集合 ({documents.length})</option>
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.name} ({dataset.document_count})
              </option>
            ))}
          </select>
          <label className="relative block min-w-0 sm:w-56">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索集合文档"
              className="h-9 w-full rounded-md border pl-8 pr-3 text-[12px] outline-none"
              style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
            />
          </label>
          <button
            type="button"
            onClick={() => void loadDocuments()}
            disabled={loading}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border disabled:opacity-50"
            style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
            title="刷新当前集合"
            aria-label="刷新当前集合"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {datasets.length > 0 && (
        <div className="flex flex-wrap gap-x-5 gap-y-2 border-b px-5 py-3 text-[11px]" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-bg-primary)' }}>
          {datasets.map((dataset) => (
            <span key={dataset.id} className="inline-flex items-center gap-1.5">
              <Database className="h-3.5 w-3.5" style={{ color: 'var(--color-accent)' }} />
              <b style={{ color: 'var(--color-text-primary)' }}>{dataset.name}</b>
              {dataset.document_count} 个文档 · {dataset.chunk_count} 个切片
            </span>
          ))}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto custom-scrollbar">
        {loading && documents.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            <RefreshCw className="h-5 w-5 animate-spin" style={{ color: 'var(--color-accent)' }} />
            正在读取当前集合
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
            <AlertCircle className="mb-3 h-7 w-7 text-red-500" />
            <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{error}</p>
            <button type="button" onClick={() => void loadDocuments()} className="mt-4 inline-flex h-8 items-center gap-2 rounded-md px-3 text-xs font-bold text-white" style={{ backgroundColor: 'var(--color-accent)' }}>
              <RefreshCw className="h-3.5 w-3.5" />重试
            </button>
          </div>
        ) : !enabled ? (
          <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
            <Database className="mb-3 h-8 w-8 opacity-30" style={{ color: 'var(--color-text-secondary)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>尚未配置 RAGFlow 知识库集合</p>
            <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>完成服务地址、密钥和数据集配置后可在此查看文档。</p>
          </div>
        ) : filteredDocuments.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
            <FileArchive className="mb-3 h-8 w-8 opacity-30" style={{ color: 'var(--color-text-secondary)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {query || datasetId !== 'all' ? '没有匹配的集合文档' : '当前集合中暂无文档'}
            </p>
          </div>
        ) : (
          <table className="w-full min-w-[900px] border-collapse text-left text-[12px]">
            <thead className="sticky top-0 z-10 border-b" style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
              <tr>
                <th className="w-[34%] px-5 py-3 font-semibold">文档名称</th>
                <th className="w-[22%] px-5 py-3 font-semibold">所属集合</th>
                <th className="px-5 py-3 font-semibold">文件大小</th>
                <th className="px-5 py-3 font-semibold">切片 / Token</th>
                <th className="px-5 py-3 font-semibold">解析状态</th>
                <th className="px-5 py-3 font-semibold">更新时间</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocuments.map((document) => {
                const formatColor = FORMAT_COLORS[document.format] || '#64748b';
                return (
                  <tr key={`${document.dataset_id}:${document.id}`} className="border-b" style={{ borderColor: 'var(--color-border)' }}>
                    <td className="px-5 py-3.5">
                      <div className="flex min-w-0 items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded border text-[9px] font-bold" style={{ backgroundColor: `${formatColor}18`, borderColor: `${formatColor}40`, color: formatColor }}>
                          {(document.format || 'DOC').toUpperCase().slice(0, 4)}
                        </span>
                        <span className="max-w-[360px] truncate font-semibold" title={document.name} style={{ color: 'var(--color-text-primary)' }}>{document.name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="inline-flex max-w-56 items-center gap-1.5 truncate" title={document.dataset_name} style={{ color: 'var(--color-text-secondary)' }}>
                        <Database className="h-3.5 w-3.5 shrink-0" />{document.dataset_name}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 font-mono" style={{ color: 'var(--color-text-secondary)' }}>{formatSize(document.size_bytes)}</td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--color-text-secondary)' }}>
                      {document.chunk_count} / {new Intl.NumberFormat('zh-CN').format(document.token_count)}
                    </td>
                    <td className="px-5 py-3.5"><DocumentStatus document={document} /></td>
                    <td className="px-5 py-3.5 whitespace-nowrap" style={{ color: 'var(--color-text-secondary)' }}>{formatTime(document.updated_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
