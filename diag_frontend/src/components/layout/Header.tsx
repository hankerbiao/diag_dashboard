import { LogIn, LogOut } from 'lucide-react';
import type { NavigationTab } from '../../types';
import type { FactorySite } from '../../api/fastapi';
import ThemeToggle from '../common/ThemeToggle';
import { useAuth } from '../../contexts/AuthContext';

interface HeaderProps {
  activeTab: NavigationTab;
  factory: string;
  factories: FactorySite[];
  onFactoryChange: (factoryId: string) => void;
}

const TAB_TITLES: Record<NavigationTab, string> = {
  diagnosis: '单机 SN 深度诊断',
  error_logs: '批量测试异常看板',
  knowledge_base: '知识库管理',
  settings: '系统管理与 AI 引擎配置',
};

function getInitials(email: string): string {
  const name = email.split('@')[0];
  return name.slice(0, 2).toUpperCase();
}

export default function Header({ activeTab, factory, factories, onFactoryChange }: HeaderProps) {
  const { user, signOut } = useAuth();

  return (
    <header
      className="h-[60px] border-b flex items-center justify-between px-6 shrink-0 shadow-sm z-10 w-full relative"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
        color: 'var(--color-text-primary)',
      }}
    >
      <h1
        className="text-sm font-bold tracking-wide"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {TAB_TITLES[activeTab]}
      </h1>

      <div className="flex items-center gap-4 text-xs font-medium">
        <ThemeToggle />

        <div className="w-px h-5" style={{ backgroundColor: 'var(--color-border)' }} />

        <div className="flex items-center gap-2 mr-2">
          <span
            className="font-bold"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            运行厂区:
          </span>
          <select
            value={factory}
            onChange={(e) => onFactoryChange(e.target.value)}
            className="h-7 px-2 rounded shadow-sm outline-none transition-colors font-bold cursor-pointer appearance-none pr-8 border"
            style={{
              backgroundColor: 'var(--color-bg-secondary)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-primary)',
              backgroundImage: `url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 0.5rem center',
              backgroundSize: '1em 1em',
            }}
          >
            {factories.length === 0 && <option value="">-- 加载中 --</option>}
            {factories.map((f) => (
              <option key={f.factory_id} value={f.factory_id}>
                {f.name}
              </option>
            ))}
          </select>
        </div>

        <div className="w-px h-5" style={{ backgroundColor: 'var(--color-border)' }} />

        {user ? (
          <div className="flex items-center gap-3 pl-2">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center font-bold shadow-sm border text-xs"
              style={{
                background: 'linear-gradient(135deg, #dbeafe, #e0e7ff)',
                color: '#4f46e5',
                borderColor: 'var(--color-border)',
              }}
            >
              {getInitials(user.email ?? '')}
            </div>
            <div className="flex flex-col">
              <span
                className="text-[13px] leading-tight font-bold"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {user.email}
              </span>
              <span
                className="text-[10px] uppercase font-bold tracking-wider"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                在线
              </span>
            </div>
            <button
              onClick={signOut}
              className="p-1.5 rounded-lg hover:opacity-80 transition-opacity"
              title="退出登录"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 ml-2">
            <LogIn className="w-3 h-6" style={{ color: 'var(--color-text-muted)' }} />
            <span className="text-[13px]" style={{ color: 'var(--color-text-secondary)' }}>
              未登录
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
