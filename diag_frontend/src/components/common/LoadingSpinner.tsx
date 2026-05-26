import type { ReactNode } from 'react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  text?: string;
  fullScreen?: boolean;
}

const sizeMap = {
  sm: 'w-4 h-4 border',
  md: 'w-5 h-5 border-2',
  lg: 'w-8 h-8 border-2',
};

/**
 * 统一的加载动画组件
 */
export default function LoadingSpinner({ size = 'md', text, fullScreen = false }: LoadingSpinnerProps) {
  const spinnerClass = sizeMap[size];
  const textClass = size === 'sm' ? 'text-[10px]' : size === 'lg' ? 'text-base' : 'text-xs';

  const content = (
    <div className="flex items-center justify-center gap-2" style={{ color: 'var(--color-text-secondary)' }}>
      <div
        className={`${spinnerClass} border-t-transparent rounded-full animate-spin`}
        style={{ borderColor: 'var(--color-accent)', borderTopColor: 'transparent' }}
      />
      {text && <span className={textClass}>{text}</span>}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="flex-1 flex items-center justify-center">
        {content}
      </div>
    );
  }

  return content;
}

/**
 * 带文字的空状态组件
 */
export function EmptyState({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3" style={{ color: 'var(--color-text-secondary)' }}>
      <div className="w-8 h-8 opacity-40">{icon}</div>
      <span className="text-sm">{text}</span>
    </div>
  );
}