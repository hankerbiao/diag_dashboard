import { LogIn, LogOut, Menu } from 'lucide-react';
import type { NavigationTab } from '../../types';
import type { FactorySite } from '../../api/fastapi';
import ThemeToggle from '../common/ThemeToggle';
import { useAuth } from '../../contexts/AuthContext';

interface HeaderProps {
  activeTab: NavigationTab;
  factory: string;
  factories: FactorySite[];
  onFactoryChange: (factoryId: string) => void;
  onMenuClick: () => void;
}

const TAB_TITLES: Record<NavigationTab, string> = {
  diagnosis: '单机 SN 深度诊断',
  error_logs: '批量测试异常看板',
  knowledge_base: '知识库管理',
  feedback: '诊断反馈管理',
  user_analytics: '用户数据与使用分析',
  settings: '系统管理与 AI 引擎配置',
};

const TABS_WITH_FACTORY = new Set<NavigationTab>(['error_logs', 'feedback']);

function getInitials(value: string): string {
  const name = value.includes('@') ? value.split('@')[0] : value;
  return name.slice(0, 2).toUpperCase();
}

export default function Header({ activeTab, factory, factories, onFactoryChange, onMenuClick }: HeaderProps) {
  const { user, signOut } = useAuth();
  const displayName = user?.name || user?.itcode || user?.email || '';

  return (
    <header
      className="relative z-10 flex h-[60px] w-full shrink-0 items-center justify-between gap-3 border-b px-3 shadow-sm sm:px-6"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
        color: 'var(--color-text-primary)',
      }}
    >
      <div className="flex min-w-0 items-center gap-2">
        <button
          type="button"
          onClick={onMenuClick}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg md:hidden"
          style={{ color: 'var(--color-text-secondary)' }}
          aria-label="打开导航菜单"
          title="打开导航"
        >
          <Menu className="h-5 w-5" />
        </button>
        <h1
          className="truncate text-xs font-bold sm:text-sm"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {TAB_TITLES[activeTab]}
        </h1>
      </div>

      <div className="flex shrink-0 items-center gap-2 text-xs font-medium sm:gap-4">
        <ThemeToggle />

        {TABS_WITH_FACTORY.has(activeTab) && (
          <>
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
          </>
        )}

        {user ? (
          <div className="flex items-center gap-2 sm:gap-3 sm:pl-2">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center font-bold shadow-sm border text-xs"
              style={{
                background: 'linear-gradient(135deg, #dbeafe, #e0e7ff)',
                color: '#4f46e5',
                borderColor: 'var(--color-border)',
              }}
            >
              {getInitials(displayName)}
            </div>
            <div className="hidden flex-col lg:flex">
              <span
                className="text-[13px] leading-tight font-bold flex items-center gap-2"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {displayName}
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
