import { useState, useCallback, useEffect } from 'react';
import {
  AlertCircle, Database, FileArchive, Search,
  CheckCircle2, Clock, RefreshCw, Trash2, X, BookOpen,
} from 'lucide-react';
import SupportHint from '../common/SupportHint';
import { knowledgeBaseApi, KnowledgeDoc } from '../../api/fastapi';
import UploadZone from './UploadZone';
import DocDetailDrawer from './DocDetailDrawer';
import SearchTest from './SearchTest';
import ConfiguredKnowledgeDocuments from './ConfiguredKnowledgeDocuments';

interface DocDisplay {
  id: string;
  name: string;
  format: string;
  sizeLabel: string;
  uploadTime: string;
  tags: string[];
  status: 'active' | 'processing' | 'queued' | 'failed';
}

const FORMAT_COLORS: Record<string, string> = {
  pdf:  '#f43f5e',
  docx: '#3b82f6',
  doc:  '#3b82f6',
  xlsx: '#22c55e',
  xls:  '#22c55e',
  csv:  '#22c55e',
  md:   '#a855f7',
  txt:  '#64748b',
  pptx: '#f97316',
  html: '#06b6d4',
  json: '#eab308',
  xml:  '#eab308',
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

function mapStatus(s: string): DocDisplay['status'] {
  if (s === 'parsed' || s === 'active') return 'active';
  if (s === 'parsing' || s === 'processing') return 'processing';
  if (s === 'queued' || s === 'ready') return 'queued';
  return 'failed';
}

export default function KnowledgeBaseTab() {
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [detailDoc, setDetailDoc] = useState<KnowledgeDoc | null>(null);
  const [chunkCount, setChunkCount] = useState(0);
  const [showSearch, setShowSearch] = useState(false);
  const [listView, setListView] = useState<'configured' | 'uploads'>('configured');
  const [ragflowRefreshKey, setRagflowRefreshKey] = useState(0);

  const limit = 20;

  const loadDocs = useCallback(async (p: number) => {
    setLoading(true);
    setError('');
    try {
      const res = await knowledgeBaseApi.list({
        search: search || undefined,
        page: p,
        limit,
        sync_status: true,
      });
      if (res.success && res.data) {
        setDocs(res.data.items);
        setTotal(res.data.total);
      }
    } catch {
      setError('加载文档列表失败');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    setPage(1);
    loadDocs(1);
  }, [search]);

  useEffect(() => {
    if (page !== 1) loadDocs(page);
  }, [page]);

  // 自动轮询：当有文档处于解析中/排队中时定期刷新状态
  useEffect(() => {
    const hasPending = docs.some((d) => d.status === 'parsing' || d.status === 'queued');
    if (!hasPending) return;
    const timer = setInterval(() => loadDocs(page), 15000);
    return () => clearInterval(timer);
  }, [docs, page, loadDocs]);

  const handleUploaded = () => {
    setPage(1);
    loadDocs(1);
    setListView('configured');
    setRagflowRefreshKey((key) => key + 1);
  };

  const handleDelete = async (docId: string) => {
    try {
      await knowledgeBaseApi.delete(docId);
      setPage(1);
      loadDocs(1);
      setRagflowRefreshKey((key) => key + 1);
    } catch {
      setError('删除失败');
    }
  };

  const handleDocClick = (doc: KnowledgeDoc) => setDetailDoc(doc);
  const handleDrawerClose = () => setDetailDoc(null);
  const handleDrawerDeleted = () => {
    setDetailDoc(null);
    setPage(1);
    loadDocs(1);
    setRagflowRefreshKey((key) => key + 1);
  };

  const handleChunkCountChange = useCallback((count: number) => {
    setChunkCount(count);
  }, []);

  const totalPages = Math.ceil(total / limit);

  // Filter and sort docs
  const displayDocs: DocDisplay[] = docs
    .filter((d) => {
      if (activeFilter === 'all') return true;
      return mapStatus(d.status) === activeFilter;
    })
    .map((d) => ({
      id: d.id,
      name: d.title,
      format: d.format,
      sizeLabel: formatSize(d.size_bytes),
      uploadTime: formatTime(d.uploaded_at),
      tags: d.tags,
      status: mapStatus(d.status),
    }));

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden" style={{ backgroundColor: 'var(--color-bg-primary)' }}>
      {/* ═══ Header Info ═══ */}
      <div className="border-b px-6 py-5 shrink-0 z-10 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between"
        style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
        <div>
          <h2 className="text-lg font-bold flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
            <Database className="w-5 h-5" style={{ color: 'var(--color-accent)' }} />
            海光DCU | RAG 领域知识库录入 (所有厂区共用)
          </h2>
          <p className="text-[13px] mt-1 max-w-2xl leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
            上传常见格式的历史维修文档、SOP教程、机身图解及日志规范。所有文件将自动通过 OCR 与文档切分引擎处理，并向量化入库，部署于海光DCU服务器上作为大模型深度诊断参考。
          </p>
          <SupportHint compact className="mt-2" />
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <button onClick={() => setShowSearch(true)}
            className="h-10 px-4 rounded-lg text-sm font-bold flex items-center gap-2 transition-colors hover:brightness-95"
            style={{ backgroundColor: 'var(--color-accent)', color: '#fff' }}>
            <Search className="w-4 h-4" />知识库检索
          </button>
          <div className="rounded-lg px-4 py-2 text-center shadow-sm"
            style={{ backgroundColor: 'var(--color-bg-primary)', border: '1px solid var(--color-border)' }}>
            <div className="text-[11px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--color-accent)' }}>有效知识切片</div>
            <div className="text-[15px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
              {chunkCount}
            </div>
          </div>
        </div>
      </div>

      {/* ═══ Scrollable Content ═══ */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-5 flex flex-col gap-5">

        {/* ─── Upload Area ─── */}
        <UploadZone onUploaded={handleUploaded} />

        {/* ─── Error ─── */}
        {error && (
          <div className="flex items-center gap-2 text-xs rounded-md px-3 py-2" style={{ backgroundColor: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            {error}
          </div>
        )}

        <div className="flex border-b" style={{ borderColor: 'var(--color-border)' }} role="tablist" aria-label="知识库文档视图">
          <button
            type="button"
            role="tab"
            aria-selected={listView === 'configured'}
            onClick={() => setListView('configured')}
            className="relative px-4 py-2.5 text-[13px] font-bold"
            style={{ color: listView === 'configured' ? 'var(--color-accent)' : 'var(--color-text-secondary)' }}
          >
            当前知识库集合
            {listView === 'configured' && <span className="absolute inset-x-0 bottom-[-1px] h-0.5" style={{ backgroundColor: 'var(--color-accent)' }} />}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={listView === 'uploads'}
            onClick={() => setListView('uploads')}
            className="relative px-4 py-2.5 text-[13px] font-bold"
            style={{ color: listView === 'uploads' ? 'var(--color-accent)' : 'var(--color-text-secondary)' }}
          >
            WeaveEye 上传记录 ({total})
            {listView === 'uploads' && <span className="absolute inset-x-0 bottom-[-1px] h-0.5" style={{ backgroundColor: 'var(--color-accent)' }} />}
          </button>
        </div>

        {/* ─── Document List ─── */}
        {listView === 'uploads' ? (
        <div className="rounded-xl shadow-sm border flex flex-col min-h-[300px]"
          style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
          {/* List Header + Filters */}
          <div className="border-b px-5 py-4 flex items-center justify-between gap-4 flex-wrap"
            style={{ borderColor: 'var(--color-border)' }}>
            <h3 className="text-[14px] font-bold flex items-center gap-2 shrink-0" style={{ color: 'var(--color-text-primary)' }}>
              <FileArchive className="w-4 h-4" style={{ color: 'var(--color-text-secondary)' }} />
              库中语料清单
              <span className="text-[12px] font-normal ml-1" style={{ color: 'var(--color-text-muted)' }}>({total})</span>
            </h3>

            <div className="flex items-center gap-3">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索文档名称…"
                  className="w-52 h-8 pl-8 pr-3 rounded-md text-[12px] outline-none border transition-colors"
                  style={{
                    borderColor: 'var(--color-border)',
                    backgroundColor: 'var(--color-bg-primary)',
                    color: 'var(--color-text-primary)',
                  }}
                />
              </div>

              {/* Filter tabs */}
              <div className="flex p-0.5 rounded-lg border shadow-inner"
                style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}>
                {(['all', 'active', 'processing'] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => { setActiveFilter(f); setPage(1); }}
                    className={`px-4 py-1.5 text-[12px] font-bold rounded flex items-center gap-1.5 transition-all ${
                      activeFilter === f
                        ? 'shadow-sm border'
                        : 'hover:opacity-80'
                    }`}
                    style={activeFilter === f
                      ? { backgroundColor: 'var(--color-bg-secondary)', color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }
                      : { color: 'var(--color-text-secondary)' }
                    }
                  >
                    {f === 'all' && '全部'}
                    {f === 'active' && '已生效'}
                    {f === 'processing' && '解析中向量化'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="flex-1 overflow-x-auto min-h-0 custom-scrollbar">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <table className="w-full text-left border-collapse text-[13px] whitespace-nowrap min-w-max">
                <thead style={{ backgroundColor: 'var(--color-bg-primary)', color: 'var(--color-text-secondary)' }}
                  className="font-semibold sticky top-0 border-b"
                >
                  <tr>
                    <th className="px-5 py-3.5 tracking-wider w-[40%]">知识文档名称</th>
                    <th className="px-5 py-3.5 tracking-wider">上传标签分类</th>
                    <th className="px-5 py-3.5 tracking-wider w-24">文件大小</th>
                    <th className="px-5 py-3.5 tracking-wider">上传时间</th>
                    <th className="px-5 py-3.5 tracking-wider w-32">解析状态</th>
                    <th className="px-6 py-3.5 tracking-wider w-20 text-center">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {displayDocs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="text-center py-12 text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
                        {search || activeFilter !== 'all' ? '没有找到匹配的文档，请调整筛选条件' : '知识库中还没有文档，请上传参考资料'}
                      </td>
                    </tr>
                  ) : (
                    displayDocs.map((doc) => {
                      const fc = FORMAT_COLORS[doc.format] || '#64748b';

                      return (
                        <tr
                          key={doc.id}
                          className="hover:opacity-80 transition-colors border-b group cursor-pointer"
                          style={{ borderColor: 'var(--color-border)' }}
                          onClick={() => {
                            const original = docs.find((d) => d.id === doc.id);
                            if (original) handleDocClick(original);
                          }}
                        >
                          {/* Name */}
                          <td className="px-5 py-3.5 font-medium" style={{ color: 'var(--color-text-primary)' }}>
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded shrink-0 flex items-center justify-center text-[10px] font-bold border"
                                style={{ backgroundColor: `${fc}20`, color: fc, borderColor: `${fc}40` }}>
                                {doc.format.toUpperCase()}
                              </div>
                              <span className="truncate max-w-[320px]" title={doc.name}>{doc.name}</span>
                            </div>
                          </td>

                          {/* Tags */}
                          <td className="px-5 py-3.5">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {doc.tags.length > 0 ? doc.tags.map((tag) => (
                                <span key={tag} className="px-2 py-0.5 rounded text-[11px] border"
                                  style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
                                  {tag}
                                </span>
                              )) : (
                                <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>-</span>
                              )}
                            </div>
                          </td>

                          {/* Size */}
                          <td className="px-5 py-3.5 font-mono text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>{doc.sizeLabel}</td>

                          {/* Time */}
                          <td className="px-5 py-3.5 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>{doc.uploadTime}</td>

                          {/* Status */}
                          <td className="px-5 py-3.5">
                            {doc.status === 'active' && (
                              <span className="inline-flex items-center gap-1.5 font-bold text-[12px]" style={{ color: '#22c55e' }}>
                                <CheckCircle2 className="w-3.5 h-3.5" /> 知识入库生效
                              </span>
                            )}
                            {doc.status === 'processing' && (
                              <span className="inline-flex items-center gap-1.5 font-bold text-[12px]" style={{ color: 'var(--color-accent)' }}>
                                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> 切片与向量化中
                              </span>
                            )}
                            {doc.status === 'queued' && (
                              <span className="inline-flex items-center gap-1.5 font-bold text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
                                <Clock className="w-3.5 h-3.5" /> 等待调度...
                              </span>
                            )}
                            {doc.status === 'failed' && (
                              <span className="inline-flex items-center gap-1.5 font-bold text-[12px]" style={{ color: '#ef4444' }}>
                                <AlertCircle className="w-3.5 h-3.5" /> 解析失败
                              </span>
                            )}
                          </td>

                          {/* Actions */}
                          <td className="px-6 py-3.5 text-center" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => handleDelete(doc.id)}
                              className="hover:text-rose-500 transition-colors p-1.5 rounded-md hover:bg-rose-500/10"
                              style={{ color: 'var(--color-text-muted)' }}
                              title="删除语料"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-5 py-3 border-t" style={{ borderColor: 'var(--color-border)' }}>
              <span className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                共 {total} 条，第 {page}/{totalPages} 页
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 text-[12px] rounded-md border disabled:opacity-40 hover:opacity-80 transition-colors cursor-pointer disabled:cursor-default"
                  style={{
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-primary)',
                    backgroundColor: 'var(--color-bg-primary)',
                  }}
                >
                  上一页
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 text-[12px] rounded-md border disabled:opacity-40 hover:opacity-80 transition-colors cursor-pointer disabled:cursor-default"
                  style={{
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-primary)',
                    backgroundColor: 'var(--color-bg-primary)',
                  }}
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
        ) : (
          <ConfiguredKnowledgeDocuments
            refreshKey={ragflowRefreshKey}
            onChunkCountChange={handleChunkCountChange}
          />
        )}
      </div>

      {/* Detail Drawer */}
      <DocDetailDrawer
        doc={detailDoc}
        onClose={handleDrawerClose}
        onDeleted={handleDrawerDeleted}
        onUpdated={() => loadDocs(page)}
      />

      {/* Search Modal */}
      {showSearch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
          onClick={() => setShowSearch(false)}>
          <div className="rounded-2xl border shadow-2xl w-[680px] max-h-[85vh] flex flex-col overflow-hidden"
            style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}
            onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b shrink-0"
              style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
              <div className="flex items-center gap-3">
                <BookOpen className="w-5 h-5" style={{ color: 'var(--color-accent)' }} />
                <h2 className="text-base font-bold" style={{ color: 'var(--color-text-primary)' }}>知识库检索</h2>
                <span className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>验证已上传文档的查询效果</span>
              </div>
              <button onClick={() => setShowSearch(false)} className="w-7 h-7 rounded-lg flex items-center justify-center hover:opacity-70"
                style={{ color: 'var(--color-text-muted)' }}>
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <SearchTest compact />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
