import { useState, useEffect, useImperativeHandle, forwardRef } from 'react';
import { Sliders, Key, Loader2, CheckCircle2, AlertCircle, Cpu, Brain, Clock } from 'lucide-react';
import { settingsApi } from '../../api/fastapi';

export interface ApiConfigHandle {
  save: () => Promise<boolean>;
}

interface ApiConfigProps {
  onErrorMessage?: (msg: string) => void;
  onSuccessMessage?: (msg: string) => void;
}

const ApiConfig = forwardRef<ApiConfigHandle, ApiConfigProps>(
  ({ onErrorMessage, onSuccessMessage }, ref) => {
    const [apiKey, setApiKey] = useState('');
    const [baseUrl, setBaseUrl] = useState('');
    const [model, setModel] = useState('');
    const [temperature, setTemperature] = useState<number | null>(null);
    const [maxTokens, setMaxTokens] = useState<number | null>(null);
    const [enableThinking, setEnableThinking] = useState(false);
    const [timeout, setTimeout_] = useState<number | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // 挂载时从 API 加载当前配置
    useEffect(() => {
      settingsApi.getAiConfig().then((resp) => {
        if (resp.success && resp.data) {
          setApiKey(resp.data.api_key);
          setBaseUrl(resp.data.base_url || '');
          setModel(resp.data.model || '');
          setTemperature(resp.data.temperature);
          setMaxTokens(resp.data.max_tokens);
          setEnableThinking(resp.data.chat_template_kwargs?.enable_thinking ?? false);
          setTimeout_(resp.data.timeout);
        }
      }).catch(() => {
        // 保持默认值
      }).finally(() => setLoading(false));
    }, []);

    // 暴露 save 方法给父组件
    useImperativeHandle(ref, () => ({
      save: async () => {
        setSaving(true);
        try {
          const body: Record<string, unknown> = {
            api_key: apiKey,
            base_url: baseUrl,
            model,
          };
          if (temperature !== null) body.temperature = temperature;
          if (maxTokens !== null) body.max_tokens = maxTokens;
          if (timeout !== null) body.timeout = timeout;
          body.chat_template_kwargs = { enable_thinking: enableThinking };
          const resp = await settingsApi.updateAiConfig(body as any);
          if (resp.success) {
            onSuccessMessage?.('AI 大模型配置已更新');
            return true;
          }
          onErrorMessage?.(resp.error || '保存失败');
          return false;
        } catch {
          onErrorMessage?.('网络错误，保存失败');
          return false;
        } finally {
          setSaving(false);
        }
      },
    }));

    if (loading) {
      return (
        <div
          className="rounded-xl shadow-sm overflow-hidden"
          style={{
            backgroundColor: 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div className="p-6 flex items-center justify-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span style={{ color: 'var(--color-text-secondary)' }}>加载配置中...</span>
          </div>
        </div>
      );
    }

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
          <h2 className="text-base font-bold flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
            AI 大模型中枢引擎配置
            <span
              className="text-[10px] font-bold px-2 py-0.5 rounded-md border flex items-center gap-1"
              style={{
                color: 'var(--color-accent)',
                borderColor: 'var(--color-accent)',
                backgroundColor: 'var(--color-accent-light)',
              }}
            >
              <Cpu className="w-3 h-3" />
              海光DCU
            </span>
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
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
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
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
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
                value={model}
                onChange={(e) => setModel(e.target.value)}
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
                <span>上下文 Token 上限</span>
                <span
                  className="font-mono font-bold px-2.5 py-0.5 rounded text-xs"
                  style={{
                    backgroundColor: 'var(--color-accent-light)',
                    color: 'var(--color-accent)',
                  }}
                >
                  {maxTokens !== null ? maxTokens.toLocaleString() : '—'}
                </span>
              </label>
              <input
                type="number"
                value={maxTokens ?? ''}
                onChange={(e) => setMaxTokens(e.target.value ? Math.max(1, parseInt(e.target.value) || 0) : null)}
                className="w-full h-11 border rounded-lg px-4 text-sm outline-none transition-all shadow-sm font-mono"
                style={{
                  borderColor: 'var(--color-border)',
                  backgroundColor: 'var(--color-bg-primary)',
                  color: 'var(--color-text-primary)',
                }}
                min={1}
                placeholder="28000"
              />
              <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                超过上限的日志和知识库内容将被自动截断。建议设为模型最大上下文 - 4096。
              </p>
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
                  {temperature !== null ? temperature.toFixed(2) : '—'}
                </span>
              </label>
              <div className="flex items-center gap-4 h-11">
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={temperature ?? 0.7}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="flex-1 outline-none"
                  style={{ accentColor: 'var(--color-accent)' }}
                />
              </div>
            </div>
          </div>

          <div
            className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-6 border-t"
            style={{ borderColor: 'var(--color-border)' }}
          >
            <div className="space-y-3">
              <label
                className="flex items-center gap-2 text-[13px] font-bold tracking-wide"
                style={{ color: 'var(--color-text-primary)' }}
              >
                <Brain className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />
                深度思考模式
              </label>
              <label
                className="relative inline-flex items-center cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={enableThinking}
                  onChange={(e) => setEnableThinking(e.target.checked)}
                  className="sr-only peer"
                />
                <div
                  className="w-11 h-6 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"
                  style={{
                    backgroundColor: enableThinking ? 'var(--color-accent)' : 'var(--color-border)',
                  }}
                ></div>
                <span
                  className="ms-3 text-sm font-medium"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {enableThinking ? '开启' : '关闭'}
                </span>
              </label>
              <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                开启后模型会展示思考过程，关闭可加快响应速度并减少 Token 消耗
              </p>
            </div>

            <div className="space-y-2">
              <label
                className="flex items-center gap-2 text-[13px] font-bold tracking-wide"
                style={{ color: 'var(--color-text-primary)' }}
              >
                <Clock className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />
                请求超时时间 (秒)
              </label>
              <input
                type="number"
                value={timeout ?? ''}
                onChange={(e) => setTimeout_(e.target.value ? Math.max(10, parseInt(e.target.value) || 0) : null)}
                className="w-full h-11 border rounded-lg px-4 text-sm outline-none transition-all shadow-sm font-mono"
                style={{
                  borderColor: 'var(--color-border)',
                  backgroundColor: 'var(--color-bg-primary)',
                  color: 'var(--color-text-primary)',
                }}
                min={10}
                placeholder="300"
              />
              <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                建议 60-600 秒，模型推理时间较长时可适当增加
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }
);

ApiConfig.displayName = 'ApiConfig';
export default ApiConfig;