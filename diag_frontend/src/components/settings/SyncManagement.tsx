import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Loader2, AlertCircle, CheckCircle2, Database, HardDrive, RefreshCw } from 'lucide-react';
import { syncApi, type AutoSyncConfig, type SyncJobItem } from '../../api/fastapi';
import SyncProgressModal from './SyncProgressModal';

const formatTime = (iso: string | null) => {
  if (!iso) return '从未';
  try { return new Date(iso).toLocaleString('zh-CN'); }
  catch { return iso; }
};

interface SectionCardProps {
  icon: React.ReactNode; title: string; description: string;
  enabled: boolean; intervalMinutes: number;
  onToggle: (enabled: boolean) => void; onIntervalChange: (minutes: number) => void;
  onTriggerAll: () => void; syncing: boolean;
  intervalOptions: { value: number; label: string }[];
  children?: React.ReactNode;
}

function SectionCard({ icon, title, description, enabled, intervalMinutes, onToggle, onIntervalChange, onTriggerAll, syncing, intervalOptions, children }: SectionCardProps) {
  return (
    <div className="rounded-xl border shadow-sm overflow-hidden" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
      <div className="px-5 py-4 border-b flex items-center gap-3 flex-wrap" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}>
        <span style={{ color: 'var(--color-accent)' }}>{icon}</span>
        <div className="flex-1 min-w-0">
          <h3 className="text-[14px] font-bold" style={{ color: 'var(--color-text-primary)' }}>{title}</h3>
          <p className="text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>{description}</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={intervalMinutes} onChange={(e) => onIntervalChange(Number(e.target.value))}
            className="h-8 px-2.5 rounded-lg border text-[12px] font-medium outline-none"
            style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)', color: 'var(--color-text-primary)' }}>
            {intervalOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
          </select>
          <button onClick={() => onToggle(!enabled)} className="h-8 w-14 rounded-full relative transition-colors"
            style={{ backgroundColor: enabled ? '#10b981' : 'var(--color-border)' }}>
            <div className="w-6 h-6 bg-white rounded-full absolute top-1 shadow transition-transform" style={{ left: enabled ? 'calc(100% - 28px)' : '4px' }} />
          </button>
          <button onClick={onTriggerAll} disabled={syncing}
            className="h-8 px-3 rounded-lg border text-[12px] font-bold flex items-center gap-1.5 transition-colors disabled:opacity-50"
            style={{ borderColor: 'var(--color-accent)', color: 'var(--color-accent)', backgroundColor: 'var(--color-accent-light)' }}>
            {syncing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}立即同步
          </button>
        </div>
      </div>
      {children}
    </div>
  );
}

const INTERVAL_OPTS = {
  sims: [{value:30,label:'每30分钟'},{value:60,label:'每1小时'},{value:120,label:'每2小时'},{value:240,label:'每4小时'},{value:480,label:'每8小时'},{value:720,label:'每12小时'},{value:1440,label:'每24小时'}],
  mes: [{value:1440,label:'每天'},{value:2880,label:'每2天'},{value:4320,label:'每3天'},{value:10080,label:'每周'}],
};

export default function SyncManagement() {
  const [config, setConfig] = useState<AutoSyncConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [syncingSims, setSyncingSims] = useState<Record<string, boolean>>({});
  const [syncingMes, setSyncingMes] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [recentJobs, setRecentJobs] = useState<SyncJobItem[]>([]);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsPage, setJobsPage] = useState(1);
  const [jobsLimit] = useState(10);
  const [progressJob, setProgressJob] = useState<{ jobId: string; factoryLabel: string } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const showFeedback = useCallback((type: 'success' | 'error', message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 3000);
  }, []);

  const fetchData = useCallback(async (showLoading = false) => {
    if (showLoading) { setLoading(true); setError(null); }
    try {
      // 获取配置和所有运行中的任务（用于显示厂区状态）
      const [cfg, allJobs] = await Promise.all([
        syncApi.getAutoConfig(),
        syncApi.getJobs({ page: 1, limit: 100 })  // 获取足够多的任务来检查运行状态
      ]);
      // 当前页的任务用于显示
      const pageJobs = await syncApi.getJobs({ page: jobsPage, limit: jobsLimit });

      if (cfg.success && cfg.data) setConfig(cfg.data);
      else if (showLoading) setError(cfg.error || '加载配置失败');
      if (allJobs.success && allJobs.data) {
        // 检查运行中的 SIMS 任务
        const runningJobs: Record<string, SyncJobItem> = {};
        for (const job of allJobs.data.items) {
          if (job.status === 'running' && job.sync_type === 'sims') {
            if (!runningJobs[job.factory_id] || job.started_at > runningJobs[job.factory_id].started_at) {
              runningJobs[job.factory_id] = job;
            }
          }
        }
        setSyncingSims(prev => {
          const newState: Record<string, boolean> = {};
          for (const fid of Object.keys(runningJobs)) newState[fid] = true;
          return Object.keys(newState).length > 0 ? newState : {};
        });
      }
      if (pageJobs.success && pageJobs.data) {
        setRecentJobs(pageJobs.data.items);
        setJobsTotal(pageJobs.data.total || 0);
      }
    } catch { if (showLoading) setError('网络错误，无法加载同步配置'); }
    finally { if (showLoading) setLoading(false); }
  }, [jobsPage, jobsLimit]);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    let elapsed = 0;
    pollRef.current = setInterval(() => {
      elapsed += 3; fetchData();
      if (elapsed >= 120 && pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    }, 3000);
  }, [fetchData]);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);
  useEffect(() => { fetchData(true); }, [fetchData]);

  // Generic config update helper
  const updateConfig = async (update: Parameters<typeof syncApi.updateAutoConfig>[0], successMsg?: string) => {
    setSaving(true);
    try {
      const resp = await syncApi.updateAutoConfig(update);
      if (resp.success && resp.data) { setConfig(resp.data); if (successMsg) showFeedback('success', successMsg); }
    } catch { showFeedback('error', '更新失败'); }
    finally { setSaving(false); }
  };

  const handleTriggerAllSims = async () => {
    setSyncingSims((prev) => { const s: Record<string,boolean> = {}; config?.sims.factories.forEach((f) => s[f.factory_id]=true); return s; });
    try {
      const resp = await syncApi.triggerSync();
      if (resp.success && resp.data) {
        showFeedback('success', `全厂区同步任务已启动（${resp.data.job_id}）`);
        setProgressJob({ jobId: resp.data.job_id, factoryLabel: '全部厂区' });
        startPolling(); fetchData(true);
      } else { showFeedback('error', resp.error || '触发失败'); }
    } catch { showFeedback('error', '网络错误'); }
    finally { setSyncingSims({}); }
  };

  const handleTriggerSims = async (factoryId: string) => {
    setSyncingSims(prev => ({ ...prev, [factoryId]: true }));
    try {
      const resp = await syncApi.triggerSync(factoryId);
      if (resp.success && resp.data) { setProgressJob({ jobId: resp.data.job_id, factoryLabel: factoryId }); startPolling(); fetchData(true); }
      else { showFeedback('error', resp.error || '触发失败'); }
    } catch { showFeedback('error', '网络错误'); }
    finally { setSyncingSims(prev => ({ ...prev, [factoryId]: false })); }
  };

  const handleTriggerMes = async () => {
    setSyncingMes(true);
    try {
      const resp = await syncApi.triggerMesSync();
      if (resp.success && resp.data) { setProgressJob({ jobId: resp.data.job_id, factoryLabel: 'MES' }); startPolling(); fetchData(true); }
      else { showFeedback('error', resp.error || '触发失败'); }
    } catch { showFeedback('error', '网络错误'); }
    finally { setSyncingMes(false); }
  };

  if (loading) return (
    <div className="rounded-xl shadow-sm overflow-hidden flex items-center justify-center py-16 gap-3"
      style={{ backgroundColor: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
      <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--color-accent)' }} />
      <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>加载同步配置中...</span>
    </div>
  );

  if (error) return (
    <div className="rounded-xl shadow-sm overflow-hidden" style={{ backgroundColor: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
      <div className="flex items-center gap-2 px-5 py-4 text-sm" style={{ color: '#dc2626', backgroundColor: 'rgba(239,68,68,0.06)' }}>
        <AlertCircle className="w-4 h-4 shrink-0" />{error}<button onClick={() => fetchData(true)} className="ml-auto font-bold underline">重试</button>
      </div>
    </div>
  );

  if (!config) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Database className="w-5 h-5" style={{ color: 'var(--color-accent)' }} />
        <h2 className="text-base font-bold" style={{ color: 'var(--color-text-primary)' }}>数据同步管理</h2>
        <span className="text-[11px] px-2 py-0.5 rounded-md font-medium" style={{ backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)' }}>自动调度</span>
      </div>

      {/* SIMS Section */}
      <SectionCard icon={<HardDrive className="w-4 h-4" />} title="平台数据同步 (SIMS)"
        description={`从各厂区 MES API 同步服务器列表及测试数据 · ${config.sims.factories.length} 个厂区`}
        enabled={config.sims.enabled} intervalMinutes={config.sims.interval_minutes}
        onToggle={(v) => updateConfig({ sims_enabled: v }, v ? '已启用 SIMS 自动同步' : '已禁用 SIMS 自动同步')}
        onIntervalChange={(v) => updateConfig({ sims_interval_minutes: v })}
        onTriggerAll={handleTriggerAllSims} syncing={Object.values(syncingSims).some(Boolean)} intervalOptions={INTERVAL_OPTS.sims}>
        <table className="w-full text-[13px]">
          <thead><tr style={{ color: 'var(--color-text-muted)', borderBottom: '1px solid var(--color-border)' }}>
            <th className="text-left font-medium px-5 py-3">厂区</th><th className="text-center font-medium px-5 py-3 w-20">启用</th>
            <th className="text-center font-medium px-5 py-3 w-24">状态</th>
            <th className="text-left font-medium px-5 py-3">上次同步</th><th className="text-right font-medium px-5 py-3 w-28">操作</th>
          </tr></thead>
          <tbody>
            {config.sims.factories.map((fac) => (
              <tr key={fac.factory_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                <td className="px-5 py-3 font-medium" style={{ color: 'var(--color-text-primary)' }}>{fac.factory_id}</td>
                <td className="px-5 py-3 text-center">
                  <button onClick={() => updateConfig({ factory_overrides: { [fac.factory_id]: { enabled: !fac.enabled } } })}
                    className="h-6 w-10 rounded-full relative transition-colors" style={{ backgroundColor: fac.enabled ? '#10b981' : 'var(--color-border)' }}>
                    <div className="w-4 h-4 bg-white rounded-full absolute top-1 shadow transition-transform" style={{ left: fac.enabled ? 'calc(100% - 18px)' : '2px' }} />
                  </button>
                </td>
                <td className="px-5 py-3 text-center">
                  {syncingSims[fac.factory_id] ? (
                    <span className="inline-flex items-center gap-1 text-[12px] font-medium px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: 'rgba(245,158,11,0.1)', color: '#d97706' }}>
                      <Loader2 className="w-3 h-3 animate-spin" />运行中
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[12px] font-medium px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: 'rgba(16,185,129,0.1)', color: '#059669' }}>
                      空闲
                    </span>
                  )}
                </td>
                <td className="px-5 py-3 font-mono text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>{formatTime(fac.last_run_at)}</td>
                <td className="px-5 py-3 text-right">
                  <button onClick={() => handleTriggerSims(fac.factory_id)} disabled={syncingSims[fac.factory_id]}
                    className="h-7 px-2.5 rounded-md border text-[12px] font-medium flex items-center gap-1 ml-auto transition-colors disabled:opacity-50"
                    style={{ borderColor: 'var(--color-accent)', color: 'var(--color-accent)', backgroundColor: 'var(--color-accent-light)' }}>
                    {syncingSims[fac.factory_id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    {syncingSims[fac.factory_id] ? '同步中' : '同步'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      {/* MES Section */}
      <SectionCard icon={<RefreshCw className="w-4 h-4" />} title="维修数据同步 (MES)"
        description="从 MES 主 API 同步维修记录并上传 RAGFlow 知识库"
        enabled={config.mes.enabled} intervalMinutes={config.mes.interval_minutes}
        onToggle={(v) => updateConfig({ mes_enabled: v }, v ? '已启用 MES 自动同步' : '已禁用 MES 自动同步')}
        onIntervalChange={(v) => updateConfig({ mes_interval_minutes: v })}
        onTriggerAll={handleTriggerMes} syncing={syncingMes} intervalOptions={INTERVAL_OPTS.mes}>
        <div className="px-5 py-4 flex items-center justify-between text-[13px]" style={{ color: 'var(--color-text-secondary)' }}>
          <span>上次同步: <span className="font-mono text-[12px]">{formatTime(config.mes.last_run_at)}</span></span>
          {saving && <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--color-accent)' }} />}
        </div>
      </SectionCard>

      {/* Recent Jobs */}
      {recentJobs.length > 0 && (
        <div className="rounded-xl border shadow-sm overflow-hidden" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
          <div className="px-5 py-3 border-b flex items-center justify-between"
            style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)' }}>
            <span className="text-[12px] font-bold uppercase tracking-widest">最近同步任务</span>
            {jobsTotal > jobsLimit && (
              <div className="flex items-center gap-2">
                <span className="text-[11px]">{Math.min((jobsPage - 1) * jobsLimit + 1, jobsTotal)}-{Math.min(jobsPage * jobsLimit, jobsTotal)} / {jobsTotal}</span>
                <button onClick={() => setJobsPage(p => Math.max(1, p - 1))} disabled={jobsPage <= 1}
                  className="h-6 w-6 rounded border text-[11px] disabled:opacity-30" style={{ borderColor: 'var(--color-border)' }}>‹</button>
                <button onClick={() => setJobsPage(p => Math.ceil(jobsTotal / jobsLimit) > p ? p + 1 : p)} disabled={jobsPage >= Math.ceil(jobsTotal / jobsLimit)}
                  className="h-6 w-6 rounded border text-[11px] disabled:opacity-30" style={{ borderColor: 'var(--color-border)' }}>›</button>
              </div>
            )}
          </div>
          <table className="w-full text-[13px]">
            <thead><tr style={{ color: 'var(--color-text-muted)', borderBottom: '1px solid var(--color-border)' }}>
              <th className="text-left font-medium px-5 py-2.5">类型</th><th className="text-left font-medium px-5 py-2.5">厂区</th>
              <th className="text-left font-medium px-5 py-2.5">状态</th><th className="text-left font-medium px-5 py-2.5">开始时间</th>
            </tr></thead>
            <tbody>
              {recentJobs.map((job) => (
                <tr key={job.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td className="px-5 py-2.5 font-medium" style={{ color: 'var(--color-text-primary)' }}>{job.sync_type === 'sims' ? 'SIMS' : 'MES'}</td>
                  <td className="px-5 py-2.5 font-mono text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>{job.factory_id}</td>
                  <td className="px-5 py-2.5">
                    <span className="inline-flex items-center gap-1 text-[12px] font-medium px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: job.status === 'completed' ? 'rgba(16,185,129,0.1)' : job.status === 'failed' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
                              color: job.status === 'completed' ? '#059669' : job.status === 'failed' ? '#dc2626' : '#d97706' }}>
                      {job.status === 'running' && <Loader2 className="w-3 h-3 animate-spin" />}
                      {job.status === 'completed' ? '完成' : job.status === 'failed' ? '失败' : '运行中'}
                    </span>
                  </td>
                  <td className="px-5 py-2.5 font-mono text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>{formatTime(job.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {progressJob && <SyncProgressModal jobId={progressJob.jobId} factoryLabel={progressJob.factoryLabel} onClose={() => setProgressJob(null)} />}

      {feedback && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium shadow-lg animate-pulse"
          style={{ backgroundColor: feedback.type === 'success' ? '#ecfdf5' : '#fef2f2', color: feedback.type === 'success' ? '#059669' : '#dc2626', border: `1px solid ${feedback.type === 'success' ? '#059669' : '#dc2626'}44` }}>
          {feedback.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}{feedback.message}
        </div>
      )}
    </div>
  );
}