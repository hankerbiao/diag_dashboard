import { Clock, Loader2 } from 'lucide-react';
import type { FactorySite, SnHistoryItem as SnHistoryItemType } from '../../api/fastapi';

function factoryDisplayName(factoryId: string, sites: FactorySite[]): string {
  if (!factoryId) return '—';
  return sites.find((f) => f.factory_id === factoryId)?.name ?? factoryId;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}

interface DiagnosisHistoryModalProps {
  items: SnHistoryItemType[];
  total: number;
  factorySites: FactorySite[];
  factoryLabel: string;
  activeId: string | null;
  loading: boolean;
  onClose: () => void;
  onSelect: (item: SnHistoryItemType) => void;
}

export default function DiagnosisHistoryModal({
  items,
  total,
  factorySites,
  factoryLabel,
  activeId,
  loading,
  onClose,
  onSelect,
}: DiagnosisHistoryModalProps) {
  const countLabel =
    total > items.length ? `最近 ${items.length} / 共 ${total} 条` : total > 0 ? `共 ${total} 条` : '';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="rounded-2xl border shadow-2xl w-[720px] max-h-[70vh] flex flex-col overflow-hidden"
        style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="px-5 py-3 border-b flex items-center justify-between shrink-0"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-secondary)' }}
        >
          <span className="text-[13px] font-bold flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
            <Clock className="w-4 h-4" /> 历史诊断记录
            {countLabel && (
              <span className="font-normal text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                {countLabel}
              </span>
            )}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center hover:opacity-70 transition-opacity text-[16px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar min-h-[200px]">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-16" style={{ color: 'var(--color-text-secondary)' }}>
              <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--color-accent)' }} />
              <span className="text-sm">加载历史记录…</span>
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-6 text-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              <p>暂无历史诊断记录</p>
              <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                {factoryLabel ? `当前厂区「${factoryLabel}」下完成诊断后会显示在这里` : '请选择厂区后进行诊断'}
              </p>
            </div>
          ) : (
            <table className="w-full text-[13px]">
              <thead className="sticky top-0 z-10">
                <tr style={{ color: 'var(--color-text-muted)', backgroundColor: 'var(--color-bg-secondary)' }}>
                  <th className="text-left font-medium whitespace-nowrap px-5 py-3 w-[96px]">时间</th>
                  <th className="text-left font-medium whitespace-nowrap px-5 py-3 w-[88px]">厂区</th>
                  <th className="text-left font-medium whitespace-nowrap px-5 py-3 w-[140px]">SN</th>
                  <th className="text-left font-medium whitespace-nowrap px-5 py-3">故障类别</th>
                  <th className="text-right font-medium whitespace-nowrap px-5 py-3 w-[80px]">置信度</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => {
                      onSelect(item);
                      onClose();
                    }}
                    className="cursor-pointer transition-colors"
                    style={{
                      backgroundColor: activeId === item.id ? 'var(--color-accent-light)' : 'transparent',
                      color: activeId === item.id ? 'var(--color-accent)' : 'var(--color-text-primary)',
                    }}
                    onMouseEnter={(e) => {
                      if (activeId !== item.id) e.currentTarget.style.backgroundColor = 'var(--color-bg-secondary)';
                    }}
                    onMouseLeave={(e) => {
                      if (activeId !== item.id) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <td className="px-5 py-3 font-mono whitespace-nowrap text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
                      {formatTime(item.created_at)}
                    </td>
                    <td className="px-5 py-3 text-[12px] whitespace-nowrap truncate max-w-[88px]" title={factoryDisplayName(item.factory, factorySites)}>
                      {factoryDisplayName(item.factory, factorySites)}
                    </td>
                    <td className="px-5 py-3 font-mono text-[12px]">{item.sn}</td>
                    <td className="px-5 py-3 truncate max-w-[220px]" title={item.category}>
                      {item.category || '—'}
                    </td>
                    <td className="px-5 py-3 text-right font-semibold">
                      {Math.round((item.confidence ?? 0) * 100)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
