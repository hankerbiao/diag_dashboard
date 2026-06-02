import { CheckCircle2, XCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import { isTestFailed, isTestPassed } from '../../utils/testStatus';

interface ResultBadgeProps {
  status: string;
  icon?: ReactNode;
}

export function isSuccessStatus(status: string): boolean {
  return isTestPassed(status);
}

export function isFailureStatus(status: string): boolean {
  return isTestFailed(status);
}

/**
 * 结果状态徽章组件
 * 根据状态显示成功/失败/未知三种样式
 */
export default function ResultBadge({ status, icon }: ResultBadgeProps) {
  const isSuccess = isSuccessStatus(status);
  const isFail = isFailureStatus(status);

  let config = {
    icon: icon as ReactNode,
    color: '#64748b',
    bg: 'rgba(100,116,139,0.1)',
    border: 'rgba(100,116,139,0.2)',
  };

  if (isFail) {
    config = {
      icon: <XCircle className="w-3 h-3" />,
      color: '#dc2626',
      bg: 'rgba(239,68,68,0.1)',
      border: 'rgba(239,68,68,0.2)',
    };
  } else if (isSuccess) {
    config = {
      icon: <CheckCircle2 className="w-3 h-3" />,
      color: '#16a34a',
      bg: 'rgba(22,163,74,0.1)',
      border: 'rgba(22,163,74,0.2)',
    };
  }

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold border"
      style={{ backgroundColor: config.bg, color: config.color, borderColor: config.border }}
    >
      {config.icon}
      {status || '-'}
    </span>
  );
}