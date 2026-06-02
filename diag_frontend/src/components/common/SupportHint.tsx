import { LifeBuoy } from 'lucide-react';
import type { CSSProperties } from 'react';

interface SupportHintProps {
  className?: string;
  /** 附加一行说明，如「详细说明见系统设置 → 使用文档」 */
  extra?: string;
  compact?: boolean;
  style?: CSSProperties;
}

export default function SupportHint({ className = '', extra, compact = false, style }: SupportHintProps) {
  return (
    <p
      className={`flex items-start gap-1.5 leading-relaxed ${compact ? 'text-[11px]' : 'text-[12px]'} ${className}`}
      style={{ color: 'var(--color-text-muted)', ...style }}
    >
      <LifeBuoy className="w-3.5 h-3.5 shrink-0 mt-0.5" style={{ color: 'var(--color-accent)' }} />
      <span>
        遇到问题？光圈联系libiao1
        {extra ? (
          <>
            <span className="mx-1 opacity-50">·</span>
            {extra}
          </>
        ) : null}
      </span>
    </p>
  );
}
