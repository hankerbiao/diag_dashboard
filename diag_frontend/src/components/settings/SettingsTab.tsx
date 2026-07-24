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
      <div className="mx-auto w-full max-w-[1400px] px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
        <div
          className="mb-7 border-b pb-5"
          style={{
            borderColor: 'var(--color-border)',
          }}
        >
          <div className="flex w-full flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Settings className="h-5 w-5 shrink-0" style={{ color: 'var(--color-accent)' }} />
                <h1 className="text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  系统管理与 AI 引擎配置
                </h1>
              </div>
              <p className="mt-2 max-w-2xl text-sm leading-6" style={{ color: 'var(--color-text-secondary)' }}>
                统一管理诊断模型、日志提取模型，以及不同机型对应的日志解析 Prompt。
              </p>
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex h-10 w-full shrink-0 items-center justify-center gap-2 rounded-lg px-4 text-sm font-bold text-white shadow-sm transition active:scale-[0.98] disabled:opacity-60 sm:w-auto"
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

        <div className="grid min-w-0 gap-6 2xl:grid-cols-[minmax(0,1fr)_300px]">
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

          <aside className="grid gap-4 md:grid-cols-2 2xl:sticky 2xl:top-6 2xl:block 2xl:space-y-4 2xl:self-start">
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
