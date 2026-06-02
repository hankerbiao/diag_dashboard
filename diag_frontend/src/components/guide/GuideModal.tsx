import { BookOpen, X } from 'lucide-react';
import GuideTab from './GuideTab';
import SupportHint from '../common/SupportHint';

interface GuideModalProps {
  open: boolean;
  onClose: () => void;
}

export default function GuideModal({ open, onClose }: GuideModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
      style={{ backdropFilter: 'blur(4px)', backgroundColor: 'rgba(15, 23, 42, 0.12)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-5xl max-h-[90vh] shadow-2xl rounded-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-300 border"
        style={{ backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="h-14 px-6 border-b flex items-center justify-between shrink-0"
          style={{ backgroundColor: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}
        >
          <h3 className="font-bold flex items-center gap-2.5 text-base" style={{ color: 'var(--color-text-primary)' }}>
            <span
              className="w-8 h-8 rounded-lg flex items-center justify-center shadow-sm"
              style={{ backgroundColor: 'var(--color-accent-light)', color: 'var(--color-accent)' }}
            >
              <BookOpen className="w-5 h-5" />
            </span>
            WeaveEye 使用文档
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-full transition-colors active:scale-95"
            style={{ color: 'var(--color-text-secondary)' }}
            aria-label="关闭"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 min-h-0 flex flex-col p-4">
          <GuideTab variant="modal" />
        </div>

        <div
          className="px-6 py-2.5 border-t shrink-0 flex justify-center"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-bg-primary)' }}
        >
          <SupportHint compact />
        </div>
      </div>
    </div>
  );
}
