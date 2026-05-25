/**
 * 自定义 JWT 认证 API
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TOKEN_KEY = 'auth_token';

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
}

export interface User {
  id: string;
  email: string;
}

// 获取 token
export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

// 设置 token
function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

// 清除 token
function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// 登录
export async function signIn(email: string, password: string): Promise<{ user?: User; error?: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      return { error: data.detail || '登录失败' };
    }

    setAccessToken(data.access_token);
    return {
      user: {
        id: data.user_id,
        email: data.email,
      },
    };
  } catch (error) {
    return { error: error instanceof Error ? error.message : '网络请求失败' };
  }
}

// 注册
export async function signUp(email: string, password: string): Promise<{ user?: User; error?: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      return { error: data.detail || '注册失败' };
    }

    setAccessToken(data.access_token);
    return {
      user: {
        id: data.user_id,
        email: data.email,
      },
    };
  } catch (error) {
    return { error: error instanceof Error ? error.message : '网络请求失败' };
  }
}

// 登出
export async function signOut(): Promise<void> {
  clearAccessToken();
}

// 获取当前用户
export async function getCurrentUser(): Promise<User | null> {
  const token = getAccessToken();
  if (!token) return null;

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      clearAccessToken();
      return null;
    }

    const data = await response.json();
    return { id: data.id, email: data.email };
  } catch {
    clearAccessToken();
    return null;
  }
}

// 检查是否已登录
export function isAuthenticated(): boolean {
  return !!getAccessToken();
}