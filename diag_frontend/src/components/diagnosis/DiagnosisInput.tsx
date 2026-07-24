import type { KeyboardEvent } from 'react';
import { ArrowRight, Bot, Building2, ChevronDown, Loader2, Search, X } from 'lucide-react';
import type { FactorySite } from '../../api/fastapi';

interface DiagnosisInputProps {
  sn: string;
  factory: string;
  factorySites: FactorySite[];
  factoryReady: boolean;
  onFactoryChange: (factoryId: string) => void;
  onSnChange: (sn: string) => void;
  onDiagnose: () => void;
  loading: boolean;
  onKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  centered?: boolean;
}

export default function DiagnosisInput({
  sn,
  factory,
  factorySites,
  factoryReady,
  onFactoryChange,
  onSnChange,
  onDiagnose,
  loading,
  onKeyDown,
  centered = false,
}: DiagnosisInputProps) {
  const canSubmit = factoryReady && Boolean(sn.trim()) && !loading;
  const controlStyle = {
    backgroundColor: 'var(--color-bg-secondary)',
    borderColor: 'var(--color-border)',
    color: 'var(--color-text-primary)',
  };

  if (centered) {
    return (
      <div className="grid w-full gap-4 lg:grid-cols-[160px_minmax(200px,1fr)_132px] lg:items-end xl:grid-cols-[180px_minmax(220px,1fr)_140px]">
        <label className="block min-w-0">
          <span className="mb-2 block text-[12px] font-semibold" style={{ color: 'var(--color-text-secondary)' }}>运行厂区</span>
          <span className="relative block">
            <Building2 className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
            <select
              value={factory}
              onChange={(event) => onFactoryChange(event.target.value)}
              disabled={loading || factorySites.length === 0}
              className="h-13 w-full appearance-none rounded-md border pl-11 pr-10 text-[13px] font-semibold outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50"
              style={controlStyle}
            >
              {factorySites.length === 0 && <option value="">厂区加载中</option>}
              {factorySites.map((site) => (
                <option key={site.factory_id} value={site.factory_id}>{site.name}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
          </span>
        </label>

        <label className="block min-w-0">
          <span className="mb-2 block text-[12px] font-semibold" style={{ color: 'var(--color-text-secondary)' }}>设备 SN</span>
          <span className="relative block">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
            <input
              type="text"
              value={sn}
              onChange={(event) => onSnChange(event.target.value)}
              onKeyDown={onKeyDown}
              autoFocus
              aria-label="设备 SN"
              autoComplete="off"
              spellCheck={false}
              className="h-13 w-full rounded-md border pl-11 pr-11 font-mono text-[15px] font-semibold outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              style={controlStyle}
              placeholder="输入设备序列号"
            />
            {sn && !loading && (
              <button
                type="button"
                onClick={() => onSnChange('')}
                className="absolute right-2.5 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md hover:bg-black/5"
                style={{ color: 'var(--color-text-muted)' }}
                aria-label="清空设备 SN"
                title="清空"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </span>
        </label>

        <button
          type="button"
          onClick={onDiagnose}
          disabled={!canSubmit}
          className="inline-flex h-13 w-full items-center justify-center gap-2 whitespace-nowrap rounded-md bg-blue-600 px-5 text-[13px] font-bold text-white shadow-sm transition hover:bg-blue-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
          {loading ? '诊断中' : '开始诊断'}
          {!loading && <ArrowRight className="h-4 w-4" />}
        </button>
      </div>
    );
  }

  return (
    <div
      className="shrink-0 border-b px-4 py-3 sm:px-6"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div className="mx-auto grid w-full max-w-[1080px] grid-cols-1 gap-2 sm:grid-cols-[190px_minmax(260px,1fr)_132px]">
        <label className="relative block min-w-0">
          <span className="sr-only">运行厂区</span>
          <Building2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
          <select
            value={factory}
            onChange={(event) => onFactoryChange(event.target.value)}
            disabled={loading || factorySites.length === 0}
            className="h-10 w-full appearance-none rounded-md border pl-9 pr-8 text-[12px] font-semibold outline-none focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50"
            style={controlStyle}
          >
            {factorySites.length === 0 && <option value="">厂区加载中</option>}
            {factorySites.map((site) => (
              <option key={site.factory_id} value={site.factory_id}>{site.name}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
        </label>

        <label className="relative block min-w-0">
          <span className="sr-only">设备 SN</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: 'var(--color-text-muted)' }} />
          <input
            type="text"
            value={sn}
            onChange={(event) => onSnChange(event.target.value)}
            onKeyDown={onKeyDown}
            aria-label="设备 SN"
            autoComplete="off"
            spellCheck={false}
            className="h-10 w-full rounded-md border pl-9 pr-10 font-mono text-[13px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            style={controlStyle}
            placeholder="输入设备 SN"
          />
          {sn && !loading && (
            <button
              type="button"
              onClick={() => onSnChange('')}
              className="absolute right-1.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md hover:bg-black/5"
              style={{ color: 'var(--color-text-muted)' }}
              aria-label="清空设备 SN"
              title="清空"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </label>

        <button
          type="button"
          onClick={onDiagnose}
          disabled={!canSubmit}
          className="inline-flex h-10 w-full items-center justify-center gap-2 whitespace-nowrap rounded-md bg-blue-600 px-4 text-[12px] font-bold text-white shadow-sm transition hover:bg-blue-700 active:scale-[0.98] disabled:opacity-45"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
          {loading ? '诊断中' : '开始诊断'}
        </button>
      </div>
    </div>
  );
}
