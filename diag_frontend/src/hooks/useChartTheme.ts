import { useMemo } from 'react';
import { useTheme } from '../contexts/ThemeContext';

export interface ChartTheme {
  isDark: boolean;
  textColor: string;
  gridColor: string;
  bgColor: string;
  borderColor: string;
  accentColor: string;
}

/**
 * 图表主题 hook
 * 统一 Recharts 组件的颜色配置
 */
export function useChartTheme(): ChartTheme {
  const { theme } = useTheme();

  return useMemo(() => {
    const isDark = theme === 'dark';
    return {
      isDark,
      textColor: isDark ? '#94a3b8' : '#64748b',
      gridColor: isDark ? '#334155' : '#f1f5f9',
      bgColor: isDark ? '#1e293b' : '#ffffff',
      borderColor: isDark ? '#334155' : '#e2e8f0',
      accentColor: '#4f46e5',
    };
  }, [theme]);
}