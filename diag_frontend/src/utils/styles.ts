// Shared style objects to avoid repetition across components
export const S = {
  // Card styles
  card: { backgroundColor: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' },
  mono: { backgroundColor: '#1a1b26', borderColor: '#334155', color: '#e2e8f0' },
  // Text colors
  muted: { color: 'var(--color-text-muted)' },
  accent: { color: 'var(--color-accent)' },
  success: { color: '#10b981' },
  error: { color: '#ef4444' },
} as const;

export const cardClass = 'rounded-xl border shadow-sm';
export const badgeClass = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium';