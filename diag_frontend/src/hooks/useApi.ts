import { useState, useCallback } from 'react';
import type { ApiResponse } from '../api/fetch';

/** Standardized API hook with loading/error state */
export function useApi<T>() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(async (apiCall: () => Promise<ApiResponse<T>>) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiCall();
      if (!res.success) setError(res.error || '请求失败');
      return res;
    } catch (e) {
      setError(e instanceof Error ? e.message : '网络请求失败');
      return { success: false, error: e instanceof Error ? e.message : '网络请求失败' } as ApiResponse<T>;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => { setError(null); }, []);

  return { loading, error, execute, reset };
}