import { useState } from 'react';
import { Check, ChevronDown, Minus, RefreshCw } from 'lucide-react';

type Stage = string;
interface StageDetail {
  label: string;
  value: string;
  multiline?: boolean;
}
interface ProgressIndicatorProps {
  stages: Stage[];
  labels: Record<string, string>;
  currentStage: string | null;
  currentDetail?: string;
  skippedStages?: Record<string, string>;
  stageDetails?: Record<string, StageDetail[]>;
  streamingText?: string;
}

export default function ProgressIndicator({
  stages,
  labels,
  currentStage,
  currentDetail,
  skippedStages = {},
  stageDetails = {},
  streamingText,
}: ProgressIndicatorProps) {
  const [expandedStage, setExpandedStage] = useState<string | null>(null);
  const curIdx = currentStage ? stages.indexOf(currentStage) : 0;
  const isLlmStage = currentStage === stages[stages.length - 1];

  return (
    <div>
      {stages.map((stage) => {
        const idx = stages.indexOf(stage);
        const skipped = stage in skippedStages;
        const done = !skipped && idx < curIdx;
        const cur = !skipped && idx === curIdx;
        const detail = skipped ? skippedStages[stage] : (cur ? currentDetail : '');
        const disclosure = stageDetails[stage] || [];
        const expandable = disclosure.length > 0;
        const expanded = expandedStage === stage;

        return (
          <div key={stage}>
            <button
              type="button"
              disabled={!expandable}
              onClick={() => setExpandedStage(expanded ? null : stage)}
              aria-expanded={expandable ? expanded : undefined}
              className={`flex w-full items-start gap-3 py-2.5 px-4 rounded-lg text-left ${expandable ? 'cursor-pointer hover:bg-black/5' : ''}`}
            >
              <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                style={{ backgroundColor: done ? '#10b981' : cur ? 'var(--color-accent)' : 'var(--color-border)' }}>
                {done ? (
                  <Check className="w-4 h-4 text-white" strokeWidth={3} />
                ) : skipped ? (
                  <Minus className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} strokeWidth={2.5} />
                ) : cur ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-white" />
                ) : (
                  <div className="w-2 h-2 rounded-full" style={{ color: 'var(--color-text-muted)' }} />
                )}
              </div>
              <div className="min-w-0 flex-1 pt-1">
                <span className={`block text-[13px] ${cur ? 'font-semibold' : done ? 'font-medium' : ''}`}
                  style={{ color: done ? '#10b981' : cur ? 'var(--color-accent)' : 'var(--color-text-muted)' }}>
                  {labels[stage] || stage}
                </span>
                {detail && !isLlmStage && (
                  <span
                    className={`block mt-0.5 text-[11px] leading-4 break-words ${cur ? 'animate-pulse' : ''}`}
                    style={{ color: cur ? 'var(--color-accent)' : 'var(--color-text-muted)' }}
                  >
                    {skipped ? `已跳过：${detail}` : detail}
                  </span>
                )}
              </div>
              {expandable && (
                <ChevronDown
                  className={`mt-1.5 h-4 w-4 shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
                  style={{ color: 'var(--color-text-muted)' }}
                />
              )}
            </button>
            {expanded && expandable && (
              <dl className="ml-14 mr-4 mb-3 border-l pl-3 space-y-2" style={{ borderColor: 'var(--color-border)' }}>
                {disclosure.map((item) => (
                  <div key={item.label}>
                    <dt className="text-[10px] font-bold uppercase" style={{ color: 'var(--color-text-muted)' }}>
                      {item.label}
                    </dt>
                    {item.multiline ? (
                      <dd className="mt-1 max-h-36 overflow-y-auto custom-scrollbar">
                        <pre className="whitespace-pre-wrap break-words text-[11px] leading-4 font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                          {item.value || '未配置'}
                        </pre>
                      </dd>
                    ) : (
                      <dd className="text-[12px] break-words" style={{ color: 'var(--color-text-primary)' }}>
                        {item.value || '未配置'}
                      </dd>
                    )}
                  </div>
                ))}
              </dl>
            )}
          </div>
        );
      })}
      {isLlmStage && streamingText && (
        <div className="mx-4 mt-2 rounded-lg border p-3 max-h-64 overflow-y-auto custom-scrollbar"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
          <pre className="text-[12px] leading-relaxed whitespace-pre-wrap break-words font-mono"
            style={{ color: 'var(--color-text-primary)' }}>
            {streamingText}
          </pre>
        </div>
      )}
    </div>
  );
}
