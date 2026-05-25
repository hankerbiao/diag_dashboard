import { Bot, Activity, AlertTriangle, Wrench, ExternalLink } from 'lucide-react';

interface DiagnosisResultProps {
  sn: string;
}

export default function DiagnosisResult({ sn }: DiagnosisResultProps) {
  return (
    <div
      className="w-[55%] border-r flex flex-col shrink-0 min-h-0 relative"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div className="p-8 flex-1 overflow-y-auto w-full mx-auto flex flex-col gap-8 custom-scrollbar">
        <div className="flex items-start gap-4">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0"
            style={{
              background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
              boxShadow: '0 4px 12px -2px rgba(59, 130, 246, 0.4)',
            }}
          >
            <Bot className="w-5 h-5" />
          </div>
          <div className="flex-1 space-y-5 mt-1">
            <div
              className="p-5 rounded-2xl text-sm leading-relaxed shadow-sm border"
              style={{
                backgroundColor: 'var(--color-bg-primary)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            >
              针对序列号{' '}
              <strong
                className="font-mono px-1 py-0.5 rounded shadow-sm"
                style={{
                  backgroundColor: 'var(--color-accent-light)',
                  color: 'var(--color-accent)',
                }}
              >
                {sn}
              </strong>{' '}
              的图谱推理分析已完成。我已交叉比对{' '}
              <strong>SIMS测试日志</strong> 与 <strong>2023年6月至8月的历史维修记录</strong>，并调用了相应的故障知识经验库。
            </div>

            <div className="space-y-3">
              <h3
                className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                <Activity className="w-4 h-4 text-amber-500" /> 智能诊断结果
              </h3>
              <div
                className="p-5 border rounded-2xl shadow-sm relative overflow-hidden"
                style={{
                  background: 'linear-gradient(135deg, rgba(254, 243, 199, 0.8), rgba(254, 226, 154, 0.3))',
                  borderColor: 'rgba(251, 191, 36, 0.3)',
                  color: '#92400e',
                }}
              >
                <div
                  className="absolute top-0 right-0 px-3 py-1 text-white rounded-bl-xl text-[10px] font-bold shadow-sm"
                  style={{ backgroundColor: '#f59e0b' }}
                >
                  置信度: 92%
                </div>
                <div className="flex items-center gap-2 font-bold mb-3 text-[15px]">
                  <AlertTriangle className="w-5 h-5 text-amber-500" /> 告警代码: MEM_FAIL_0x822
                </div>
                <p className="text-[13px] leading-relaxed opacity-90">
                  基于近因图谱聚类分析，<strong>DIMM插槽 4</strong> 发生结构性硬件故障的概率极高。此失效模式与生产监控所暴露的{' '}
                  <strong>批次 #8821</strong> 高度共振，该批料件近期在高温负荷下多次发生电压离散跳动特征。
                </p>
              </div>
            </div>

            <div className="space-y-3 pt-2">
              <h3
                className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                <Wrench className="w-4 h-4 text-emerald-500" /> 标准推荐排障协议
              </h3>
              <ul className="space-y-3">
                <li
                  className="flex items-start gap-4 text-[13px] p-4 rounded-xl border shadow-sm transition-colors"
                  style={{
                    backgroundColor: 'var(--color-bg-secondary)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  <span
                    className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 shadow-sm"
                    style={{
                      backgroundColor: 'rgba(16, 185, 129, 0.1)',
                      color: '#059669',
                    }}
                  >
                    1
                  </span>
                  <div className="flex-1 space-y-2">
                    <span className="block font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      执行硬件 ECC 寄存器清除命令：
                    </span>
                    <div
                      className="rounded-lg p-2.5 flex justify-between items-center group"
                      style={{ backgroundColor: '#1e293b' }}
                    >
                      <code className="text-emerald-400 font-mono text-xs tracking-wider">
                        diag --clear-ecc-error 0x4
                      </code>
                      <button
                        className="text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity text-[10px] px-2 py-0.5 rounded uppercase"
                        style={{ backgroundColor: '#334155' }}
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                </li>
                <li
                  className="flex items-center gap-4 text-[13px] p-4 rounded-xl border shadow-sm transition-colors"
                  style={{
                    backgroundColor: 'var(--color-bg-secondary)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  <span
                    className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 shadow-sm"
                    style={{
                      backgroundColor: 'var(--color-bg-primary)',
                      color: 'var(--color-text-secondary)',
                    }}
                  >
                    2
                  </span>
                  <div>
                    执行物理更换动作，标准部件料号定位:{' '}
                    <span
                      className="font-mono font-semibold px-2 py-1 rounded-md ml-1 shadow-sm border"
                      style={{
                        backgroundColor: 'var(--color-bg-primary)',
                        borderColor: 'var(--color-border)',
                        color: 'var(--color-text-primary)',
                      }}
                    >
                      8GB-DDR4-HYNX
                    </span>
                  </div>
                </li>
                <li
                  className="flex items-center gap-4 text-[13px] p-4 rounded-xl border shadow-sm transition-colors"
                  style={{
                    backgroundColor: 'var(--color-bg-secondary)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  <span
                    className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 shadow-sm"
                    style={{
                      backgroundColor: 'var(--color-bg-primary)',
                      color: 'var(--color-text-secondary)',
                    }}
                  >
                    3
                  </span>
                  <div>
                    复测验证，向自动化测试框架推送 Diag 强化测试项:{' '}
                    <span
                      className="font-medium cursor-pointer underline-offset-4 ml-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-md border"
                      style={{
                        color: 'var(--color-accent)',
                        backgroundColor: 'var(--color-accent-light)',
                        borderColor: 'var(--color-accent)',
                      }}
                    >
                      MEM_STRESS_T2 <ExternalLink className="w-3 h-3" />
                    </span>
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </div>
        <div className="h-4 shrink-0" />
      </div>
    </div>
  );
}