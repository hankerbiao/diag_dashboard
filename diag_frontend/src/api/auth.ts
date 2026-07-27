/** OA SSO 与应用 Bearer JWT 管理。 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const TOKEN_KEY = 'auth_token';
const LEGACY_CREDENTIAL_KEYS = ['remember_email', 'remember_password'];
const OA_STATE_KEY = 'oa_login_state';
const OA_STATE_PARAM = '__oa_state';
const OA_LOGIN_URL =
  import.meta.env.VITE_OA_LOGIN_URL ||
  'http://tl.cooacloud.com/springboard_v3/login_proxy/diagweaveeye';

export interface User {
  id: string;
  itcode: string;
  name: string;
  email?: string | null;
  profile?: Record<string, unknown>;
  is_admin: boolean;
}

export interface OACallbackParams {
  status: string;
  payload: string;
  next: string | null;
}

export interface OACallbackResponse {
  access_token: string;
  token_type: string;
  user: User;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseUser(value: unknown): User {
  if (
    !isRecord(value) ||
    typeof value.id !== 'string' ||
    typeof value.itcode !== 'string' ||
    typeof value.name !== 'string' ||
    (value.email !== undefined && value.email !== null && typeof value.email !== 'string') ||
    (value.profile !== undefined && !isRecord(value.profile)) ||
    (value.is_admin !== undefined && typeof value.is_admin !== 'boolean')
  ) {
    throw new Error('认证服务返回了无效的用户信息');
  }

  return {
    id: value.id,
    itcode: value.itcode,
    name: value.name,
    email: value.email as string | null | undefined,
    profile: value.profile as Record<string, unknown> | undefined,
    is_admin: value.is_admin === true,
  };
}

function parseOACallbackResponse(value: unknown): OACallbackResponse {
  if (
    !isRecord(value) ||
    typeof value.access_token !== 'string' ||
    !value.access_token ||
    typeof value.token_type !== 'string'
  ) {
    throw new Error('认证服务返回了无效的登录信息');
  }

  return {
    access_token: value.access_token,
    token_type: value.token_type,
    user: parseUser(value.user),
  };
}

function getErrorMessage(value: unknown): string | null {
  if (!isRecord(value)) return null;
  if (typeof value.detail === 'string') return value.detail;
  if (typeof value.message === 'string') return value.message;
  return null;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function clearLegacyCredentials(): void {
  LEGACY_CREDENTIAL_KEYS.forEach((key) => localStorage.removeItem(key));
}

export function getOACallbackParams(): OACallbackParams | null {
  const url = new URL(window.location.href);
  const status = url.searchParams.get('status');
  const payload = url.searchParams.get('payload');
  const next = url.searchParams.get('next');

  if (!status || !payload) return null;
  return { status: status || '', payload: payload || '', next };
}

export function clearOACallbackParams(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete('status');
  url.searchParams.delete('payload');
  url.searchParams.delete('next');
  url.searchParams.delete(OA_STATE_PARAM);
  window.history.replaceState(null, '', url.toString());
}

export function isValidOACallbackNext(next: string | null): boolean {
  const expectedState = sessionStorage.getItem(OA_STATE_KEY);
  if (!next || !expectedState) return false;
  try {
    const nextUrl = new URL(next, window.location.origin);
    return (
      nextUrl.origin === window.location.origin &&
      nextUrl.searchParams.get(OA_STATE_PARAM) === expectedState
    );
  } catch {
    return false;
  }
}

export function clearOAState(): void {
  sessionStorage.removeItem(OA_STATE_KEY);
}

function createOAState(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function getOALoginUrl(): string {
  const callbackUrl = new URL(window.location.href);
  callbackUrl.searchParams.delete('status');
  callbackUrl.searchParams.delete('payload');
  callbackUrl.searchParams.delete('next');
  callbackUrl.searchParams.delete(OA_STATE_PARAM);

  const state = createOAState();
  sessionStorage.setItem(OA_STATE_KEY, state);
  callbackUrl.searchParams.set(OA_STATE_PARAM, state);

  const target = new URL(OA_LOGIN_URL);
  target.searchParams.set('next', callbackUrl.toString());
  return target.toString();
}

export async function completeOACallback(
  params: OACallbackParams,
): Promise<OACallbackResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/oa/callback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  const data: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(data) || 'OA 登录失败');
  }
  return parseOACallbackResponse(data);
}

export async function getCurrentUser(): Promise<User | null> {
  const token = getAccessToken();
  if (!token) return null;

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.status === 401) {
      clearAccessToken();
      return null;
    }
    if (!response.ok) {
      throw new Error('无法验证当前登录状态');
    }

    return parseUser(await response.json());
  } catch (error) {
    throw error instanceof Error ? error : new Error('无法连接认证服务');
  }
}

export function signOut(): void {
  clearAccessToken();
  clearLegacyCredentials();
  clearOAState();
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}
