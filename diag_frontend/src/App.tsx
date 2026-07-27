import { useState, useEffect } from 'react';
import type { NavigationTab } from './types';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ToastProvider } from './contexts/ToastContext';
import AuthGuard from './components/auth/AuthGuard';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import Footer from './components/layout/Footer';
import DiagnosisTab from './components/diagnosis/DiagnosisTab';
import ErrorLogsTab from './components/error-logs/ErrorLogsTab';
import SettingsTab from './components/settings/SettingsTab';
import KnowledgeBaseTab from './components/knowledge-base/KnowledgeBaseTab';
import FeedbackManagementTab from './components/feedback/FeedbackManagementTab';
import UserAnalyticsTab from './components/user-analytics/UserAnalyticsTab';
import { analyticsApi, factoryApi, userAnalyticsApi, FactorySite } from './api/fastapi';

const FACTORY_STORAGE_KEY = 'weaveeye:selected-factory';

function AppContent() {
  const { theme } = useTheme();
  const { user } = useAuth();
  const isAdmin = user?.is_admin === true;
  const [activeTab, setActiveTab] = useState<NavigationTab>('diagnosis');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [factorySites, setFactorySites] = useState<FactorySite[]>([]);
  const [factory, setFactory] = useState('');

  const handleFactoryChange = (factoryId: string) => {
    setFactory(factoryId);
    if (factoryId) localStorage.setItem(FACTORY_STORAGE_KEY, factoryId);
    else localStorage.removeItem(FACTORY_STORAGE_KEY);
  };

  // 加载厂区列表，并预热分析看板缓存
  useEffect(() => {
    factoryApi.list().then((resp) => {
      if (resp.success && resp.data && resp.data.length > 0) {
        setFactorySites(resp.data);
        const cachedFactory = localStorage.getItem(FACTORY_STORAGE_KEY);
        const selectedFactory = resp.data.some(
          (site) => site.factory_id === cachedFactory,
        ) ? cachedFactory as string : resp.data[0].factory_id;
        handleFactoryChange(selectedFactory);
        // 预热分析看板（预计算统计）
        analyticsApi.getSummary({ factory_id: selectedFactory, days: 30 }).catch(() => {});
        analyticsApi.getDailyStats({ factory_id: selectedFactory, days: 30 }).catch(() => {});
      }
    });
  }, []);

  useEffect(() => {
    void userAnalyticsApi.trackFeature(activeTab);
  }, [activeTab]);

  const handleTabChange = (tab: NavigationTab) => {
    if (tab === 'user_analytics' && !isAdmin) return;
    setActiveTab(tab);
    setSidebarOpen(false);
  };

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
      <Sidebar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        isAdmin={isAdmin}
      />

      <div className="relative flex h-full min-w-0 flex-1 flex-col overflow-hidden">
        <Header
          activeTab={activeTab}
          factory={factory}
          factories={factorySites}
          onFactoryChange={handleFactoryChange}
          onMenuClick={() => setSidebarOpen(true)}
        />

        <div
          className="flex-1 flex flex-col min-h-0 relative"
          style={{ backgroundColor: 'var(--color-bg-primary)' }}
        >
          {activeTab === 'diagnosis' && (
            <DiagnosisTab
              factory={factory}
              factorySites={factorySites}
              onFactoryChange={handleFactoryChange}
            />
          )}
          {activeTab === 'error_logs' && <ErrorLogsTab factory={factory} factorySites={factorySites} />}
          {activeTab === 'knowledge_base' && <KnowledgeBaseTab />}
          {activeTab === 'feedback' && <FeedbackManagementTab factory={factory} factorySites={factorySites} />}
          {activeTab === 'user_analytics' && isAdmin && <UserAnalyticsTab />}
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
        <ToastProvider>
          <AuthGuard>
            <AppContent />
          </AuthGuard>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
