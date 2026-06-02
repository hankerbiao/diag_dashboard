import { LayoutDashboard } from 'lucide-react';
import type { FactorySite } from '../../api/fastapi';
import SupportHint from '../common/SupportHint';

interface SearchPanelProps {
  factory: string;
  factorySites: FactorySite[];
  sn: string;
  productModels: string;
  onSnChange: (value: string) => void;
  onProductModelsChange: (value: string) => void;
  onSearch: () => void;
  onReset: () => void;
}

export default function SearchPanel({
  factory,
  factorySites,
  sn,
  productModels,
  onSnChange,
  onProductModelsChange,
  onSearch,
  onReset,
}: SearchPanelProps) {
  const factoryName = factorySites.find((f) => f.factory_id === factory)?.name ?? factory;
  return (
    <div
      className="m-4 p-5 rounded-lg flex-none border"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div
        className="flex items-center gap-2 border-b pb-4 mb-4"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <div
          className="flex items-center gap-2 px-2.5 py-1 rounded-md text-xs font-bold border"
          style={{
            backgroundColor: 'var(--color-accent-light)',
            color: 'var(--color-accent)',
            borderColor: 'var(--color-accent)',
          }}
        >
          <LayoutDashboard className="w-3.5 h-3.5" />
          {factoryName}厂区数据视图
        </div>
      </div>

      <div className="flex gap-4 items-end">
        <div className="flex flex-col gap-1.5 flex-1 max-w-xs">
          <label
            className="text-xs font-semibold"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            服务器 SN
          </label>
          <input
            type="text"
            value={sn}
            onChange={(e) => onSnChange(e.target.value)}
            placeholder="输入 SN 模糊搜索"
            className="h-9 border rounded-md px-3 text-[13px] outline-none transition-all font-mono shadow-sm"
            style={{
              borderColor: 'var(--color-border)',
              backgroundColor: 'var(--color-bg-primary)',
              color: 'var(--color-text-primary)',
            }}
          />
        </div>

        <div className="flex flex-col gap-1.5 flex-1 max-w-xs">
          <label
            className="text-xs font-semibold"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            产品型号
          </label>
          <input
            type="text"
            value={productModels}
            onChange={(e) => onProductModelsChange(e.target.value)}
            placeholder="输入产品型号"
            className="h-9 border rounded-md px-3 text-[13px] outline-none transition-all shadow-sm"
            style={{
              borderColor: 'var(--color-border)',
              backgroundColor: 'var(--color-bg-primary)',
              color: 'var(--color-text-primary)',
            }}
          />
        </div>

        <button
          onClick={onSearch}
          className="h-9 px-6 border rounded-md text-[13px] font-bold transition-colors shadow-sm text-white border-0"
          style={{ backgroundColor: 'var(--color-accent)' }}
        >
          搜索
        </button>

        <button
          onClick={onReset}
          className="h-9 px-6 border rounded-md text-[13px] font-medium transition-colors shadow-sm"
          style={{
            backgroundColor: 'var(--color-bg-secondary)',
            borderColor: 'var(--color-border)',
            color: 'var(--color-text-secondary)',
          }}
        >
          重置
        </button>
      </div>

      <SupportHint
        className="mt-4 pt-3 border-t"
        style={{ borderColor: 'var(--color-border)' }}
        extra="详细说明见系统设置 → 使用文档"
      />
    </div>
  );
}
