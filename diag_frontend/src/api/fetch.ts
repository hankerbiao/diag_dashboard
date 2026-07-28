import { getAccessToken } from './auth';

// Empty means same-origin. In development Vite proxies /api to the backend,
// which keeps remote browser access independent from backend CORS settings.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  errorDetail?: string;
  errorCode?: string;
  stage?: string;
  message?: string;
}

export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
  try {
    const token = getAccessToken();
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options?.headers,
      },
    });
    return await response.json();
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : '网络请求失败' };
  }
}

export { API_BASE_URL };
