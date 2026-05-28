import { useState, useEffect } from 'react';
import type { NavigationTab } from './types';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { AuthProvider } from './contexts/AuthContext';
import AuthGuard from './components/auth/AuthGuard';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import Footer from './components/layout/Footer';
import DiagnosisTab from './components/diagnosis/DiagnosisTab';
import ErrorLogsTab from './components/error-logs/ErrorLogsTab';
import SettingsTab from './components/settings/SettingsTab';
import KnowledgeBaseTab from './components/knowledge-base/KnowledgeBaseTab';
import { analyticsApi, factoryApi, FactorySite } from './api/fastapi';

function AppContent() {
  const { theme } = useTheme();
  const [activeTab, setActiveTab] = useState<NavigationTab>('diagnosis');
  const [factorySites, setFactorySites] = useState<FactorySite[]>([]);
  const [factory, setFactory] = useState('');

  // 加载厂区列表，并预热分析看板缓存
  useEffect(() => {
    factoryApi.list().then((resp) => {
      if (resp.success && resp.data && resp.data.length > 0) {
        setFactorySites(resp.data);
        const firstFactory = resp.data[0].factory_id;
        setFactory(firstFactory);
        // 预热分析看板（带上厂区ID）
        const trends = ['day', 'week', 'month'] as const;
        trends.forEach((trend) => {
          analyticsApi.getInsights({ factory_id: firstFactory, days: 30, trend }).catch(() => {});
        });
      }
    });
  }, []);

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
          factories={factorySites}
          onFactoryChange={setFactory}
        />

        <div
          className="flex-1 flex flex-col min-h-0 relative"
          style={{ backgroundColor: 'var(--color-bg-primary)' }}
        >
          {activeTab === 'diagnosis' && <DiagnosisTab factory={factory} factorySites={factorySites} />}
          {activeTab === 'error_logs' && <ErrorLogsTab factory={factory} factorySites={factorySites} />}
          {activeTab === 'knowledge_base' && <KnowledgeBaseTab />}
          {activeTab === 'settings' && <SettingsTab />}
        </div>

        <Footer />
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
