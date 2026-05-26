import { useState, useCallback, useEffect } from 'react';
import {
  AlertCircle, Database, FileArchive, Search,
  CheckCircle2, Clock, RefreshCw, Trash2,
} from 'lucide-react';
import { knowledgeBaseApi, KnowledgeDoc } from '../../api/fastapi';
import UploadZone from './UploadZone';
import DocDetailDrawer from './DocDetailDrawer';

interface DocDisplay {
  id: string;
  name: string;
  format: string;
  sizeLabel: string;
  uploadTime: string;
  tags: string[];
  status: 'active' | 'processing' | 'queued' | 'failed';
}

const FORMAT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  pdf:  { bg: 'bg-rose-50', text: 'text-rose-600', border: 'border-rose-100' },
  docx: { bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-100' },
  doc:  { bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-100' },
  xlsx: { bg: 'bg-green-50', text: 'text-green-600', border: 'border-green-100' },
  xls:  { bg: 'bg-green-50', text: 'text-green-600', border: 'border-green-100' },
  csv:  { bg: 'bg-green-50', text: 'text-green-600', border: 'border-green-100' },
  md:   { bg: 'bg-purple-50', text: 'text-purple-600', border: 'border-purple-100' },
  txt:  { bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-100' },
  pptx: { bg: 'bg-orange-50', text: 'text-orange-600', border: 'border-orange-100' },
  html: { bg: 'bg-cyan-50', text: 'text-cyan-600', border: 'border-cyan-100' },
  json: { bg: 'bg-yellow-50', text: 'text-yellow-600', border: 'border-yellow-100' },
  xml:  { bg: 'bg-yellow-50', text: 'text-yellow-600', border: 'border-yellow-100' },
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

  // 获取真实切片数
  useEffect(() => {
    knowledgeBaseApi.getRagflowStatus().then((res) => {
      if (res.success && res.data?.dataset) {
        setChunkCount(res.data.dataset.chunk_count);
      }
    });
  }, []);

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

  const refreshChunks = () => {
    knowledgeBaseApi.getRagflowStatus().then((res) => {
      if (res.success && res.data?.dataset) {
        setChunkCount(res.data.dataset.chunk_count);
      }
    });
  };

  const handleUploaded = () => {
    setPage(1);
    loadDocs(1);
    refreshChunks();
  };

  const handleDelete = async (docId: string) => {
    try {
      await knowledgeBaseApi.delete(docId);
      setPage(1);
      loadDocs(1);
      refreshChunks();
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
  };

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
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50">
      {/* ═══ Header Info ═══ */}
      <div className="bg-white border-b border-slate-200 px-6 py-5 shrink-0 z-10 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-600" />
            RAG 领域知识库录入 (所有厂区共用)
          </h2>
          <p className="text-[13px] text-slate-500 mt-1 max-w-2xl leading-relaxed">
            上传常见格式的历史维修文档、SOP教程、机身图解及日志规范。所有文件将自动通过 OCR 与文档切分引擎处理，并向量化入库，随后将作为大模型深度诊断参考。
          </p>
        </div>
        <div className="flex shrink-0">
          <div className="bg-emerald-50 border border-emerald-100 rounded-lg px-4 py-2 text-center shadow-sm">
            <div className="text-[11px] text-emerald-600 font-bold uppercase tracking-wider mb-0.5">有效知识切片</div>
            <div className="text-[15px] font-bold text-emerald-800">
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
          <div className="flex items-center gap-2 text-xs rounded-md px-3 py-2 bg-red-50 text-red-600 border border-red-100">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            {error}
          </div>
        )}

        {/* ─── Document List ─── */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col min-h-[300px]">
          {/* List Header + Filters */}
          <div className="border-b border-slate-100 px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
            <h3 className="text-[14px] font-bold text-slate-800 flex items-center gap-2 shrink-0">
              <FileArchive className="w-4 h-4 text-slate-500" />
              库中语料清单
              <span className="text-[12px] font-normal text-slate-400 ml-1">({total})</span>
            </h3>

            <div className="flex items-center gap-3">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索文档名称…"
                  className="w-52 h-8 pl-8 pr-3 rounded-md text-[12px] outline-none border border-slate-200 bg-slate-50 text-slate-700 placeholder:text-slate-400 focus:border-blue-300 focus:bg-white transition-colors"
                />
              </div>

              {/* Filter tabs */}
              <div className="flex bg-slate-100 p-0.5 rounded-lg border border-slate-200/60 shadow-inner">
                {(['all', 'active', 'processing'] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => { setActiveFilter(f); setPage(1); }}
                    className={`px-4 py-1.5 text-[12px] font-bold rounded flex items-center gap-1.5 transition-all ${
                      activeFilter === f
                        ? 'bg-white text-slate-800 shadow-sm border border-slate-200/60'
                        : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
                    }`}
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
                <thead className="bg-[#fafafa] text-slate-500 font-semibold sticky top-0 border-b border-slate-200">
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
                      <td colSpan={6} className="text-center py-12 text-slate-400 text-[13px]">
                        {search || activeFilter !== 'all' ? '没有找到匹配的文档，请调整筛选条件' : '知识库中还没有文档，请上传参考资料'}
                      </td>
                    </tr>
                  ) : (
                    displayDocs.map((doc) => {
                      const fc = FORMAT_COLORS[doc.format] || { bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-100' };

                      return (
                        <tr
                          key={doc.id}
                          className="hover:bg-slate-50/80 transition-colors border-b border-slate-100 group cursor-pointer"
                          onClick={() => {
                            const original = docs.find((d) => d.id === doc.id);
                            if (original) handleDocClick(original);
                          }}
                        >
                          {/* Name */}
                          <td className="px-5 py-3.5 text-slate-800 font-medium">
                            <div className="flex items-center gap-3">
                              <div className={`w-8 h-8 rounded shrink-0 flex items-center justify-center text-[10px] font-bold ${fc.bg} ${fc.text} ${fc.border} border`}>
                                {doc.format.toUpperCase()}
                              </div>
                              <span className="truncate max-w-[320px]" title={doc.name}>{doc.name}</span>
                            </div>
                          </td>

                          {/* Tags */}
                          <td className="px-5 py-3.5">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {doc.tags.length > 0 ? doc.tags.map((tag) => (
                                <span key={tag} className="bg-slate-100 border border-slate-200 text-slate-600 px-2 py-0.5 rounded text-[11px]">
                                  {tag}
                                </span>
                              )) : (
                                <span className="text-slate-300 text-[11px]">-</span>
                              )}
                            </div>
                          </td>

                          {/* Size */}
                          <td className="px-5 py-3.5 text-slate-500 font-mono text-[12px]">{doc.sizeLabel}</td>

                          {/* Time */}
                          <td className="px-5 py-3.5 text-slate-500 text-[12px]">{doc.uploadTime}</td>

                          {/* Status */}
                          <td className="px-5 py-3.5">
                            {doc.status === 'active' && (
                              <span className="inline-flex items-center gap-1.5 font-bold text-emerald-600 text-[12px]">
                                <CheckCircle2 className="w-3.5 h-3.5" /> 知识入库生效
                              </span>
                            )}
                            {doc.status === 'processing' && (
                              <span className="inline-flex items-center gap-1.5 font-bold text-blue-600 text-[12px]">
                                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> 切片与向量化中
                              </span>
                            )}
                            {doc.status === 'queued' && (
                              <span className="inline-flex items-center gap-1.5 font-bold text-slate-500 text-[12px]">
                                <Clock className="w-3.5 h-3.5" /> 等待调度...
                              </span>
                            )}
                            {doc.status === 'failed' && (
                              <span className="inline-flex items-center gap-1.5 font-bold text-red-500 text-[12px]">
                                <AlertCircle className="w-3.5 h-3.5" /> 解析失败
                              </span>
                            )}
                          </td>

                          {/* Actions */}
                          <td className="px-6 py-3.5 text-center" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => handleDelete(doc.id)}
                              className="text-slate-400 hover:text-rose-500 transition-colors p-1.5 rounded-md hover:bg-rose-50"
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
            <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100">
              <span className="text-[12px] text-slate-400">
                共 {total} 条，第 {page}/{totalPages} 页
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 text-[12px] rounded-md border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50 transition-colors cursor-pointer disabled:cursor-default"
                >
                  上一页
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 text-[12px] rounded-md border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50 transition-colors cursor-pointer disabled:cursor-default"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Detail Drawer */}
      <DocDetailDrawer
        doc={detailDoc}
        onClose={handleDrawerClose}
        onDeleted={handleDrawerDeleted}
        onUpdated={() => loadDocs(page)}
      />
    </div>
  );
}
