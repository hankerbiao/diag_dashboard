import React from 'react';
import { Bot, Search, LayoutDashboard, Library, Settings, Cpu } from 'lucide-react';
import type { NavigationTab } from '../../types';

interface SidebarProps {
  activeTab: NavigationTab;
  onTabChange: (tab: NavigationTab) => void;
}

const navItems: { icon: React.ReactNode; label: string; tab: NavigationTab }[] = [
  { icon: <Search className="w-4 h-4" />, label: '单机深度诊断', tab: 'diagnosis' },
  { icon: <LayoutDashboard className="w-4 h-4" />, label: '批量异常看板', tab: 'error_logs' },
  { icon: <Library className="w-4 h-4" />, label: '知识库管理', tab: 'knowledge_base' },
];

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <div
      className="w-56 text-white flex flex-col shadow-xl z-20 shrink-0"
      style={{ backgroundColor: 'var(--color-bg-sidebar)' }}
    >
      <div
        className="h-[60px] flex items-center px-4 border-b shrink-0 select-none"
        style={{ borderColor: 'var(--color-border-sidebar)' }}
      >
        <Bot className="w-6 h-6 text-blue-400 mr-2 shrink-0" />
        <span className="font-bold text-[15px] tracking-wide text-white">WeaveEye</span>
      </div>

      <div className="flex-1 py-5 flex flex-col gap-1.5 px-3">
        <div
          className="text-[11px] font-semibold mb-2 px-2 uppercase tracking-wider"
          style={{ color: 'var(--color-text-sidebar-muted)' }}
        >
          功能导航
        </div>
        {navItems.map((item) => (
          <NavItem
            icon={item.icon}
            label={item.label}
            active={activeTab === item.tab}
            onClick={() => onTabChange(item.tab)}
          />
        ))}
      </div>

      <div className="p-4" style={{ borderTop: '1px solid var(--color-border-sidebar)' }}>
        <NavItem
          icon={<Settings className="w-4 h-4" />}
          label="系统设置"
          active={activeTab === 'settings'}
          onClick={() => onTabChange('settings')}
        />
        <div
          className="flex items-center gap-2 mt-3 px-3 py-2 rounded-lg"
          style={{ backgroundColor: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.15)' }}
        >
          <Cpu className="w-3.5 h-3.5 text-blue-400 shrink-0" />
          <span className="text-[11px] font-medium" style={{ color: 'var(--color-text-sidebar-muted)' }}>
            海光DCU 算力平台
          </span>
        </div>
      </div>
    </div>
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
      className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] transition-all duration-200 text-left relative cursor-pointer"
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