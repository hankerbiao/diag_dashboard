import { useRef, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, BookOpen } from 'lucide-react';
import ApiConfig from './ApiConfig';
import type { ApiConfigHandle } from './ApiConfig';
import ExternalSyncNotice from './ExternalSyncNotice';
import GuideModal from '../guide/GuideModal';
import SupportHint from '../common/SupportHint';

export default function SettingsTab() {
  const apiConfigRef = useRef<ApiConfigHandle>(null);
  const [saving, setSaving] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showFeedback = useCallback((type: 'success' | 'error', message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 3000);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setFeedback(null);

    if (apiConfigRef.current) {
      const ok = await apiConfigRef.current.save();
      if (!ok) {
        setSaving(false);
        return;
      }
    }

    showFeedback('success', 'AI 配置已保存并生效');
    setSaving(false);
  };

  return (
    <div
      className="flex-1 overflow-y-auto p-6 lg:p-10 flex justify-center custom-scrollbar"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <div className="w-full max-w-4xl space-y-8 pb-12">
        <ExternalSyncNotice />
        <ApiConfig ref={apiConfigRef} />

        <section
          className="rounded-xl border p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
          style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
        >
          <div className="space-y-2 min-w-0">
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 shrink-0" style={{ color: 'var(--color-accent)' }} />
              <h2 className="text-[15px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
                使用文档
              </h2>
            </div>
            <p className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              面向产线操作人员的快速指南，含登录、诊断、异常看板与 FAQ。
            </p>
            <SupportHint compact />
          </div>
          <button
            type="button"
            onClick={() => setGuideOpen(true)}
            className="shrink-0 px-5 py-2.5 rounded-lg text-[13px] font-bold text-white shadow-sm flex items-center gap-2 transition-all active:scale-[0.98]"
            style={{ backgroundColor: 'var(--color-accent)', boxShadow: '0 2px 8px -2px var(--color-shadow)' }}
          >
            <BookOpen className="w-4 h-4" />
            查看使用文档
          </button>
        </section>

        <GuideModal open={guideOpen} onClose={() => setGuideOpen(false)} />

        {feedback && (
          <div
            className="flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium animate-pulse"
            style={{
              backgroundColor: feedback.type === 'success' ? 'var(--color-success-bg, #ecfdf5)' : 'var(--color-error-bg, #fef2f2)',
              color: feedback.type === 'success' ? 'var(--color-success, #059669)' : 'var(--color-error, #dc2626)',
              border: `1px solid ${feedback.type === 'success' ? 'var(--color-success, #059669)' : 'var(--color-error, #dc2626)'}44`,
            }}
          >
            {feedback.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            {feedback.message}
          </div>
        )}

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
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2.5 text-white font-bold text-[13px] rounded-lg transition-colors shadow-sm flex items-center gap-2 active:scale-95 disabled:opacity-60"
            style={{
              backgroundColor: 'var(--color-accent)',
              boxShadow: '0 4px 6px -1px var(--color-shadow)',
            }}
          >
            <CheckCircle2 className="w-4 h-4" /> {saving ? '保存中...' : '应用全局配置'}
          </button>
        </div>
      </div>
    </div>
  );
}