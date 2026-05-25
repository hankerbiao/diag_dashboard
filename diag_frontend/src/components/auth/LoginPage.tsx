import { useState, type FormEvent } from 'react';
import { Bot, Mail, Lock, Loader2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export default function LoginPage() {
  const { signIn, signUp } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setSubmitting(true);

    const result = isRegister
      ? await signUp(email, password)
      : await signIn(email, password);

    setSubmitting(false);

    if (result?.error) {
      setError(result.error);
    } else if (isRegister) {
      setSuccessMsg('注册成功！请检查邮箱确认链接，或直接尝试登录。');
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <div className="w-full max-w-md mx-4">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg"
              style={{
                background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
              }}
            >
              <Bot className="w-9 h-9 text-white" />
            </div>
          </div>
          <h1
            className="text-2xl font-bold tracking-wide"
            style={{ color: 'var(--color-text-primary)' }}
          >
            WeaveEye
          </h1>
          <p
            className="text-sm mt-1"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            智能诊断系统
          </p>
        </div>

        <div
          className="rounded-2xl shadow-xl p-8 border"
          style={{
            backgroundColor: 'var(--color-bg-secondary)',
            borderColor: 'var(--color-border)',
          }}
        >
          <h2
            className="text-lg font-bold mb-6 text-center"
            style={{ color: 'var(--color-text-primary)' }}
          >
            {isRegister ? '创建账号' : 'OA 登录'}
          </h2>

          {successMsg && (
            <div
              className="text-sm p-3 rounded-lg mb-4 border"
              style={{
                backgroundColor: '#ecfdf5',
                borderColor: '#6ee7b7',
                color: '#065f46',
              }}
            >
              {successMsg}
            </div>
          )}

          {error && (
            <div
              className="text-sm p-3 rounded-lg mb-4 border"
              style={{
                backgroundColor: '#fef2f2',
                borderColor: '#fca5a5',
                color: '#991b1b',
              }}
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                className="text-xs font-bold uppercase tracking-wider mb-1.5 block"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                邮箱
              </label>
              <div className="relative">
                <Mail
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                  style={{ color: 'var(--color-text-muted)' }}
                />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full h-10 pl-10 pr-3 rounded-lg text-sm outline-none border transition-colors"
                  style={{
                    backgroundColor: 'var(--color-bg-primary)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-primary)',
                  }}
                />
              </div>
            </div>

            <div>
              <label
                className="text-xs font-bold uppercase tracking-wider mb-1.5 block"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                密码
              </label>
              <div className="relative">
                <Lock
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                  style={{ color: 'var(--color-text-muted)' }}
                />
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="不少于6位"
                  className="w-full h-10 pl-10 pr-3 rounded-lg text-sm outline-none border transition-colors"
                  style={{
                    backgroundColor: 'var(--color-bg-primary)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-primary)',
                  }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full h-10 rounded-lg text-white font-bold text-sm transition-all active:scale-[0.98] flex items-center justify-center gap-2"
              style={{
                background: submitting
                  ? 'linear-gradient(135deg, #93c5fd, #a5b4fc)'
                  : 'linear-gradient(135deg, #3b82f6, #6366f1)',
              }}
            >
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              {isRegister ? '注册' : '登录'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setIsRegister(!isRegister);
                setError('');
                setSuccessMsg('');
              }}
              className="text-sm font-medium hover:underline transition-colors"
              style={{ color: 'var(--color-accent)' }}
            >
              {isRegister ? '已有账号？立即登录' : '没有账号？立即注册'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
