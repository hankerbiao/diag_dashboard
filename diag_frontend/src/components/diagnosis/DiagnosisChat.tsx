import { useState, useEffect, useRef, type KeyboardEvent } from 'react';
import { ChevronUp, Loader2, Bot, User } from 'lucide-react';

export interface ChatMessage { role: 'user' | 'assistant'; content: string }

interface DiagnosisChatProps {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (question: string) => void;
}

export default function DiagnosisChat({ messages, loading, onSend }: DiagnosisChatProps) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput('');
    onSend(q);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className="flex h-[220px] min-h-0 w-full shrink-0 flex-col border-t sm:h-[260px] xl:h-auto xl:w-[380px] xl:border-l xl:border-t-0"
      style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}
    >
      <div
        className="shrink-0 border-b px-4 py-3 text-[12px] font-bold"
        style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
      >
        AI 诊断对话
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar min-h-0">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-[13px] text-center" style={{ color: 'var(--color-text-muted)' }}>
              诊断完成后，可在此追问细节<br />例如"解释一下第三项建议的原理"
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
              style={{
                backgroundColor: m.role === 'assistant' ? 'var(--color-accent-light)' : 'var(--color-bg-secondary)',
                border: `1px solid ${m.role === 'assistant' ? 'transparent' : 'var(--color-border)'}`,
              }}
            >
              {m.role === 'assistant'
                ? <Bot className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />
                : <User className="w-4 h-4" style={{ color: 'var(--color-text-secondary)' }} />
              }
            </div>
            <div
              className={`text-[13px] leading-relaxed rounded-xl px-3.5 py-2.5 max-w-[75%] whitespace-pre-wrap break-words ${m.role === 'user' ? 'text-right' : ''}`}
              style={{
                backgroundColor: m.role === 'assistant' ? 'var(--color-accent-light)' : 'var(--color-bg-secondary)',
                color: 'var(--color-text-primary)',
                border: `1px solid var(--color-border)`,
              }}
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ backgroundColor: 'var(--color-accent-light)' }}>
              <Bot className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />
            </div>
            <div className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl border" style={{ backgroundColor: 'var(--color-accent-light)', borderColor: 'var(--color-border)' }}>
              <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--color-accent)' }} />
              <span className="text-[13px]" style={{ color: 'var(--color-text-secondary)' }}>思考中...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="p-3 border-t shrink-0 flex items-center gap-2" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="追问诊断细节"
          disabled={loading}
          aria-label="追问诊断细节"
          className="h-10 flex-1 rounded-md border px-3 text-[13px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:opacity-40"
          style={{
            backgroundColor: 'var(--color-bg-primary)',
            borderColor: 'var(--color-border)',
            color: 'var(--color-text-primary)',
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-blue-600 text-white transition hover:bg-blue-700 active:scale-[0.98] disabled:opacity-40"
          style={{ backgroundColor: 'var(--color-accent)' }}
          aria-label="发送追问"
          title="发送"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ChevronUp className="w-5 h-5" />}
        </button>
      </div>
    </div>
  );
}
