import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import { CheckCircle, XCircle, Loader2, Info } from 'lucide-react';

type ToastType = 'success' | 'error' | 'info' | 'loading';

interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number; // ms, 0 means no auto-dismiss
}

interface ToastContextValue {
  toast: (type: ToastType, message: string, duration?: number) => string;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

const TOAST_ICONS: Record<ToastType, ReactNode> = {
  success: <CheckCircle className="w-4 h-4 text-green-400" />,
  error: <XCircle className="w-4 h-4 text-red-400" />,
  info: <Info className="w-4 h-4 text-blue-400" />,
  loading: <Loader2 className="w-4 h-4 animate-spin text-blue-400" />,
};

const TOAST_STYLES: Record<ToastType, { bg: string; border: string }> = {
  success: { bg: 'rgba(5, 150, 105, 0.08)', border: 'rgba(5, 150, 105, 0.25)' },
  error: { bg: 'rgba(220, 38, 38, 0.08)', border: 'rgba(220, 38, 38, 0.25)' },
  info: { bg: 'rgba(59, 130, 246, 0.08)', border: 'rgba(59, 130, 246, 0.25)' },
  loading: { bg: 'rgba(59, 130, 246, 0.08)', border: 'rgba(59, 130, 246, 0.25)' },
};

let toastIdCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((type: ToastType, message: string, duration = 3000): string => {
    const id = `toast-${++toastIdCounter}`;
    setToasts((prev) => [...prev, { id, type, message, duration: type === 'loading' ? 0 : duration }]);
    return id;
  }, []);

  // Auto-dismiss non-loading toasts
  useEffect(() => {
    const timers = toasts
      .filter((t) => t.duration && t.duration > 0)
      .map((t) => setTimeout(() => dismiss(t.id), t.duration));
    return () => timers.forEach(clearTimeout);
  }, [toasts, dismiss]);

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      {children}

      {/* Toast container - fixed top-right */}
      <div
        className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none"
        style={{ maxWidth: '400px' }}
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl border shadow-lg text-sm animate-in slide-in-from-right pointer-events-auto"
            style={{
              backgroundColor: t.type === 'success' ? 'rgba(5, 150, 105, 0.95)' :
                t.type === 'error' ? 'rgba(220, 38, 38, 0.95)' :
                'rgba(30, 41, 59, 0.95)',
              borderColor: TOAST_STYLES[t.type].border,
              color: '#fff',
              backdropFilter: 'blur(8px)',
            }}
          >
            {TOAST_ICONS[t.type]}
            <span className="text-[13px] font-medium flex-1">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="p-0.5 rounded-full hover:bg-white/10 transition-colors shrink-0"
            >
              <XCircle className="w-3.5 h-3.5 opacity-60 hover:opacity-100" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
