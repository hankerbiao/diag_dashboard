import { RefreshCw } from 'lucide-react';

type Stage = string;
interface ProgressIndicatorProps {
  stages: Stage[];
  labels: Record<string, string>;
  currentStage: string | null;
  streamingText?: string;
}

export default function ProgressIndicator({ stages, labels, currentStage, streamingText }: ProgressIndicatorProps) {
  const curIdx = currentStage ? stages.indexOf(currentStage) : 0;

  return (
    <div>
      {stages.map((stage) => {
        const idx = stages.indexOf(stage);
        const done = idx < curIdx, cur = idx === curIdx;

        return (
          <div key={stage} className="flex items-center gap-3 py-2.5 px-4 rounded-lg">
            <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
              style={{ backgroundColor: done ? '#10b981' : cur ? 'var(--color-accent)' : 'var(--color-border)' }}>
              {done ? (
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : cur ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-white" />
              ) : (
                <div className="w-2 h-2 rounded-full" style={{ color: 'var(--color-text-muted)' }} />
              )}
            </div>
            <span className={`text-[13px] flex-1 ${cur ? 'font-semibold' : done ? 'font-medium' : ''}`}
              style={{ color: done ? '#10b981' : cur ? 'var(--color-accent)' : 'var(--color-text-muted)' }}>
              {labels[stage] || stage}
            </span>
            {cur && currentStage && (
              <span className="text-[11px] animate-pulse" style={{ color: 'var(--color-accent)' }}>
                {currentStage === stages[stages.length - 1] ? streamingText || '推理中...' : labels[currentStage] || ''}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}