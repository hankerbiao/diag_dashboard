import { useState, useEffect, type FormEvent } from 'react';
import { Bot, Mail, Lock, Loader2, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { getRememberedCredentials } from '../../api/auth';
import { useTypingAnimation } from '../../hooks/useTypingAnimation';
import ParticleBackground from './ParticleBackground';

const TAGLINES = [
  '智能分析每一条异常日志…',
  '基于知识图谱的深度诊断推理…',
  '覆盖所有厂区，实时数据同步…',
  '毫秒级 SN 诊断查询响应…',
  'AI 驱动的设备故障根因定位…',
];

export default function LoginPage() {
  const { signIn, signUp } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('admin@admin.com');
  const [password, setPassword] = useState('admin123');
  const [remember, setRemember] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const { displayText } = useTypingAnimation({ texts: TAGLINES });

  useEffect(() => {
    const saved = getRememberedCredentials();
    if (saved) {
      setEmail(saved.email);
      setPassword(saved.password);
      setRemember(true);
    }
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setSubmitting(true);

    const result = isRegister
      ? await signUp(email, password)
      : await signIn(email, password, remember);

    setSubmitting(false);

    if (result?.error) {
      setError(result.error);
    } else if (isRegister) {
      setSuccessMsg('注册成功！请使用新账号登录。');
      setIsRegister(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center relative"
      style={{ backgroundColor: '#f8fafc' }}
    >
      <ParticleBackground />

      {/* Subtle gradient mesh */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse at 20% 50%, rgba(99,102,241,0.04) 0%, transparent 50%), ' +
            'radial-gradient(ellipse at 80% 20%, rgba(59,130,246,0.04) 0%, transparent 50%)',
        }}
      />

      <div className="w-full max-w-md mx-4 relative z-10">
        {/* Logo + Brand */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-5">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center"
              style={{
                background: 'linear-gradient(135deg, #6366f1, #3b82f6)',
                boxShadow: '0 8px 40px rgba(99, 102, 241, 0.25)',
              }}
            >
              <Bot className="w-9 h-9 text-white" />
            </div>
          </div>
          <h1
            className="text-3xl font-extrabold tracking-tight"
            style={{
              background: 'linear-gradient(135deg, #6366f1, #3b82f6, #06b6d4)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            WeaveEye
          </h1>
          <p className="text-sm font-medium text-slate-500 mt-1 tracking-wide">
            Diag SIMS 异常分析系统
          </p>

          {/* Typing tagline */}
          <div className="h-6 mt-3 flex items-center justify-center">
            <p className="text-sm text-slate-400">
              {displayText}
              <span
                className="inline-block w-[2px] h-4 ml-0.5 align-middle animate-pulse"
                style={{ backgroundColor: '#6366f1' }}
              />
            </p>
          </div>
        </div>

        {/* Login Card */}
        <div
          className="rounded-2xl p-8 border shadow-xl"
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.75)',
            borderColor: 'rgba(226, 232, 240, 0.8)',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 4px 60px rgba(99, 102, 241, 0.06)',
          }}
        >
          <h2 className="text-lg font-bold mb-6 text-center text-slate-800">
            {isRegister ? '创建账号' : '登录系统'}
          </h2>

          {successMsg && (
            <div className="text-sm p-3 rounded-lg mb-4 border border-emerald-200 bg-emerald-50 text-emerald-700">
              {successMsg}
            </div>
          )}
          {error && (
            <div className="text-sm p-3 rounded-lg mb-4 border border-red-200 bg-red-50 text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">
                邮箱
              </label>
              <div className="relative group">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
                <input
                  type="email"
                  name="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full h-11 pl-10 pr-4 rounded-xl text-sm outline-none border transition-all duration-300 bg-white border-slate-200 text-slate-800 placeholder:text-slate-300 focus:border-indigo-400 focus:shadow-[0_0_0_3px_rgba(99,102,241,0.08)]"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">
                密码
              </label>
              <div className="relative group">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  name={isRegister ? 'new-password' : 'password'}
                  autoComplete={isRegister ? 'new-password' : 'current-password'}
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="不少于6位"
                  className="w-full h-11 pl-10 pr-10 rounded-xl text-sm outline-none border transition-all duration-300 bg-white border-slate-200 text-slate-800 placeholder:text-slate-300 focus:border-indigo-400 focus:shadow-[0_0_0_3px_rgba(99,102,241,0.08)]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {!isRegister && (
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300 bg-white cursor-pointer accent-indigo-500"
                />
                <span className="text-xs text-slate-500">保存密码，保持 1 天免登录</span>
              </label>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full h-11 rounded-xl text-white font-semibold text-sm transition-all active:scale-[0.98] flex items-center justify-center gap-2"
              style={{
                background: submitting
                  ? 'linear-gradient(135deg, #818cf8, #60a5fa)'
                  : 'linear-gradient(135deg, #6366f1, #3b82f6)',
                boxShadow: submitting
                  ? 'none'
                  : '0 4px 20px rgba(99, 102, 241, 0.3)',
              }}
            >
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              {isRegister ? '注册' : '登 录'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setIsRegister(!isRegister);
                setError('');
                setSuccessMsg('');
              }}
              className="text-sm font-medium text-indigo-500 hover:text-indigo-600 transition-colors"
            >
              {isRegister ? '已有账号？立即登录' : '没有账号？立即注册'}
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">
          WeaveEye · Diag SIMS · AI-Powered Diagnostics
        </p>
      </div>
    </div>
  );
}
