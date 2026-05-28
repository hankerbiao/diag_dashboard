import type { KeyboardEvent } from 'react';
import { Bot, Loader2 } from 'lucide-react';

interface DiagnosisInputProps {
  sn: string;
  onSnChange: (sn: string) => void;
  onDiagnose: () => void;
  loading: boolean;
  onKeyDown: (e: KeyboardEvent<HTMLInputElement>) => void;
}

export default function DiagnosisInput({ sn, onSnChange, onDiagnose, loading, onKeyDown }: DiagnosisInputProps) {
  return (
    <div
      className="h-16 border-b flex items-center px-6 gap-4 shadow-sm z-10 shrink-0"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div
        className="flex-1 max-w-2xl h-10 rounded-full flex items-center px-4 gap-3 transition-all shrink-0 border"
        style={{
          backgroundColor: 'var(--color-bg-primary)',
          borderColor: 'var(--color-border)',
        }}
      >
        <span
          className="text-xs font-bold uppercase tracking-wider select-none shrink-0 border-r pr-3 mr-1"
          style={{
            color: 'var(--color-text-secondary)',
            borderColor: 'var(--color-border)',
          }}
        >
          SN码检索
        </span>
        <input
          type="text"
          value={sn}
          onChange={(e) => onSnChange(e.target.value)}
          onKeyDown={onKeyDown}
          className="bg-transparent text-sm w-full outline-none font-mono shrink"
          style={{
            color: 'var(--color-text-primary)',
          }}
          placeholder="输入产品序列号进行结构化智能分析..."
        />
      </div>
      <button
        onClick={onDiagnose}
        disabled={loading || !sn.trim()}
        className="text-white px-5 py-2 rounded-lg text-sm font-bold shadow-md transition-all flex items-center gap-2 active:scale-[0.98] shrink-0 disabled:opacity-50"
        style={{
          backgroundColor: 'var(--color-accent)',
          boxShadow: '0 2px 10px -2px var(--color-shadow)',
        }}
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bot className="w-4 h-4" />}
        {loading ? '诊断中...' : '大模型推理'}
      </button>
    </div>
  );
}
