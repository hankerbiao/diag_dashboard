import { type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import LoginPage from './LoginPage';

interface AuthGuardProps {
  children: ReactNode;
}

export default function AuthGuard({ children }: AuthGuardProps) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ backgroundColor: 'var(--color-bg-primary)' }}
      >
        <div className="text-center">
          <Loader2
            className="w-8 h-8 animate-spin mx-auto mb-3"
            style={{ color: 'var(--color-accent)' }}
          />
          <p
            className="text-sm font-medium"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            加载中...
          </p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return <>{children}</>;
}
