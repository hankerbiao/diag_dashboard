import { useState, type KeyboardEvent } from 'react';
import { Search, FileText, Loader2, AlertCircle, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { knowledgeBaseApi, KnowledgeSearchResult } from '../../api/fastapi';

interface SearchTestProps {
  compact?: boolean;
}

// ── 搜索栏 ──
function SearchBar({ question, onChange, onKeyDown, onSearch, loading }: {
  question: string;
  onChange: (v: string) => void;
  onKeyDown: (e: KeyboardEvent<HTMLInputElement>) => void;
  onSearch: () => void;
  loading: boolean;
}) {
  return (
    <div className="flex gap-3">
      <div className="relative flex-1">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
        <input
          type="text"
          value={question}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="输入问题，测试知识库检索效果…"
          className="w-full h-11 pl-10 pr-4 text-sm outline-none rounded-lg transition-all shadow-sm"
          style={{ border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg-primary)', color: 'var(--color-text-primary)' }}
        />
      </div>
      <button onClick={onSearch} disabled={loading || !question.trim()}
        className="h-11 px-6 text-white text-sm font-bold rounded-lg transition-all flex items-center gap-2 border-0 cursor-pointer disabled:opacity-50 active:scale-95 shrink-0"
        style={{ backgroundColor: 'var(--color-accent)' }}>
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
        检索
      </button>
    </div>
  );
}

// ── 参数标签 ──
function ParamTags() {
  const tagStyle = { backgroundColor: 'var(--color-accent-light)', border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' };
  return (
    <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full" style={tagStyle}>相似度阈值 0.2</span>
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full" style={tagStyle}>向量相似度权重 0.3</span>
    </div>
  );
}

// ── 结果列表 ──
function ResultList({ result, expandedIdx, onToggle }: {
  result: KnowledgeSearchResult;
  expandedIdx: number | null;
  onToggle: (idx: number) => void;
}) {
  const formatSimilarity = (v: number) => (v * 100).toFixed(1) + '%';

  if (result.references.length === 0) {
    return <div className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>未找到匹配的文档内容</div>;
  }

  return (
    <div>
      <h4 className="text-xs font-bold mb-2 flex items-center gap-2" style={{ color: 'var(--color-text-secondary)' }}>
        <FileText className="w-3.5 h-3.5" />匹配结果（{result.references.length} 条）
      </h4>
      <div className="space-y-2">
        {result.references.map((ref, i) => (
          <div key={ref.chunk_id || i}
            className="rounded-lg p-4 cursor-pointer transition-colors"
            style={{ backgroundColor: 'var(--color-bg-primary)', border: '1px solid var(--color-border)' }}
            onClick={() => onToggle(i)}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium truncate max-w-[65%]" style={{ color: 'var(--color-text-secondary)' }}>{ref.doc_name || '未知文档'}</span>
              <span className="text-xs font-bold px-2 py-0.5 rounded shrink-0"
                style={{
                  backgroundColor: ref.similarity >= 0.7 ? 'rgba(34,197,94,0.15)' : ref.similarity >= 0.4 ? 'rgba(234,179,8,0.15)' : 'rgba(100,116,139,0.15)',
                  color: ref.similarity >= 0.7 ? '#22c55e' : ref.similarity >= 0.4 ? '#eab308' : 'var(--color-text-secondary)',
                }}>
                {formatSimilarity(ref.similarity)}
              </span>
            </div>
            <p className={`text-sm leading-relaxed ${expandedIdx === i ? '' : 'line-clamp-3'}`} style={{ color: 'var(--color-text-primary)' }}>{ref.content}</p>
            <div className="flex items-center justify-center mt-1.5 text-[11px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
              {expandedIdx === i ? <><ChevronUp className="w-3 h-3" />收起</> : <><ChevronDown className="w-3 h-3" />展开</>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SearchTest({ compact }: SearchTestProps) {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<KnowledgeSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const handleSearch = async () => {
    const q = question.trim();
    if (!q) return;
    setLoading(true);
    setError('');
    setResult(null);
    setExpandedIdx(null);
    try {
      const res = await knowledgeBaseApi.search(q);
      if (res.success && res.data) setResult(res.data);
      else setError(res.error || '检索失败');
    } catch { setError('网络请求失败'); }
    finally { setLoading(false); }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch();
  };

  const body = (
    <div className={compact ? 'p-5 space-y-4' : 'p-6 space-y-5'}>
      <SearchBar question={question} onChange={setQuestion} onKeyDown={handleKeyDown} onSearch={handleSearch} loading={loading} />
      <ParamTags />
      {error && (
        <div className="flex items-center gap-2 text-xs rounded-md px-3 py-2" style={{ backgroundColor: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />{error}
        </div>
      )}
      {result && <ResultList result={result} expandedIdx={expandedIdx} onToggle={(i) => setExpandedIdx(expandedIdx === i ? null : i)} />}
    </div>
  );

  if (compact) return body;

  return (
    <div className="rounded-xl shadow-sm overflow-hidden" style={{ backgroundColor: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
      <div className="border-b px-6 py-4 flex items-center gap-3" style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}>
        <BookOpen className="w-5 h-5" style={{ color: 'var(--color-accent)' }} />
        <h2 className="text-base font-bold" style={{ color: 'var(--color-text-primary)' }}>知识库检索测试</h2>
        <span className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>验证已上传文档的查询效果</span>
      </div>
      {body}
    </div>
  );
}
