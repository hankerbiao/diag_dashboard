import { useRef, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, BookOpen, Save, Settings } from 'lucide-react';
import ApiConfig from './ApiConfig';
import type { ApiConfigHandle } from './ApiConfig';
import LogExtractionPrompts from './LogExtractionPrompts';
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
  const showSuccess = useCallback((message: string) => showFeedback('success', message), [showFeedback]);
  const showError = useCallback((message: string) => showFeedback('error', message), [showFeedback]);

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
      className="flex-1 overflow-y-auto custom-scrollbar"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <div className="mx-auto w-full max-w-6xl px-5 py-6 lg:px-8 lg:py-8">
        <div
          className="sticky top-0 z-10 -mx-5 mb-6 border-b px-5 py-4 backdrop-blur lg:-mx-8 lg:px-8"
          style={{
            backgroundColor: 'color-mix(in srgb, var(--color-bg-primary) 88%, transparent)',
            borderColor: 'var(--color-border)',
          }}
        >
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Settings className="h-5 w-5 shrink-0" style={{ color: 'var(--color-accent)' }} />
                <h1 className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  系统设置
                </h1>
              </div>
              <p className="mt-1 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                管理 AI 模型、日志提取 Prompt 与操作文档。
              </p>
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg px-4 text-sm font-bold text-white shadow-sm transition active:scale-[0.98] disabled:opacity-60"
              style={{
                backgroundColor: 'var(--color-accent)',
                boxShadow: '0 4px 10px -4px var(--color-shadow)',
              }}
            >
              <Save className="h-4 w-4" />
              {saving ? '保存中...' : '保存 AI 配置'}
            </button>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="min-w-0 space-y-6">
            <ApiConfig
              ref={apiConfigRef}
              onSuccessMessage={showSuccess}
              onErrorMessage={showError}
            />

            <LogExtractionPrompts
              onSuccessMessage={showSuccess}
              onErrorMessage={showError}
            />
          </div>

          <aside className="space-y-4 lg:sticky lg:top-28 lg:self-start">
            <section
              className="rounded-lg border p-5"
              style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
            >
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 shrink-0" style={{ color: 'var(--color-accent)' }} />
                <h2 className="text-sm font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  使用文档
                </h2>
              </div>
              <p className="mt-2 text-xs leading-5" style={{ color: 'var(--color-text-muted)' }}>
                登录、诊断、异常看板与常见问题的快速指南。
              </p>
              <button
                type="button"
                onClick={() => setGuideOpen(true)}
                className="mt-4 inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg text-sm font-bold text-white transition active:scale-[0.98]"
                style={{ backgroundColor: 'var(--color-accent)' }}
              >
                <BookOpen className="h-4 w-4" />
                打开文档
              </button>
            </section>

            <SupportHint compact />
          </aside>
        </div>

        <GuideModal open={guideOpen} onClose={() => setGuideOpen(false)} />

        {feedback && (
          <div
            className="fixed bottom-6 right-6 z-20 flex max-w-sm items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium shadow-lg"
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
      </div>
    </div>
  );
}
