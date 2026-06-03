import { Terminal, FileText } from 'lucide-react';

export default function ExternalSyncNotice() {
  return (
    <section
      className="rounded-xl border p-6 space-y-4"
      style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
    >
      <div className="flex items-center gap-2">
        <Terminal className="w-5 h-5 shrink-0" style={{ color: 'var(--color-accent)' }} />
        <h2 className="text-[15px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
          数据同步（独立任务）
        </h2>
      </div>
      <p className="text-[12px] leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
        测试数据与维修记录的写入已迁出 API 服务，请在部署机或定时任务中执行仓库内同步脚本。
        本系统仅读取 MongoDB 中已同步数据；异常看板「实时查询」仍通过 MES 接口拉取。
      </p>
      <div
        className="rounded-lg p-4 font-mono text-[11px] space-y-2 overflow-x-auto"
        style={{ backgroundColor: 'var(--color-bg-primary)', color: 'var(--color-text-secondary)' }}
      >
        <div>cp scripts/sync_config.example.yaml scripts/sync_config.yaml</div>
        <div>python scripts/weaveeye_sync.py run</div>
        <div className="opacity-80"># 或: ./scripts/run_sync.sh</div>
      </div>
      <p className="text-[11px] flex items-center gap-1.5" style={{ color: 'var(--color-text-muted)' }}>
        <FileText className="w-3.5 h-3.5 shrink-0" />
        详见仓库 <span className="font-mono">scripts/README.md</span>
      </p>
    </section>
  );
}
