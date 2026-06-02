import { useState, useEffect, useCallback } from 'react';
import { Loader2, AlertCircle, CheckCircle2, Database, HardDrive, RefreshCw, History, X } from 'lucide-react';
import { syncApi, type AutoSyncConfig, type SyncJobItem } from '../../api/fastapi';
import SyncProgressModal from './SyncProgressModal';
import { formatTime } from '../../utils/time';

const INTERVAL_OPTS = {
  sims: [{value:30,label:'每30分钟'},{value:60,label:'每1小时'},{value:120,label:'每2小时'},{value:240,label:'每4小时'},{value:480,label:'每8小时'},{value:720,label:'每12小时'},{value:1440,label:'每24小时'}],
  mes: [{value:1440,label:'每天'},{value:2880,label:'每2天'},{value:4320,label:'每3天'},{value:10080,label:'每周'}],
};

// ── 小组件 ──
function Toggle({ value, onChange, size = 'md' }: { value: boolean; onChange: () => void; size?: 'sm' | 'md' }) {
  const dim = size === 'sm' ? { track: 'h-5 w-9', dot: 'w-3.5 h-3.5 top-[3px]', off: '2px', on: 'calc(100% - 16px)' }
    : { track: 'h-7 w-12', dot: 'w-5 h-5 top-1', off: '2px', on: 'calc(100% - 22px)' };
  return (
    <button onClick={onChange} className={`${dim.track} rounded-full relative transition-colors`}
      style={{ backgroundColor: value ? '#10b981' : 'var(--color-border)' }}>
      <div className={`${dim.dot} bg-white rounded-full absolute shadow transition-transform`}
        style={{ left: value ? dim.on : dim.off }} />
    </button>
  );
}

function SyncBtn({ onClick, loading, label, full }: { onClick: () => void; loading: boolean; label: string; full?: boolean }) {
  return (
    <button onClick={onClick} disabled={loading}
      className={`h-7 px-3 rounded-md border text-[11px] font-bold flex items-center gap-1 transition-colors disabled:opacity-50 ${full ? '' : ''}`}
      style={{ borderColor: 'var(--color-accent)', color: full ? '#fff' : 'var(--color-accent)', backgroundColor: full ? 'var(--color-accent)' : 'var(--color-accent-light)' }}>
      {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}{label}
    </button>
  );
}

// ── 历史任务弹窗 ──
function SyncHistoryModal({ onClose }: { onClose: () => void }) {
  const [jobs, setJobs] = useState<SyncJobItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const resp = await syncApi.getJobs({ page: p, limit: 10 });
      if (resp.success && resp.data) { setJobs(resp.data.items); setTotal(resp.data.total || 0); }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(1); }, [load]);

  const go = (p: number) => { setPage(p); load(p); };
  const totalPages = Math.ceil(total / 10);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <div className="rounded-2xl border shadow-2xl w-[640px] max-h-[80vh] flex flex-col overflow-hidden"
        style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }} onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b flex items-center justify-between shrink-0"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
          <div className="flex items-center gap-3">
            <History className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />
            <span className="text-[14px] font-bold" style={{ color: 'var(--color-text-primary)' }}>最近同步任务</span>
          </div>
          <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center hover:opacity-70"
            style={{ color: 'var(--color-text-muted)' }}><X className="w-4 h-4" /></button>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {loading ? (
            <div className="flex items-center justify-center py-16"><Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--color-accent)' }} /></div>
          ) : jobs.length === 0 ? (
            <div className="flex items-center justify-center py-16 text-sm" style={{ color: 'var(--color-text-muted)' }}>暂无同步记录</div>
          ) : (
            <table className="w-full text-[13px]">
              <thead><tr style={{ color: 'var(--color-text-muted)', borderBottom: '1px solid var(--color-border)' }}>
                <th className="text-left font-medium px-5 py-3 w-20">类型</th>
                <th className="text-left font-medium px-5 py-3 w-24">厂区</th>
                <th className="text-left font-medium px-5 py-3">开始时间</th>
              </tr></thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td className="px-5 py-2.5">
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
                        style={{ backgroundColor: job.sync_type === 'sims' ? 'rgba(99,102,241,0.08)' : 'rgba(16,185,129,0.08)', color: job.sync_type === 'sims' ? '#6366f1' : '#059669' }}>
                        {job.sync_type === 'sims' ? 'SIMS' : 'MES'}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 font-mono text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>{job.factory_id}</td>
                    <td className="px-5 py-2.5 font-mono text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>{formatTime(job.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        {totalPages > 1 && (
          <div className="px-5 py-3 border-t flex items-center justify-between shrink-0"
            style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{(page - 1) * 10 + 1}-{Math.min(page * 10, total)} / {total}</span>
            <div className="flex items-center gap-2">
              <button onClick={() => go(page - 1)} disabled={page <= 1}
                className="h-7 px-3 rounded-lg border text-xs font-medium disabled:opacity-30 hover:bg-black/[0.03]"
                style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-bg-primary)' }}>上一页</button>
              <button onClick={() => go(page + 1)} disabled={page >= totalPages}
                className="h-7 px-3 rounded-lg border text-xs font-medium disabled:opacity-30 hover:bg-black/[0.03]"
                style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-bg-primary)' }}>下一页</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── 主组件 ──
export default function SyncManagement() {
  const [config, setConfig] = useState<AutoSyncConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState<{ mes: boolean; factories: Record<string, boolean> }>({ mes: false, factories: {} });
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [progressJob, setProgressJob] = useState<{ jobId: string; label: string } | null>(null);

  const showFeedback = useCallback((type: 'success' | 'error', message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 3000);
  }, []);

  const fetchData = useCallback(async (showLoading = false) => {
    if (showLoading) { setLoading(true); setError(null); }
    try {
      const cfg = await syncApi.getAutoConfig();
      if (cfg.success && cfg.data) setConfig(cfg.data);
      else if (showLoading) setError(cfg.error || '加载配置失败');
    } catch { if (showLoading) setError('网络错误，无法加载同步配置'); }
    finally { if (showLoading) setLoading(false); }
  }, []);

  useEffect(() => { fetchData(true); }, [fetchData]);

  const updateConfig = async (update: Parameters<typeof syncApi.updateAutoConfig>[0], successMsg?: string) => {
    setSaving(true);
    try {
      const resp = await syncApi.updateAutoConfig(update);
      if (resp.success && resp.data) { setConfig(resp.data); if (successMsg) showFeedback('success', successMsg); }
    } catch { showFeedback('error', '更新失败'); }
    finally { setSaving(false); }
  };

  // 通用触发：fn 里设置 loading 态 → 调用 API → 弹进度/报错 → finally reset
  const trigger = async (
    fn: () => Promise<{ success: boolean; data?: { job_id: string }; error?: string }>,
    label: string,
    reset: () => void,
  ) => {
    try {
      const resp = await fn();
      if (resp.success && resp.data) setProgressJob({ jobId: resp.data.job_id, label });
      else showFeedback('error', resp.error || '触发失败');
    } catch { showFeedback('error', '网络错误'); }
    finally { reset(); }
  };

  if (loading) return (
    <div className="rounded-xl border shadow-sm flex items-center justify-center py-16 gap-3" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
      <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--color-accent)' }} />
      <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>加载同步配置中...</span>
    </div>
  );
  if (error) return (
    <div className="rounded-xl border" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
      <div className="flex items-center gap-2 px-5 py-4 text-sm" style={{ color: '#dc2626', backgroundColor: 'rgba(239,68,68,0.06)' }}>
        <AlertCircle className="w-4 h-4 shrink-0" />{error}<button onClick={() => fetchData(true)} className="ml-auto font-bold underline">重试</button>
      </div>
    </div>
  );
  if (!config) return null;

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center gap-3">
        <Database className="w-5 h-5" style={{ color: 'var(--color-accent)' }} />
        <h2 className="text-base font-bold" style={{ color: 'var(--color-text-primary)' }}>数据同步管理（历史数据统计）</h2>
        <span className="text-[11px] px-2 py-0.5 rounded-md font-medium" style={{ backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)' }}>自动调度</span>
        <button onClick={() => setShowHistory(true)}
          className="ml-auto h-7 px-3 rounded-lg border text-[11px] font-medium flex items-center gap-1.5 hover:opacity-80"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-bg-primary)' }}>
          <History className="w-3.5 h-3.5" />最近同步
        </button>
      </div>

      {/* ── 同步配置卡片 ── */}
      <div className="rounded-xl border shadow-sm overflow-hidden" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
        {/* SIMS 头部 */}
        <div className="px-5 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
          <div className="flex items-center gap-2">
            <HardDrive className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />
            <span className="text-[13px] font-bold" style={{ color: 'var(--color-text-primary)' }}>SIMS 平台数据同步</span>
            <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>{config.sims.factories.length} 个厂区</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] mr-1" style={{ color: 'var(--color-text-muted)' }}>调度间隔</span>
            <select value={config.sims.interval_minutes} onChange={(e) => updateConfig({ sims_interval_minutes: Number(e.target.value) })}
              className="h-7 px-2 rounded-md border text-[11px] font-medium outline-none"
              style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)', color: 'var(--color-text-primary)' }}>
              {INTERVAL_OPTS.sims.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <Toggle value={config.sims.enabled} onChange={() => updateConfig({ sims_enabled: !config.sims.enabled })} />
            <SyncBtn full label="全部同步" loading={Object.values(syncing.factories).some(Boolean)}
              onClick={() => trigger(
                () => { setSyncing(p => { const s: Record<string,boolean> = {}; config.sims.factories.forEach(f => s[f.factory_id]=true); return { ...p, factories: s }; }); return syncApi.triggerSync(); },
                '全部厂区',
                () => setSyncing(p => ({ ...p, factories: {} })),
              )} />
          </div>
        </div>
        {/* SIMS 工厂列表 */}
        <div className="divide-y" style={{ borderColor: 'var(--color-border)' }}>
          {config.sims.factories.map((fac) => (
            <div key={fac.factory_id} className="px-5 py-2.5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--color-border)' }}>
              <span className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>{fac.factory_id}</span>
              <div className="flex items-center gap-3">
                <Toggle size="sm" value={fac.enabled} onChange={() => updateConfig({ factory_overrides: { [fac.factory_id]: { enabled: !fac.enabled } } })} />
                <SyncBtn label={syncing.factories[fac.factory_id] ? '同步中' : '同步'} loading={!!syncing.factories[fac.factory_id]}
                  onClick={() => trigger(
                    () => { setSyncing(p => ({ ...p, factories: { ...p.factories, [fac.factory_id]: true } })); return syncApi.triggerSync(fac.factory_id); },
                    fac.factory_id,
                    () => setSyncing(p => ({ ...p, factories: { ...p.factories, [fac.factory_id]: false } })),
                  )} />
              </div>
            </div>
          ))}
        </div>

        {/* MES */}
        <div className="px-5 py-3 flex items-center justify-between" style={{ backgroundColor: 'var(--color-bg-secondary)', borderTop: '1px solid var(--color-border)' }}>
          <div className="flex items-center gap-2">
            <RefreshCw className="w-3.5 h-3.5" style={{ color: 'var(--color-accent)' }} />
            <span className="text-[13px] font-bold" style={{ color: 'var(--color-text-primary)' }}>MES 维修数据同步</span>
            <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>上次: <span className="font-mono">{formatTime(config.mes.last_run_at)}</span></span>
          </div>
          <div className="flex items-center gap-2">
            <select value={config.mes.interval_minutes} onChange={(e) => updateConfig({ mes_interval_minutes: Number(e.target.value) })}
              className="h-7 px-2 rounded-md border text-[11px] font-medium outline-none"
              style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)', color: 'var(--color-text-primary)' }}>
              {INTERVAL_OPTS.mes.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <Toggle value={config.mes.enabled} onChange={() => updateConfig({ mes_enabled: !config.mes.enabled })} />
            <SyncBtn label={syncing.mes ? '同步中' : '同步'} loading={syncing.mes}
              onClick={() => trigger(
                () => { setSyncing(p => ({ ...p, mes: true })); return syncApi.triggerMesSync(); },
                'MES',
                () => setSyncing(p => ({ ...p, mes: false })),
              )} />
          </div>
        </div>
      </div>

      {showHistory && <SyncHistoryModal onClose={() => setShowHistory(false)} />}

      {progressJob && <SyncProgressModal jobId={progressJob.jobId} factoryLabel={progressJob.label} onClose={() => setProgressJob(null)} />}

      {feedback && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium shadow-lg animate-pulse"
          style={{ backgroundColor: feedback.type === 'success' ? '#ecfdf5' : '#fef2f2', color: feedback.type === 'success' ? '#059669' : '#dc2626', border: `1px solid ${feedback.type === 'success' ? '#059669' : '#dc2626'}44` }}>
          {feedback.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}{feedback.message}
        </div>
      )}
    </div>
  );
}
