import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="p-2 rounded-lg transition-all duration-200 cursor-pointer"
      style={{
        backgroundColor: 'var(--color-accent-light)',
        color: 'var(--color-text-primary)',
      }}
      aria-label={theme === 'light' ? '切换到暗色主题' : '切换到亮色主题'}
    >
      {theme === 'light' ? (
        <Moon className="w-4 h-4" />
      ) : (
        <Sun className="w-4 h-4" />
      )}
    </button>
  );
}