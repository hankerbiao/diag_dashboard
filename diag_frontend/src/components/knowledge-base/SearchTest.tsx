import { useState } from 'react';
import { Search, FileText, ChevronDown, ChevronUp, Loader2, AlertCircle, BookOpen } from 'lucide-react';
import { knowledgeBaseApi, KnowledgeSearchResult } from '../../api/fastapi';

export default function SearchTest() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<KnowledgeSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(true);

  const handleSearch = async () => {
    const q = question.trim();
    if (!q) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await knowledgeBaseApi.search(q);
      if (res.success && res.data) {
        setResult(res.data);
      } else {
        setError(res.error || '检索失败');
      }
    } catch {
      setError('网络请求失败');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const formatSimilarity = (v: number): string => {
    return (v * 100).toFixed(1) + '%';
  };

  return (
    <div
      className="rounded-xl shadow-sm overflow-hidden"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        border: '1px solid var(--color-border)',
      }}
    >
      {/* Header */}
      <div
        className="border-b px-6 py-4 flex items-center gap-3"
        style={{
          backgroundColor: 'var(--color-bg-primary)',
          borderColor: 'var(--color-border)',
        }}
      >
        <BookOpen className="w-5 h-5" style={{ color: 'var(--color-accent)' }} />
        <h2 className="text-base font-bold" style={{ color: 'var(--color-text-primary)' }}>
          知识库检索测试
        </h2>
        <span className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
          验证已上传文档的查询效果
        </span>
      </div>

      <div className="p-6 space-y-5">
        {/* Search Input */}
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入问题，测试知识库检索效果…"
              className="w-full h-11 pl-10 pr-4 text-sm outline-none rounded-lg transition-all shadow-sm"
              style={{
                border: '1px solid var(--color-border)',
                backgroundColor: 'var(--color-bg-primary)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={loading || !question.trim()}
            className="h-11 px-6 text-white text-sm font-bold rounded-lg transition-all flex items-center gap-2 border-0 cursor-pointer disabled:opacity-50 active:scale-95 shrink-0"
            style={{ backgroundColor: 'var(--color-accent)' }}
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            检索
          </button>
        </div>

        {/* Fixed params hint */}
        <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          <span
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full"
            style={{
              backgroundColor: 'var(--color-accent-light)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-secondary)',
            }}
          >
            相似度阈值 0.2
          </span>
          <span
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full"
            style={{
              backgroundColor: 'var(--color-accent-light)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-secondary)',
            }}
          >
            向量相似度权重 0.3
          </span>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 text-xs rounded-md px-3 py-2" style={{ backgroundColor: '#fef2f2', color: '#ef4444', border: '1px solid #fecaca' }}>
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="space-y-3">
            {result.references.length > 0 ? (
              <div>
                <h4 className="text-xs font-bold mb-2 flex items-center gap-2" style={{ color: 'var(--color-text-secondary)' }}>
                  <FileText className="w-3.5 h-3.5" />
                  匹配结果（{result.references.length} 条）
                </h4>
                <div className="space-y-2">
                  {result.references.map((ref, i) => (
                    <div
                      key={ref.chunk_id || i}
                      className="rounded-lg p-4"
                      style={{
                        backgroundColor: 'var(--color-bg-primary)',
                        border: '1px solid var(--color-border)',
                      }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium truncate max-w-[70%]" style={{ color: 'var(--color-text-secondary)' }}>
                          {ref.doc_name || '未知文档'}
                        </span>
                        <span
                          className="text-xs font-bold px-2 py-0.5 rounded"
                          style={{
                            backgroundColor: ref.similarity >= 0.7 ? '#d1fae5' : ref.similarity >= 0.4 ? '#fef3c7' : '#f1f5f9',
                            color: ref.similarity >= 0.7 ? '#065f46' : ref.similarity >= 0.4 ? '#92400e' : '#475569',
                          }}
                        >
                          {formatSimilarity(ref.similarity)}
                        </span>
                      </div>
                      <p className="text-sm leading-relaxed line-clamp-3" style={{ color: 'var(--color-text-primary)' }}>
                        {ref.content}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                未找到匹配的文档内容，请尝试调整问题或上传更多文档
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
