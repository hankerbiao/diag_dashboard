import { useEffect, useRef } from 'react';
import { Bot, Loader2, LogIn } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import ParticleBackground from './ParticleBackground';

const TAGLINES = [
  '智能分析每一条异常日志…',
  '基于知识图谱的深度诊断推理…',
  '覆盖所有厂区，实时数据同步…',
  '毫秒级 SN 诊断查询响应…',
  'AI 驱动的设备故障根因定位…',
];

export default function LoginPage() {
  const { authError, oaLoginPaused, startOALogin } = useAuth();
  const redirectStartedRef = useRef(false);

  useEffect(() => {
    if (!authError && !oaLoginPaused && !redirectStartedRef.current) {
      redirectStartedRef.current = true;
      startOALogin();
    }
  }, [authError, oaLoginPaused, startOALogin]);

  return (
    <div
      className="min-h-screen flex items-center justify-center relative"
      style={{ backgroundColor: '#f8fafc' }}
    >
      <ParticleBackground />
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_20%_50%,rgba(99,102,241,0.04),transparent_50%),radial-gradient(ellipse_at_80%_20%,rgba(59,130,246,0.04),transparent_50%)]" />

      <div className="w-full max-w-md mx-4 relative z-10 text-center">
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

        <div
          className="rounded-2xl p-8 border shadow-xl mt-8"
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.75)',
            borderColor: 'rgba(226, 232, 240, 0.8)',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 4px 60px rgba(99, 102, 241, 0.06)',
          }}
        >
          <h2 className="text-lg font-bold text-slate-800">OA 登录</h2>
          <p className="text-sm text-slate-500 mt-3">
            {authError || TAGLINES[0]}
          </p>

          {!authError && !oaLoginPaused && (
            <Loader2 className="w-5 h-5 animate-spin mx-auto mt-6 text-indigo-500" />
          )}

          {(authError || oaLoginPaused) && (
            <button
              type="button"
              onClick={startOALogin}
              className="w-full h-11 mt-6 rounded-xl text-white font-semibold text-sm transition-all active:scale-[0.98] flex items-center justify-center gap-2"
              style={{
                background: 'linear-gradient(135deg, #6366f1, #3b82f6)',
                boxShadow: '0 4px 20px rgba(99, 102, 241, 0.3)',
              }}
            >
              <LogIn className="w-4 h-4" />
              使用 OA 登录
            </button>
          )}
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">
          WeaveEye · Diag SIMS · AI-Powered Diagnostics
        </p>
      </div>
    </div>
  );
}
