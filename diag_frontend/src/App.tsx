import { useState } from 'react';
import type { NavigationTab, AppSettings, FactoryLocation } from './types';
import { DEFAULT_SETTINGS } from './types';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { AuthProvider } from './contexts/AuthContext';
import AuthGuard from './components/auth/AuthGuard';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import Footer from './components/layout/Footer';
import DiagnosisTab from './components/diagnosis/DiagnosisTab';
import ErrorLogsTab from './components/error-logs/ErrorLogsTab';
import SettingsTab from './components/settings/SettingsTab';

function AppContent() {
  const { theme } = useTheme();
  const [activeTab, setActiveTab] = useState<NavigationTab>('diagnosis');
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [factory, setFactory] = useState<FactoryLocation>('天津');

  return (
    <div
      className={`flex h-screen w-full font-sans text-slate-800 overflow-hidden ${
        theme === 'dark' ? 'dark' : ''
      }`}
      style={{
        backgroundColor: 'var(--color-bg-primary)',
        color: 'var(--color-text-primary)',
      }}
    >
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="flex-1 flex flex-col relative overflow-hidden h-full">
        <Header
          activeTab={activeTab}
          factory={factory}
          onFactoryChange={setFactory}
        />

        <div
          className="flex-1 flex flex-col min-h-0 relative"
          style={{ backgroundColor: 'var(--color-bg-primary)' }}
        >
          {activeTab === 'diagnosis' && <DiagnosisTab settings={settings} factory={factory} />}
          {activeTab === 'error_logs' && <ErrorLogsTab factory={factory} />}
          {activeTab === 'settings' && <SettingsTab settings={settings} setSettings={setSettings} />}
        </div>

        <Footer activeKBsCount={settings.activeKBs.length} />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AuthGuard>
          <AppContent />
        </AuthGuard>
      </AuthProvider>
    </ThemeProvider>
  );
}
