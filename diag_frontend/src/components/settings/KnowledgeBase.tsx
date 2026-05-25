import { Database, CheckCircle2 } from 'lucide-react';
import type { AppSettings } from '../../types';

interface KnowledgeBaseProps {
  settings: AppSettings;
  onToggleKB: (kb: string) => void;
}

const KNOWLEDGE_BASES = [
  {
    id: 'MES',
    name: 'MES 生产制造管网',
    description: '接入底层工厂执行系统接口簇，毫秒级同步设备当期流转路由、工艺过站记录及全生命周期维护动作。',
  },
  {
    id: 'SIMS',
    name: 'SIMS 自动化测试系统',
    description: '贯通测试节点底层堆栈，捕获全部自动化执行脚本异常断点报错及拦截上下文档案序列。',
  },
  {
    id: 'Case Library',
    name: '历史缺陷图谱库',
    description: '高维抽象聚类沉淀缺陷根因拓扑与维修策略库，作为大模型知识推理链路中最强势效仿证据链提供方。',
  },
];

export default function KnowledgeBase({ settings, onToggleKB }: KnowledgeBaseProps) {
  return (
    <div
      className="rounded-xl shadow-sm overflow-hidden"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        border: '1px solid var(--color-border)',
      }}
    >
      <div
        className="border-b px-6 py-4 flex items-center gap-3"
        style={{
          backgroundColor: 'var(--color-bg-primary)',
          borderColor: 'var(--color-border)',
        }}
      >
        <Database className="w-5 h-5" style={{ color: 'var(--color-accent)' }} />
        <h2 className="text-base font-bold flex items-center" style={{ color: 'var(--color-text-primary)' }}>
          知识库挂载总线
        </h2>
        <span className="ml-2 text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
          配置激活状态池，融入大模型诊断决策推演链路
        </span>
      </div>

      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {KNOWLEDGE_BASES.map((kb) => {
            const isActive = settings.activeKBs.includes(kb.id);
            return (
              <label
                key={kb.id}
                className={`flex flex-col gap-2 p-5 border-2 rounded-xl cursor-pointer transition-all ${
                  isActive ? 'transform scale-[1.02]' : ''
                }`}
                style={
                  isActive
                    ? {
                        backgroundColor: 'var(--color-accent-light)',
                        borderColor: 'var(--color-accent)',
                        boxShadow: '0 4px 12px -2px var(--color-shadow)',
                      }
                    : {
                        backgroundColor: 'var(--color-bg-secondary)',
                        borderColor: 'var(--color-border)',
                      }
                }
                onClick={() => onToggleKB(kb.id)}
              >
                <div className="flex justify-between items-start mb-2">
                  <div
                    className="flex items-center gap-3 text-sm font-bold tracking-wide"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    <span
                      className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors ${
                        isActive ? '' : ''
                      }`}
                      style={
                        isActive
                          ? {
                              backgroundColor: 'var(--color-accent)',
                              borderColor: 'var(--color-accent)',
                            }
                          : {
                              borderColor: 'var(--color-border)',
                              backgroundColor: 'var(--color-bg-secondary)',
                            }
                      }
                    >
                      {isActive && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                    </span>
                    {kb.name}
                  </div>
                </div>
                <div
                  className="text-[12px] leading-relaxed pl-8"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {kb.description}
                </div>
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}