/**
 * 自定义 JWT 认证 API
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TOKEN_KEY = 'auth_token';
const REMEMBER_EMAIL_KEY = 'remember_email';
const REMEMBER_PASSWORD_KEY = 'remember_password';

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

// ============ Token 管理 ============

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ============ 记住密码 ============

export function getRememberedCredentials(): { email: string; password: string } | null {
  const email = localStorage.getItem(REMEMBER_EMAIL_KEY);
  const password = localStorage.getItem(REMEMBER_PASSWORD_KEY);
  if (email && password) {
    return { email, password };
  }
  return null;
}

function saveRememberedCredentials(email: string, password: string): void {
  localStorage.setItem(REMEMBER_EMAIL_KEY, email);
  localStorage.setItem(REMEMBER_PASSWORD_KEY, password);
}

function clearRememberedCredentials(): void {
  localStorage.removeItem(REMEMBER_EMAIL_KEY);
  localStorage.removeItem(REMEMBER_PASSWORD_KEY);
}

// ============ 认证操作 ============

export async function signIn(
  email: string,
  password: string,
  remember: boolean = false
): Promise<{ user?: User; error?: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, remember }),
    });

    const data = await response.json();

    if (!response.ok) {
      return { error: data.detail || '登录失败' };
    }

    setAccessToken(data.access_token);

    // 如果选择记住密码，保存凭据
    if (remember) {
      saveRememberedCredentials(email, password);
    } else {
      clearRememberedCredentials();
    }

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

export async function signOut(): Promise<void> {
  clearAccessToken();
  clearRememberedCredentials();
}

export async function getCurrentUser(): Promise<User | null> {
  const token = getAccessToken();
  if (!token) return null;

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      clearAccessToken();
      clearRememberedCredentials();
      return null;
    }

    const data = await response.json();
    return { id: data.id, email: data.email };
  } catch {
    clearAccessToken();
    clearRememberedCredentials();
    return null;
  }
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}