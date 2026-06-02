export function formatTime(iso: string | null, fallback = '从未'): string {
  if (!iso) return fallback;
  try { return new Date(iso).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }); }
  catch { return iso; }
}

export function formatRelative(iso: string | null): string {
  if (!iso) return '';
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return '刚刚';
    if (mins < 60) return `${mins}分钟前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}小时前`;
    if (hours < 48) return '昨天';
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}天前`;
    return new Date(iso).toLocaleDateString('zh-CN');
  } catch { return ''; }
}
