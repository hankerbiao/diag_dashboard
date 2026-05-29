import { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, XCircle, Clock, X, Terminal } from 'lucide-react';
import { syncApi, type SyncJobItem } from '../../api/fastapi';

interface SyncProgressModalProps {
  jobId: string;
  factoryLabel: string;
  onClose: () => void;
}

const STATUS_CONFIG = {
  running:  { Icon: Loader2,     label: '同步中', color: '#d97706', bg: 'rgba(245,158,11,0.1)' },
  completed:{ Icon: CheckCircle2, label: '同步完成', color: '#059669', bg: 'rgba(16,185,129,0.1)' },
  failed:   { Icon: XCircle,     label: '同步失败', color: '#dc2626', bg: 'rgba(239,68,68,0.1)' },
} as const;

const EMPTY_MSG = { running: '等待脚本输出...', completed: '同步完成，无输出', failed: '同步失败，无输出' } as const;

function ElapsedTime({ since }: { since: string }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const secs = Math.floor((Date.now() - new Date(since).getTime()) / 1000);
  return <span className="font-mono">{Math.floor(secs/60)}:{String(secs%60).padStart(2, '0')}</span>;
}

export default function SyncProgressModal({ jobId, factoryLabel, onClose }: SyncProgressModalProps) {
  const [job, setJob] = useState<SyncJobItem | null>(null);
  const doneRef = useRef(false);

  useEffect(() => {
    const poll = async () => {
      try {
        const resp = await syncApi.getJobDetail(jobId);
        if (resp.success && resp.data) {
          setJob(resp.data);
          if (resp.data.status !== 'running') doneRef.current = true;
        }
      } catch { /* ignore */ }
    };
    poll();
    const id = setInterval(poll, 1500);
    return () => clearInterval(id);
  }, [jobId]);

  const statusKey = job?.status ?? 'running';
  const { Icon: StatusIcon, label, color, bg } = STATUS_CONFIG[statusKey as keyof typeof STATUS_CONFIG] ?? STATUS_CONFIG.running;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={doneRef.current ? onClose : undefined}>
      <div className="rounded-2xl border shadow-2xl w-[560px] max-h-[80vh] flex flex-col overflow-hidden"
        style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}
        onClick={(e) => e.stopPropagation()}>

        <div className="px-5 py-4 border-b flex items-center justify-between shrink-0"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
          <div className="flex items-center gap-3">
            <Terminal className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />
            <span className="text-[14px] font-bold" style={{ color: 'var(--color-text-primary)' }}>同步进度 — {factoryLabel}</span>
          </div>
          <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center hover:opacity-70"
            style={{ color: 'var(--color-text-muted)' }}>
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 py-3 border-b flex items-center gap-4 shrink-0" style={{ borderColor: 'var(--color-border)' }}>
          <span className="inline-flex items-center gap-1.5 text-[13px] font-bold px-3 py-1 rounded-full" style={{ backgroundColor: bg, color }}>
            <StatusIcon className={`w-3.5 h-3.5 ${statusKey === 'running' ? 'animate-spin' : ''}`} />
            {label}
          </span>
          <div className="flex items-center gap-1.5 text-[13px]" style={{ color: 'var(--color-text-secondary)' }}>
            <Clock className="w-3.5 h-3.5" />
            {job ? <ElapsedTime since={job.started_at} /> : '--:--'}
          </div>
          {statusKey === 'completed' && (
            <button onClick={onClose} className="ml-auto text-[12px] font-bold px-4 py-1.5 rounded-lg text-white"
              style={{ backgroundColor: 'var(--color-accent)' }}>关闭</button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 min-h-[200px]">
          {!job ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--color-accent)' }} />
            </div>
          ) : job.progress ? (
            <pre className="text-[11px] font-mono leading-relaxed rounded-xl p-4 whitespace-pre-wrap break-all min-h-full"
              style={{ backgroundColor: '#0d1117', color: '#c9d1d9', border: '1px solid #30363d' }}>
              {job.progress}
              {statusKey === 'running' && <span className="animate-pulse text-blue-400">{'▌'}</span>}
            </pre>
          ) : (
            <div className="flex items-center justify-center h-full text-sm" style={{ color: 'var(--color-text-muted)' }}>
              {EMPTY_MSG[statusKey as keyof typeof EMPTY_MSG]}
            </div>
          )}
        </div>

        {statusKey === 'failed' && job?.error && (
          <div className="px-5 py-3 border-t shrink-0" style={{ borderColor: 'var(--color-border)' }}>
            <p className="text-[12px] font-bold mb-1" style={{ color: '#dc2626' }}>错误信息</p>
            <pre className="text-[11px] font-mono text-red-400 bg-red-50 rounded-lg p-3 max-h-24 overflow-y-auto whitespace-pre-wrap break-all">
              {job.error}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
