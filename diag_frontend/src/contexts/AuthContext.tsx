import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import * as auth from '../api/auth';

const OA_LOGIN_PAUSED_KEY = 'oa_login_paused';

interface AuthContextType {
  user: auth.User | null;
  loading: boolean;
  authError: string;
  oaLoginPaused: boolean;
  startOALogin: () => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<auth.User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState('');
  const [oaLoginPaused, setOaLoginPaused] = useState(
    () => sessionStorage.getItem(OA_LOGIN_PAUSED_KEY) === 'true',
  );
  const initialCallbackRef = useRef<auth.OACallbackParams | null>(auth.getOACallbackParams());
  const callbackRequestRef = useRef<Promise<auth.OACallbackResponse> | null>(null);
  const callbackNextValidRef = useRef<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;

    const initialize = async () => {
      auth.clearLegacyCredentials();
      const callback = initialCallbackRef.current;

      if (callback) {
        auth.clearOACallbackParams();

        if (callback.status !== 'success') {
          if (!cancelled) {
            auth.clearOAState();
            sessionStorage.setItem(OA_LOGIN_PAUSED_KEY, 'true');
            setAuthError('OA 登录失败，请重试');
            setOaLoginPaused(true);
            setLoading(false);
          }
          return;
        }

        if (!callback.payload) {
          if (!cancelled) {
            auth.clearOAState();
            sessionStorage.setItem(OA_LOGIN_PAUSED_KEY, 'true');
            setAuthError('OA 登录返回信息不完整，请重试');
            setOaLoginPaused(true);
            setLoading(false);
          }
          return;
        }

        callbackNextValidRef.current ??= auth.isValidOACallbackNext(callback.next);
        if (!callbackNextValidRef.current) {
          if (!cancelled) {
            auth.clearOAState();
            sessionStorage.setItem(OA_LOGIN_PAUSED_KEY, 'true');
            setAuthError('OA 登录返回地址无效，请重试');
            setOaLoginPaused(true);
            setLoading(false);
          }
          return;
        }

        try {
          callbackRequestRef.current ||= auth.completeOACallback(callback);
          const result = await callbackRequestRef.current;
          if (cancelled) return;

          auth.setAccessToken(result.access_token);
          auth.clearOAState();
          if (!cancelled) {
            setUser(result.user);
            setAuthError('');
            setOaLoginPaused(false);
            sessionStorage.removeItem(OA_LOGIN_PAUSED_KEY);
            setLoading(false);
          }
        } catch (error) {
          if (!cancelled) {
            auth.clearAccessToken();
            auth.clearOAState();
            sessionStorage.setItem(OA_LOGIN_PAUSED_KEY, 'true');
            setAuthError(error instanceof Error ? error.message : 'OA 登录失败，请重试');
            setOaLoginPaused(true);
            setLoading(false);
          }
        }
        return;
      }

      try {
        const currentUser = await auth.getCurrentUser();
        if (!cancelled) {
          setUser(currentUser);
          setLoading(false);
        }
      } catch (error) {
        if (!cancelled) {
          sessionStorage.setItem(OA_LOGIN_PAUSED_KEY, 'true');
          setAuthError(error instanceof Error ? error.message : '无法连接认证服务');
          setOaLoginPaused(true);
          setLoading(false);
        }
      }
    };

    initialize();
    return () => {
      cancelled = true;
    };
  }, []);

  const startOALogin = useCallback(() => {
    sessionStorage.removeItem(OA_LOGIN_PAUSED_KEY);
    setOaLoginPaused(false);
    setAuthError('');
    window.location.assign(auth.getOALoginUrl());
  }, []);

  const signOut = () => {
    auth.signOut();
    setUser(null);
    setAuthError('');
    setOaLoginPaused(true);
    sessionStorage.setItem(OA_LOGIN_PAUSED_KEY, 'true');
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, authError, oaLoginPaused, startOALogin, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
