import { Database, Terminal, Network } from 'lucide-react';
import type { FactoryLocation } from '../../types';

interface ReferenceDataProps {
  factory: FactoryLocation;
}

export default function ReferenceData({ factory }: ReferenceDataProps) {
  return (
    <div
      className="w-[45%] flex flex-col shrink-0 shadow-inner overflow-hidden min-h-0"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <div
        className="p-4 border-b sticky top-0 z-10 flex justify-between items-center shrink-0 backdrop-blur-md"
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.7)',
          borderColor: 'var(--color-border)',
          color: 'var(--color-text-primary)',
        }}
      >
        <h2 className="text-[13px] font-bold flex items-center gap-2">
          <Database className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />
          结构化参考数据源支撑 ({factory}厂区)
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-6 custom-scrollbar min-h-0">
        <div
          className="border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow"
          style={{
            backgroundColor: 'var(--color-bg-secondary)',
            borderColor: 'var(--color-border)',
          }}
        >
          <div
            className="px-4 py-3 text-xs font-semibold border-b flex justify-between items-center"
            style={{
              backgroundColor: 'var(--color-bg-primary)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-secondary)',
            }}
          >
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4" style={{ color: 'var(--color-text-secondary)' }} />{' '}
              SIMS 测试拦截点快照
            </div>
          </div>
          <div
            className="p-4 font-mono text-[11px] leading-relaxed space-y-2 overflow-x-auto shadow-inner"
            style={{ backgroundColor: '#1a1b26', color: '#94a3b8' }}
          >
            <div className="flex gap-3 whitespace-nowrap opacity-70">
              <span className="text-slate-500 shrink-0">[14:22:01.032]</span>
              <span className="text-cyan-400 shrink-0 font-bold">INFO</span>
              <span>Initializing Memory Controller B...</span>
            </div>
            <div className="flex gap-3 whitespace-nowrap">
              <span className="text-slate-500 shrink-0">[14:23:44.209]</span>
              <span className="text-red-400 shrink-0 font-bold">FAIL</span>
              <span className="text-red-300 font-medium">Parity mismatch detected at proxy address 0x00FF82200</span>
            </div>
            <div className="flex gap-3 whitespace-nowrap text-amber-200/80">
              <span className="text-slate-500 shrink-0">[14:23:45.001]</span>
              <span className="text-amber-500 shrink-0 font-bold">WARN</span>
              <span>Retry 1 of 3 exhausted logic sequence...</span>
            </div>
          </div>
        </div>

        <div
          className="border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow"
          style={{
            backgroundColor: 'var(--color-bg-secondary)',
            borderColor: 'var(--color-border)',
          }}
        >
          <div
            className="px-4 py-3 text-xs font-semibold border-b flex items-center justify-between"
            style={{
              backgroundColor: 'var(--color-accent-light)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-accent)',
            }}
          >
            <div className="flex items-center gap-2">
              <Network className="w-4 h-4" /> 历史维修知识图谱关联匹配
            </div>
            <div
              className="text-[10px] font-bold px-2 py-0.5 rounded-full border shadow-sm"
              style={{
                backgroundColor: 'var(--color-bg-secondary)',
                borderColor: 'var(--color-accent)',
              }}
            >
              关键特征相似度: 94.6%
            </div>
          </div>
          <div className="p-5">
            <div
              className="text-[13px] leading-relaxed p-4 rounded-xl border shadow-inner"
              style={{
                backgroundColor: 'var(--color-bg-primary)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            >
              <div className="mb-2">
                相似历史异常设备标签{' '}
                <code
                  className="border px-1.5 py-0.5 rounded shadow-sm font-semibold font-mono mx-1"
                  style={{
                    backgroundColor: 'var(--color-bg-secondary)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  CN-0M38-0015
                </code>{' '}
                ，呈现了强一致态的奇偶校验位故障特征。
              </div>
              <div className="mt-4 border-t pt-4 flex flex-col gap-2" style={{ borderColor: 'var(--color-border)' }}>
                <span
                  className="text-[11px] font-bold uppercase tracking-widest"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  知识闭环动作执行记录
                </span>
                <p className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  直接更换为更新批期的增强型 <span className="font-mono text-xs">8GB-DDR4-HYNX</span> ，并同步重刷微控制器总线电压阈值容错固件策略，成功闭环通过极限循环压力测试验证。
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}