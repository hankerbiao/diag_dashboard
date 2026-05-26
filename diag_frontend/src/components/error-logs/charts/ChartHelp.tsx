import { useState, useRef, useEffect } from 'react';
import { HelpCircle } from 'lucide-react';
import { useTheme } from '../../../contexts/ThemeContext';

interface Props {
  text: string;
}

export default function ChartHelp({ text }: Props) {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="p-0.5 rounded-full transition-colors hover:opacity-70"
        style={{ color: isDark ? '#64748b' : '#94a3b8' }}
        title="图表说明"
      >
        <HelpCircle className="w-3.5 h-3.5" />
      </button>
      {open && (
        <div
          className="absolute left-1/2 -translate-x-1/2 top-6 z-50 w-60 p-3 rounded-lg text-[11px] leading-relaxed shadow-lg border"
          style={{
            backgroundColor: isDark ? '#1e293b' : '#ffffff',
            borderColor: isDark ? '#334155' : '#e2e8f0',
            color: isDark ? '#cbd5e1' : '#475569',
          }}
        >
          <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rotate-45" style={{ backgroundColor: isDark ? '#1e293b' : '#ffffff', borderLeft: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`, borderTop: `1px solid ${isDark ? '#334155' : '#e2e8f0'}` }} />
          {text}
        </div>
      )}
    </div>
  );
}
