import React from 'react';
import { Bot, Search, LayoutDashboard, Library, MessageSquareText, Settings, Cpu, X } from 'lucide-react';
import type { NavigationTab } from '../../types';

interface SidebarProps {
  activeTab: NavigationTab;
  onTabChange: (tab: NavigationTab) => void;
  open: boolean;
  onClose: () => void;
}

const navItems: { icon: React.ReactNode; label: string; tab: NavigationTab }[] = [
  { icon: <Search className="w-4 h-4" />, label: '单机深度诊断', tab: 'diagnosis' },
  { icon: <LayoutDashboard className="w-4 h-4" />, label: '批量异常看板', tab: 'error_logs' },
  { icon: <Library className="w-4 h-4" />, label: '知识库管理', tab: 'knowledge_base' },
  { icon: <MessageSquareText className="w-4 h-4" />, label: '反馈管理', tab: 'feedback' },
];

export default function Sidebar({ activeTab, onTabChange, open, onClose }: SidebarProps) {
  return (
    <>
      {open && (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/45 md:hidden"
          onClick={onClose}
          aria-label="关闭导航菜单"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-56 shrink-0 flex-col text-white shadow-xl transition-transform duration-200 md:static md:z-20 md:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ backgroundColor: 'var(--color-bg-sidebar)' }}
      >
        <div className="flex h-[60px] shrink-0 items-center border-b" style={{ borderColor: 'var(--color-border-sidebar)' }}>
          <button
            onClick={() => onTabChange('diagnosis')}
            className="flex h-full min-w-0 flex-1 cursor-pointer select-none items-center px-4 text-left transition-opacity hover:opacity-80"
          >
            <Bot className="mr-2 h-6 w-6 shrink-0 text-blue-400" />
            <span className="text-[15px] font-bold tracking-wide text-white">WeaveEye</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="mr-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-300 md:hidden"
            aria-label="关闭导航菜单"
            title="关闭导航"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-1.5 px-3 py-5">
          <div
            className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-sidebar-muted)' }}
          >
            功能导航
          </div>
          {navItems.map((item) => (
            <NavItem
              key={item.tab}
              icon={item.icon}
              label={item.label}
              active={activeTab === item.tab}
              onClick={() => onTabChange(item.tab)}
            />
          ))}
        </div>

        <div className="p-4" style={{ borderTop: '1px solid var(--color-border-sidebar)' }}>
          <NavItem
            icon={<Settings className="h-4 w-4" />}
            label="系统设置"
            active={activeTab === 'settings'}
            onClick={() => onTabChange('settings')}
          />
          <div
            className="mt-3 flex items-center gap-2 rounded-lg px-3 py-2"
            style={{ backgroundColor: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.15)' }}
          >
            <Cpu className="h-3.5 w-3.5 shrink-0 text-blue-400" />
            <span className="text-[11px] font-medium" style={{ color: 'var(--color-text-sidebar-muted)' }}>
              海光DCU 算力平台
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}

function NavItem({ icon, label, active, onClick }: NavItemProps) {
  return (
    <button
      onClick={onClick}
      className="relative flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[13px] transition-all duration-200"
      style={
        active
          ? {
              backgroundColor: 'rgba(59, 130, 246, 0.9)',
              color: '#fff',
              boxShadow: '0 2px 8px rgba(59, 130, 246, 0.4)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              fontWeight: 600,
            }
          : {
              color: 'var(--color-text-sidebar)',
            }
      }
    >
      <span style={{ color: active ? '#dbeafe' : 'var(--color-text-sidebar-muted)' }}>
        {icon}
      </span>
      {label}
      {active && (
        <div
          className="absolute left-[-12px] top-1/2 -translate-y-1/2 w-1.5 h-6 rounded"
          style={{
            backgroundColor: '#60a5fa',
            boxShadow: '0 0 8px rgba(96, 165, 250, 0.5)',
          }}
        />
      )}
    </button>
  );
}
