import { CheckCircle2, Database } from 'lucide-react';

interface FooterProps {
  activeKBsCount: number;
}

export default function Footer({ activeKBsCount }: FooterProps) {
  return (
    <div
      className="h-8 border-t flex justify-between items-center px-5 shrink-0 z-20 text-[10.5px]"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
        color: 'var(--color-text-secondary)',
      }}
    >
      <div className="flex items-center gap-4 font-medium">
        <div className="flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5" style={{ color: 'var(--color-accent)' }} />
          系统连通性正常
        </div>
      </div>

      <div className="flex items-center gap-4 font-medium tracking-wide">
        <div className="flex items-center gap-1.5">
          <Database className="w-3.5 h-3.5" style={{ color: 'var(--color-accent)' }} />
          已挂载知识库:{' '}
          <span className="font-bold" style={{ color: 'var(--color-text-primary)' }}>
            {activeKBsCount} / 3
          </span>
        </div>
        <div className="w-px h-3.5" style={{ backgroundColor: 'var(--color-border)' }} />
        <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
          <span className="relative flex h-2 w-2 mr-0.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          大模型引擎就绪
        </div>
      </div>
    </div>
  );
}