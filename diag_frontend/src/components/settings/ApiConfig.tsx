import { Sliders, Key } from 'lucide-react';
import type { AppSettings } from '../../types';

interface ApiConfigProps {
  settings: AppSettings;
  onSettingsChange: (settings: Partial<AppSettings>) => void;
}

export default function ApiConfig({ settings, onSettingsChange }: ApiConfigProps) {
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
        <Sliders className="w-5 h-5" style={{ color: 'var(--color-accent)' }} />
        <h2 className="text-base font-bold" style={{ color: 'var(--color-text-primary)' }}>
          AI 大模型中枢引擎配置
        </h2>
        <span
          className="ml-auto text-[11px] font-bold px-2.5 py-1 rounded-full uppercase tracking-widest"
          style={{
            backgroundColor: 'var(--color-accent-light)',
            color: 'var(--color-accent)',
            border: '1px solid var(--color-accent)',
          }}
        >
          OpenAI 兼容协议组
        </span>
      </div>

      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <label
              className="block text-[13px] font-bold tracking-wide"
              style={{ color: 'var(--color-text-primary)' }}
            >
              接口网关地址 (Base URL)
            </label>
            <input
              type="text"
              value={settings.aiApiUrl}
              onChange={(e) => onSettingsChange({ aiApiUrl: e.target.value })}
              className="w-full h-11 border rounded-lg px-4 text-sm outline-none transition-all shadow-sm font-mono"
              style={{
                borderColor: 'var(--color-border)',
                backgroundColor: 'var(--color-bg-primary)',
                color: 'var(--color-text-primary)',
              }}
              placeholder="https://api.openai.com/v1"
            />
          </div>

          <div className="space-y-2">
            <label
              className="block text-[13px] font-bold tracking-wide"
              style={{ color: 'var(--color-text-primary)' }}
            >
              鉴权密钥 (API Key)
            </label>
            <div className="relative">
              <input
                type="password"
                value={settings.aiApiKey}
                onChange={(e) => onSettingsChange({ aiApiKey: e.target.value })}
                className="w-full h-11 border rounded-lg pl-10 pr-4 text-sm outline-none transition-all shadow-sm font-mono"
                style={{
                  borderColor: 'var(--color-border)',
                  backgroundColor: 'var(--color-bg-primary)',
                  color: 'var(--color-text-primary)',
                }}
                placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
              />
              <Key
                className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2"
                style={{ color: 'var(--color-text-secondary)' }}
              />
            </div>
          </div>
        </div>

        <div
          className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-6 border-t"
          style={{ borderColor: 'var(--color-border)' }}
        >
          <div className="space-y-2">
            <label
              className="block text-[13px] font-bold tracking-wide"
              style={{ color: 'var(--color-text-primary)' }}
            >
              指定推理核心 (Model ID)
            </label>
            <input
              type="text"
              value={settings.aiModel}
              onChange={(e) => onSettingsChange({ aiModel: e.target.value })}
              className="w-full h-11 border rounded-lg px-4 text-sm outline-none transition-all shadow-sm font-mono"
              style={{
                borderColor: 'var(--color-border)',
                backgroundColor: 'var(--color-bg-primary)',
                color: 'var(--color-text-primary)',
              }}
              placeholder="gpt-4-turbo"
            />
          </div>

          <div className="space-y-2">
            <label
              className="flex items-center justify-between text-[13px] font-bold tracking-wide"
              style={{ color: 'var(--color-text-primary)' }}
            >
              <span>推理发散阈值 (Temperature)</span>
              <span
                className="font-mono font-bold px-2.5 py-0.5 rounded text-xs"
                style={{
                  backgroundColor: 'var(--color-accent-light)',
                  color: 'var(--color-accent)',
                }}
              >
                {settings.aiTemperature.toFixed(2)}
              </span>
            </label>
            <div className="flex items-center gap-4 h-11">
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={settings.aiTemperature}
                onChange={(e) => onSettingsChange({ aiTemperature: parseFloat(e.target.value) })}
                className="flex-1 outline-none"
                style={{ accentColor: 'var(--color-accent)' }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}