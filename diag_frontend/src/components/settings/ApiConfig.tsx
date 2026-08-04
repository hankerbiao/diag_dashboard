import { useState, useEffect, useImperativeHandle, forwardRef, type ReactNode } from 'react';
import { Activity, Brain, CheckCircle2, Clock, Gauge, Key, Layers, Link2, Loader2, Sliders, Thermometer, XCircle, Zap } from 'lucide-react';
import { settingsApi, type AiConfigDraft, type AiConnectivityResult, type RuntimeConfig } from '../../api/fastapi';

export interface ApiConfigHandle {
  save: () => Promise<boolean>;
}

interface ApiConfigProps {
  onErrorMessage?: (msg: string) => void;
  onSuccessMessage?: (msg: string) => void;
}

interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: 'text' | 'password';
  icon?: ReactNode;
}

interface NumberFieldProps {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  placeholder?: string;
  min?: number;
  icon?: ReactNode;
}

const inputStyle = {
  borderColor: 'var(--color-border)',
  backgroundColor: 'var(--color-bg-primary)',
  color: 'var(--color-text-primary)',
};

const labelStyle = { color: 'var(--color-text-primary)' };
const mutedStyle = { color: 'var(--color-text-muted)' };

function TextField({ label, value, onChange, placeholder, type = 'text', icon }: TextFieldProps) {
  return (
    <label className="block space-y-2">
      <span className="text-xs font-bold" style={labelStyle}>
        {label}
      </span>
      <span className="relative block">
        {icon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--color-text-secondary)' }}>
            {icon}
          </span>
        )}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`h-10 w-full rounded-lg border px-3 text-sm font-mono outline-none transition focus:border-blue-400 ${
            icon ? 'pl-9' : ''
          }`}
          style={inputStyle}
          placeholder={placeholder}
        />
      </span>
    </label>
  );
}

function NumberField({ label, value, onChange, placeholder, min = 1, icon }: NumberFieldProps) {
  return (
    <label className="block space-y-2">
      <span className="flex items-center justify-between gap-3 text-xs font-bold" style={labelStyle}>
        <span className="inline-flex items-center gap-1.5">
          {icon}
          {label}
        </span>
        <span className="rounded px-2 py-0.5 font-mono text-[11px]" style={{ backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)' }}>
          {value !== null ? value.toLocaleString() : '默认'}
        </span>
      </span>
      <input
        type="number"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value ? Math.max(min, parseInt(e.target.value) || 0) : null)}
        className="h-10 w-full rounded-lg border px-3 text-sm font-mono outline-none transition focus:border-blue-400"
        style={inputStyle}
        min={min}
        placeholder={placeholder}
      />
    </label>
  );
}

function SectionTitle({ icon, title, description, badge }: { icon: ReactNode; title: string; description: string; badge?: string }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--color-accent)' }}>{icon}</span>
          <h3 className="text-sm font-bold" style={labelStyle}>
            {title}
          </h3>
        </div>
        <p className="mt-1 text-xs leading-5" style={mutedStyle}>
          {description}
        </p>
      </div>
      {badge && (
        <span
          className="w-fit shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-bold"
          style={{ color: 'var(--color-accent)', borderColor: 'var(--color-accent)', backgroundColor: 'var(--color-accent-light)' }}
        >
          {badge}
        </span>
      )}
    </div>
  );
}

const ApiConfig = forwardRef<ApiConfigHandle, ApiConfigProps>(
  ({ onErrorMessage, onSuccessMessage }, ref) => {
    const [apiKey, setApiKey] = useState('');
    const [baseUrl, setBaseUrl] = useState('');
    const [model, setModel] = useState('');
    const [temperature, setTemperature] = useState<number | null>(null);
    const [enableThinking, setEnableThinking] = useState(false);
    const [timeout, setTimeout_] = useState<number | null>(null);
    const [extractionApiKey, setExtractionApiKey] = useState('');
    const [extractionBaseUrl, setExtractionBaseUrl] = useState('');
    const [extractionModel, setExtractionModel] = useState('');
    const [extractionTimeout, setExtractionTimeout] = useState<number | null>(null);
    const [perRequestConcurrency, setPerRequestConcurrency] = useState<number | null>(null);
    const [globalConcurrency, setGlobalConcurrency] = useState<number | null>(null);
    const [runtimeDefaults, setRuntimeDefaults] = useState<RuntimeConfig | null>(null);

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [testResults, setTestResults] = useState<AiConnectivityResult[]>([]);

    useEffect(() => {
      settingsApi.getAiConfig().then((resp) => {
        if (resp.success && resp.data) {
          setApiKey(resp.data.api_key);
          setBaseUrl(resp.data.base_url || '');
          setModel(resp.data.model || '');
          setTemperature(resp.data.temperature);
          setEnableThinking(resp.data.chat_template_kwargs?.enable_thinking ?? false);
          setTimeout_(resp.data.timeout);
          setExtractionApiKey(resp.data.extraction_api_key || '');
          setExtractionBaseUrl(resp.data.extraction_base_url || '');
          setExtractionModel(resp.data.extraction_model || '');
          setExtractionTimeout(resp.data.extraction_timeout);
        }
      }).catch(() => {
        onErrorMessage?.('AI 配置加载失败，已使用默认空配置');
      }).finally(() => setLoading(false));

      settingsApi.getRuntimeConfig().then((resp) => {
        if (resp.success && resp.data) {
          setPerRequestConcurrency(resp.data.config.per_request_concurrency);
          setGlobalConcurrency(resp.data.config.global_concurrency);
          setRuntimeDefaults(resp.data.defaults);
        }
      }).catch(() => {
        // 并发配置加载失败不阻塞主表单
      });
    }, [onErrorMessage]);

    const buildConfigDraft = (): AiConfigDraft => {
      const body: AiConfigDraft = {
        api_key: apiKey,
        base_url: baseUrl,
        model,
        chat_template_kwargs: { enable_thinking: enableThinking },
        extraction_api_key: extractionApiKey,
        extraction_base_url: extractionBaseUrl,
        extraction_model: extractionModel,
      };
      if (temperature !== null) body.temperature = temperature;
      if (timeout !== null) body.timeout = timeout;
      if (extractionTimeout !== null) body.extraction_timeout = extractionTimeout;
      return body;
    };

    const handleTestConnection = async () => {
      if (testing) return;
      setTesting(true);
      setTestResults([]);
      try {
        const resp = await settingsApi.testAiConfig(buildConfigDraft());
        if (!resp.success || !resp.data) {
          onErrorMessage?.(resp.error || '模型连接测试失败');
          return;
        }
        setTestResults(resp.data.results);
        if (resp.data.all_connected) {
          onSuccessMessage?.('模型服务连接正常');
        } else {
          onErrorMessage?.('部分模型服务连接失败，请检查测试结果');
        }
      } catch {
        onErrorMessage?.('网络错误，无法测试模型连接');
      } finally {
        setTesting(false);
      }
    };

    useImperativeHandle(ref, () => ({
      save: async () => {
        setSaving(true);
        try {
          const resp = await settingsApi.updateAiConfig(buildConfigDraft());
          if (!resp.success) {
            onErrorMessage?.(resp.error || '保存失败');
            return false;
          }
          // 并发配置：加载成功才提交；本地先校验 global >= per_request
          if (perRequestConcurrency !== null && globalConcurrency !== null) {
            if (globalConcurrency < perRequestConcurrency) {
              onErrorMessage?.('全局并发上限不能小于单请求并发');
              return false;
            }
            const runtimeResp = await settingsApi.updateRuntimeConfig({
              per_request_concurrency: perRequestConcurrency,
              global_concurrency: globalConcurrency,
            });
            if (!runtimeResp.success) {
              onErrorMessage?.(runtimeResp.error || '并发配置保存失败');
              return false;
            }
          }
          onSuccessMessage?.('AI 大模型配置已更新');
          return true;
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
        <section
          className="rounded-lg border p-6"
          style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
        >
          <div className="flex items-center justify-center gap-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            <Loader2 className="h-5 w-5 animate-spin" />
            加载配置中...
          </div>
        </section>
      );
    }

    const extractionReused = !extractionBaseUrl && !extractionApiKey;

    return (
      <section
        className="overflow-hidden rounded-lg border"
        style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
      >
        <div className="flex flex-col gap-3 border-b px-4 py-4 sm:px-5 md:flex-row md:items-center md:justify-between" style={{ borderColor: 'var(--color-border)' }}>
          <div>
            <div className="flex items-center gap-2">
              <Sliders className="h-5 w-5" style={{ color: 'var(--color-accent)' }} />
              <h2 className="text-base font-bold" style={labelStyle}>
                AI 模型配置
              </h2>
            </div>
            <p className="mt-1 text-xs" style={mutedStyle}>
              主模型负责诊断结论，提取模型负责日志预处理。
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            {saving && (
              <span className="inline-flex items-center gap-2 text-xs font-bold" style={{ color: 'var(--color-accent)' }}>
                <Loader2 className="h-4 w-4 animate-spin" />
                保存中
              </span>
            )}
            <button
              type="button"
              onClick={() => void handleTestConnection()}
              disabled={testing || saving}
              className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-bold disabled:opacity-50"
              style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)', color: 'var(--color-text-secondary)' }}
            >
              {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
              {testing ? '正在测试' : '测试模型连接'}
            </button>
          </div>
        </div>

        {testResults.length > 0 && (
          <div className="grid border-b sm:grid-cols-2" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}>
            {testResults.map((result) => (
              <div key={result.service} className="flex min-w-0 items-start gap-3 border-b px-5 py-3 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0" style={{ borderColor: 'var(--color-border)' }}>
                {result.success
                  ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-bold">
                    <span>{result.label}</span>
                    {result.reused_answer && <span className="text-[10px] font-normal" style={mutedStyle}>复用主模型</span>}
                    {result.success && result.latency_ms !== undefined && <span className="font-mono text-[10px] text-emerald-600">{result.latency_ms} ms</span>}
                  </div>
                  <div className="mt-1 truncate font-mono text-[10px]" style={mutedStyle} title={`${result.model} · ${result.base_url}`}>
                    {result.model || '未配置模型'} · {result.base_url || '未配置地址'}
                  </div>
                  {!result.success && <div className="mt-1 break-words text-[10px] text-red-600">{result.error || '连接失败'}</div>}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="space-y-7 p-4 sm:p-5">
          <div className="space-y-4">
            <SectionTitle
              icon={<Brain className="h-4 w-4" />}
              title="诊断回答模型"
              description="建议选择推理能力更强的模型，用于根因分析和维修建议生成。"
              badge="OpenAI 兼容"
            />
            <div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              <TextField label="Base URL" value={baseUrl} onChange={setBaseUrl} placeholder="https://api.openai.com/v1" icon={<Link2 className="h-4 w-4" />} />
              <TextField label="API Key" value={apiKey} onChange={setApiKey} placeholder="sk-xxxxxxxx" type="password" icon={<Key className="h-4 w-4" />} />
              <TextField label="Model ID" value={model} onChange={setModel} placeholder="deepseek-reasoner" />
            </div>
          </div>

          <div className="space-y-4 border-t pt-5" style={{ borderColor: 'var(--color-border)' }}>
            <SectionTitle
              icon={<Zap className="h-4 w-4" />}
              title="日志提取模型"
              description="留空时复用诊断回答模型，单模型部署时无需重复填写。"
              badge={extractionReused ? '复用主模型' : '独立配置'}
            />
            <div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              <TextField label="Base URL" value={extractionBaseUrl} onChange={setExtractionBaseUrl} placeholder="留空复用主模型" icon={<Link2 className="h-4 w-4" />} />
              <TextField label="API Key" value={extractionApiKey} onChange={setExtractionApiKey} placeholder="留空复用主模型" type="password" icon={<Key className="h-4 w-4" />} />
              <TextField label="Model ID" value={extractionModel} onChange={setExtractionModel} placeholder="gpt-4o-mini / deepseek-chat" />
            </div>
          </div>

          <div className="grid min-w-0 grid-cols-1 gap-4 border-t pt-5 sm:grid-cols-2" style={{ borderColor: 'var(--color-border)' }}>
            <NumberField label="诊断超时秒数" value={timeout} onChange={setTimeout_} placeholder="300" min={10} icon={<Clock className="h-3.5 w-3.5" />} />
            <NumberField label="提取超时秒数" value={extractionTimeout} onChange={setExtractionTimeout} placeholder="300" min={10} icon={<Clock className="h-3.5 w-3.5" />} />
          </div>

          <div className="grid min-w-0 grid-cols-1 gap-5 border-t pt-5 xl:grid-cols-[minmax(0,1fr)_240px]" style={{ borderColor: 'var(--color-border)' }}>
            <label className="block space-y-3">
              <span className="flex items-center justify-between gap-3 text-xs font-bold" style={labelStyle}>
                <span className="inline-flex items-center gap-1.5">
                  <Thermometer className="h-3.5 w-3.5" />
                  Temperature
                </span>
                <span className="rounded px-2 py-0.5 font-mono text-[11px]" style={{ backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)' }}>
                  {temperature !== null ? temperature.toFixed(2) : '默认'}
                </span>
              </span>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={temperature ?? 0.7}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full outline-none"
                style={{ accentColor: 'var(--color-accent)' }}
              />
            </label>

            <div
              className="flex items-center justify-between gap-4 rounded-lg border px-4 py-3"
              style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}
            >
              <div>
                <div className="text-xs font-bold" style={labelStyle}>
                  深度思考
                </div>
                <div className="mt-1 text-[11px]" style={mutedStyle}>
                  {enableThinking ? '已开启' : '已关闭'}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setEnableThinking((v) => !v)}
                className="relative h-6 w-11 rounded-full transition"
                style={{ backgroundColor: enableThinking ? 'var(--color-accent)' : 'var(--color-border)' }}
                aria-pressed={enableThinking}
                aria-label="切换深度思考模式"
              >
                <span
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                    enableThinking ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
          </div>

          <div className="space-y-4 border-t pt-5" style={{ borderColor: 'var(--color-border)' }}>
            <SectionTitle
              icon={<Gauge className="h-4 w-4" />}
              title="日志提取并发"
              description="控制日志分段并行调用提取模型的数量。保存后对进行中的诊断从下一请求开始实时生效。"
              badge="实时生效"
            />
            <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2">
              <NumberField
                label="单请求并发"
                value={perRequestConcurrency}
                onChange={setPerRequestConcurrency}
                placeholder={String(runtimeDefaults?.per_request_concurrency ?? 8)}
                min={1}
                icon={<Layers className="h-3.5 w-3.5" />}
              />
              <NumberField
                label="全局并发上限"
                value={globalConcurrency}
                onChange={setGlobalConcurrency}
                placeholder={String(runtimeDefaults?.global_concurrency ?? 16)}
                min={1}
                icon={<Gauge className="h-3.5 w-3.5" />}
              />
            </div>
            <p className="text-[11px] leading-5" style={mutedStyle}>
              全局上限为所有诊断请求共享的进程级并发，需 ≥ 单请求并发；调大可缩短大批量诊断耗时，但会提高提取模型的限流风险。
            </p>
          </div>
        </div>
      </section>
    );
  }
);

ApiConfig.displayName = 'ApiConfig';
export default ApiConfig;
