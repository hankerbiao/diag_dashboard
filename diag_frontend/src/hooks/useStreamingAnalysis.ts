import { useState, useCallback, useRef, useEffect } from 'react';

interface StreamingState<T> {
  progress: { stage: string; detail: string } | null;
  streamingText: string;
  result: T | null;
  error: string;
  loading: boolean;
}

interface UseStreamingAnalysisOptions<T> {
  onComplete?: (data: T) => void;
  onError?: (msg: string) => void;
}

/** Hook for SSE streaming analysis with standardized state management */
export function useStreamingAnalysis<T>(options?: UseStreamingAnalysisOptions<T>) {
  const [state, setState] = useState<StreamingState<T>>({
    progress: null, streamingText: '', result: null, error: '', loading: false,
  });
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => { abortRef.current?.abort(); }, []);

  const start = useCallback((sseFactory: (callbacks: {
    onProgress: (stage: string, detail: string) => void;
    onComplete: (data: T) => void;
    onError: (msg: string) => void;
    onToken?: (text: string) => void;
  }) => Promise<AbortController>) => {
    abortRef.current?.abort();
    setState({ progress: null, streamingText: '', result: null, error: '', loading: true });

    sseFactory({
      onProgress: (stage, detail) => setState(s => ({ ...s, progress: { stage, detail } })),
      onComplete: (data) => {
        setState(s => ({ ...s, result: data, loading: false, progress: null }));
        options?.onComplete?.(data);
      },
      onError: (msg) => {
        setState(s => ({ ...s, error: msg, loading: false, progress: null }));
        options?.onError?.(msg);
      },
      onToken: (text) => setState(s => ({ ...s, streamingText: prev => prev + text })),
    }).then(ctrl => { abortRef.current = ctrl; });
  }, [options]);

  const cancel = useCallback(() => { abortRef.current?.abort(); }, []);

  return { ...state, start, cancel };
}