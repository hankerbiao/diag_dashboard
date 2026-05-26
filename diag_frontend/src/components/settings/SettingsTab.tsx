import { CheckCircle2 } from 'lucide-react';
import type { Dispatch, SetStateAction } from 'react';
import type { AppSettings } from '../../types';
import ApiConfig from './ApiConfig';
import KnowledgeBase from './KnowledgeBase';

interface SettingsTabProps {
  settings: AppSettings;
  setSettings: Dispatch<SetStateAction<AppSettings>>;
}

export default function SettingsTab({ settings, setSettings }: SettingsTabProps) {
  const toggleKB = (kb: string) => {
    setSettings((prev) => {
      if (prev.activeKBs.includes(kb) && prev.activeKBs.length <= 1) {
        return prev; // 至少保留一个知识库
      }
      return {
        ...prev,
        activeKBs: prev.activeKBs.includes(kb) ? prev.activeKBs.filter((k) => k !== kb) : [...prev.activeKBs, kb],
      };
    });
  };

  const handleSettingsChange = (changes: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...changes }));
  };

  return (
    <div
      className="flex-1 overflow-y-auto p-6 lg:p-10 flex justify-center custom-scrollbar"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <div className="w-full max-w-4xl space-y-8 pb-12">
        <ApiConfig settings={settings} onSettingsChange={handleSettingsChange} />
        <KnowledgeBase settings={settings} onToggleKB={toggleKB} />

        <div
          className="flex justify-end gap-4 pt-6"
          style={{ borderTop: '1px solid var(--color-border)' }}
        >
          <button
            className="px-6 py-2.5 font-bold text-[13px] rounded-lg transition-colors shadow-sm"
            style={{
              backgroundColor: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-secondary)',
            }}
          >
            放弃更改
          </button>
          <button
            className="px-6 py-2.5 text-white font-bold text-[13px] rounded-lg transition-colors shadow-sm flex items-center gap-2 active:scale-95"
            style={{
              backgroundColor: 'var(--color-accent)',
              boxShadow: '0 4px 6px -1px var(--color-shadow)',
            }}
          >
            <CheckCircle2 className="w-4 h-4" /> 应用全局配置
          </button>
        </div>
      </div>
    </div>
  );
}