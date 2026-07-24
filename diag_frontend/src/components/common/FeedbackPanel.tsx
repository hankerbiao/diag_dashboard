import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { diagnosisApi } from '../../api/fastapi';
import { useToast } from '../../contexts/ToastContext';

interface FeedbackPanelProps {
  historyId?: string;
  sn: string;
  factory: string;
  diagnosisContext?: string;
}

type Rating = 'solved' | 'partially' | 'unsolved';

export default function FeedbackPanel({
  historyId,
  sn,
  factory,
  diagnosisContext,
}: FeedbackPanelProps) {
  const { toast } = useToast();
  const [selectedRating, setSelectedRating] = useState<Rating | null>(null);
  const [comment, setComment] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showComment, setShowComment] = useState(false);

  // 检查是否已有反馈（从历史记录读取）
  useEffect(() => {
    if (historyId) {
      diagnosisApi.getSnHistoryDetail(historyId).then((res) => {
        if (res.success && res.data?.feedback_rating) {
          setSubmitted(true);
        }
      }).catch(() => {});
    }
  }, [historyId]);

  const needsComment = selectedRating === 'partially' || selectedRating === 'unsolved';
  const isValid = selectedRating !== null && (!needsComment || comment.trim().length > 0);

  const handleSelect = (rating: Rating) => {
    setSelectedRating(rating);
    if (rating === 'partially' || rating === 'unsolved') {
      setShowComment(true);
    } else {
      setShowComment(false);
      // 自动提交"可以解决"
      handleSubmit(rating);
    }
  };

  const handleSubmit = async (rating?: Rating) => {
    const finalRating = rating || selectedRating;
    if (!finalRating || loading) return;

    setLoading(true);
    setError('');

    try {
      const res = await diagnosisApi.submitFeedback({
        history_id: historyId,
        sn,
        factory,
        rating: finalRating,
        comment: needsComment && selectedRating === finalRating ? comment.trim() : undefined,
        diagnosis_context: diagnosisContext,
      });

      if (res.success) {
        setSubmitted(true);
        toast('success', '感谢您的反馈！');
      } else {
        setError(res.error || '提交失败');
        toast('error', res.error || '提交失败');
      }
    } catch {
      setError('网络错误');
      toast('error', '网络错误，反馈提交失败');
    } finally {
      setLoading(false);
    }
  };

  // 已提交或已有反馈 - 不显示
  if (submitted) {
    return null;
  }

  return (
    <div
      className="mx-2 mb-2 flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 sm:mx-4 sm:mb-3 sm:flex-nowrap sm:gap-3 sm:px-4 sm:py-2.5"
      style={{
        backgroundColor: 'var(--color-bg-primary)',
        borderColor: 'var(--color-border)',
      }}
    >
      <span className="hidden shrink-0 text-[12px] sm:inline" style={{ color: 'var(--color-text-secondary)' }}>
        帮助改进 AI
      </span>

      {/* 评分按钮组 */}
      <div className="grid w-full grid-cols-3 items-center gap-1.5 sm:flex sm:w-auto">
        <button
          type="button"
          onClick={() => handleSelect('solved')}
          className="flex items-center justify-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium transition-all sm:px-2.5 sm:text-[12px]"
          style={{
            backgroundColor: selectedRating === 'solved' ? 'rgba(5, 150, 105, 0.15)' : 'rgba(5, 150, 105, 0.08)',
            border: `1px solid ${selectedRating === 'solved' ? 'rgba(5, 150, 105, 0.4)' : 'transparent'}`,
            color: '#059669',
          }}
          title="诊断结果准确，能直接解决问题"
        >
          <CheckCircle className="w-3.5 h-3.5" />
          可以解决
        </button>

        <button
          type="button"
          onClick={() => handleSelect('partially')}
          className="flex items-center justify-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium transition-all sm:px-2.5 sm:text-[12px]"
          style={{
            backgroundColor: selectedRating === 'partially' ? 'rgba(217, 119, 6, 0.15)' : 'rgba(217, 119, 6, 0.08)',
            border: `1px solid ${selectedRating === 'partially' ? 'rgba(217, 119, 6, 0.4)' : 'transparent'}`,
            color: '#d97706',
          }}
          title="方向正确但细节有偏差，或只能解决部分问题"
        >
          部分参考
        </button>

        <button
          type="button"
          onClick={() => handleSelect('unsolved')}
          className="flex items-center justify-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium transition-all sm:px-2.5 sm:text-[12px]"
          style={{
            backgroundColor: selectedRating === 'unsolved' ? 'rgba(220, 38, 38, 0.15)' : 'rgba(220, 38, 38, 0.08)',
            border: `1px solid ${selectedRating === 'unsolved' ? 'rgba(220, 38, 38, 0.4)' : 'transparent'}`,
            color: '#dc2626',
          }}
          title="诊断结果完全不对，无法帮助解决问题"
        >
          <XCircle className="w-3.5 h-3.5" />
          没有帮助
        </button>
      </div>

      {/* 提示语 */}
      {!showComment && (
        <span className="hidden shrink-0 text-[11px] 2xl:inline" style={{ color: 'var(--color-text-muted)' }}>
          反馈越多，系统越懂您的问题
        </span>
      )}

      {/* 反馈输入框（需要时显示） */}
      {showComment && (
        <div className="flex w-full flex-1 items-center gap-2 sm:w-auto">
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="补充说明，帮助 AI 学习..."
            className="flex-1 px-2.5 py-1 rounded-md border text-[12px] transition-colors focus:outline-none"
            style={{
              backgroundColor: 'var(--color-bg-secondary)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-primary)',
            }}
            maxLength={200}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && isValid) handleSubmit();
            }}
          />
          <button
            type="button"
            onClick={() => handleSubmit()}
            disabled={!isValid || loading}
            className="shrink-0 p-1.5 rounded-md transition-colors disabled:opacity-50"
            style={{ backgroundColor: 'var(--color-accent)', color: 'white' }}
          >
            {loading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <span className="text-[11px] font-medium px-1">发送</span>
            )}
          </button>
        </div>
      )}

      {error && (
        <span className="text-[11px]" style={{ color: '#dc2626' }}>{error}</span>
      )}
    </div>
  );
}
