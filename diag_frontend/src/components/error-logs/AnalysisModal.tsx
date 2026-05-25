import { Bot, Sparkles, AlertTriangle, Wrench, Terminal, RefreshCw, X } from 'lucide-react';
import type { ErrorLogRow } from '../../types';
import { DEFAULT_ANALYSIS_RESULT } from '../../data/mockData';

interface AnalysisModalProps {
  selectedLog: ErrorLogRow | null;
  analyzingId: string | null;
  analysisResult: Record<string, string>;
  onClose: () => void;
}

export default function AnalysisModal({
  selectedLog,
  analyzingId,
  analysisResult,
  onClose,
}: AnalysisModalProps) {
  if (!selectedLog) return null;

  const isAnalyzing = analyzingId === selectedLog.id;
  const result = analysisResult[selectedLog.id] || DEFAULT_ANALYSIS_RESULT;
  const isLoading = isAnalyzing && !analysisResult[selectedLog.id];

  return (
    <div
      className="absolute inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
      style={{ backgroundColor: 'rgba(15, 23, 42, 0.4)' }}
    >
      <div
        className="w-full max-w-4xl max-h-[85vh] shadow-2xl rounded-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-300 border"
        style={{
          backgroundColor: 'var(--color-bg-secondary)',
          borderColor: 'var(--color-border)',
        }}
      >
        <div
          className="h-[65px] px-6 border-b flex items-center justify-between shrink-0"
          style={{
            backgroundColor: 'var(--color-bg-primary)',
            borderColor: 'var(--color-border)',
          }}
        >
          <h3 className="font-bold flex items-center gap-2.5 text-base" style={{ color: 'var(--color-text-primary)' }}>
            <span
              className="w-8 h-8 rounded-lg flex items-center justify-center shadow-sm"
              style={{
                backgroundColor: 'var(--color-accent-light)',
                color: 'var(--color-accent)',
              }}
            >
              <Bot className="w-5 h-5" />
            </span>
            大模型缺陷诊断与修复研判中心
          </h3>
          <button
            onClick={onClose}
            className="p-2 rounded-full transition-colors active:scale-95"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 md:p-8 flex flex-col md:flex-row gap-8 custom-scrollbar">
          <div className="w-full md:w-1/3 space-y-5 flex flex-col">
            <h4
              className="text-[12px] font-bold uppercase tracking-widest border-b pb-2"
              style={{
                color: 'var(--color-text-secondary)',
                borderColor: 'var(--color-border)',
              }}
            >
              异常追踪快照
            </h4>

            <div className="space-y-4">
              <div>
                <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>
                  被测对象 SN
                </div>
                <div
                  className="text-sm font-mono font-semibold px-2.5 py-1 rounded border inline-flex shadow-sm"
                  style={{
                    backgroundColor: 'var(--color-bg-primary)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  {selectedLog.sn}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>
                    测试项目
                  </div>
                  <div className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
                    {selectedLog.testItem}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>
                    拦截状态
                  </div>
                  <div
                    className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold shadow-sm border"
                    style={{
                      backgroundColor: 'rgba(239, 68, 68, 0.1)',
                      color: '#dc2626',
                      borderColor: 'rgba(239, 68, 68, 0.2)',
                    }}
                  >
                    {selectedLog.status}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>
                    发生时间
                  </div>
                  <div className="text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                    {selectedLog.testTime}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] mb-1" style={{ color: 'var(--color-text-secondary)' }}>
                    判定结论
                  </div>
                  <div className="text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                    {selectedLog.decision}
                  </div>
                </div>
              </div>
            </div>

            <div
              className="p-4 mx-[-8px] rounded-xl shadow-inner border mt-2 flex-1"
              style={{ backgroundColor: '#1a1b26', borderColor: '#334155' }}
            >
              <div
                className="text-[11px] mb-3 flex items-center gap-2 border-b pb-2"
                style={{ color: '#64748b', borderColor: '#334155' }}
              >
                <Terminal className="w-3.5 h-3.5" /> Console 终端拦截输出
              </div>
              <div className="font-mono text-[12px] text-red-300/90 leading-relaxed break-words whitespace-pre-wrap">
                {`> 故障日志路径
> ${selectedLog.logPath}
> 故障类型: ${selectedLog.faultTypes || '-'}`}
              </div>
            </div>
          </div>

          <div
            className="w-full md:w-2/3 flex flex-col min-h-0 border-l pl-0 md:pl-8"
            style={{ borderColor: 'var(--color-border)' }}
          >
            <h4
              className="text-[12px] font-bold uppercase tracking-widest border-b pb-2 flex items-center gap-2 mb-4"
              style={{
                color: 'var(--color-text-secondary)',
                borderColor: 'var(--color-border)',
              }}
            >
              <Sparkles className="w-4 h-4" style={{ color: 'var(--color-accent)' }} /> 高维图谱聚类分析结果
            </h4>

            <div
              className="rounded-xl p-6 relative overflow-hidden transition-all shadow-sm flex-1 flex flex-col border"
              style={{
                backgroundColor: 'var(--color-accent-light)',
                borderColor: 'var(--color-border)',
              }}
            >
              {isAnalyzing && (
                <div
                  className="absolute top-0 left-0 w-full h-1 animate-pulse"
                  style={{ backgroundColor: 'var(--color-accent)' }}
                />
              )}

              {isLoading ? (
                <div className="flex flex-col items-center justify-center flex-1 py-12 gap-5">
                  <RefreshCw className="w-10 h-10 animate-spin" style={{ color: 'var(--color-accent)' }} />
                  <div className="flex flex-col items-center gap-2 font-medium text-[13px]" style={{ color: 'var(--color-accent)' }}>
                    <div className="flex gap-2 mb-2">
                      <div
                        className="w-2 h-2 rounded-full animate-bounce"
                        style={{ backgroundColor: 'var(--color-accent)' }}
                      />
                      <div
                        className="w-2 h-2 rounded-full animate-bounce"
                        style={{ backgroundColor: 'var(--color-accent)', animationDelay: '0.15s' }}
                      />
                      <div
                        className="w-2 h-2 rounded-full animate-bounce"
                        style={{ backgroundColor: 'var(--color-accent)', animationDelay: '0.3s' }}
                      />
                    </div>
                    正在交叉验证 MES 流水线与历史缺陷知识库...
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
                  <div className="space-y-3">
                    <h5
                      className="flex items-center gap-1.5 text-xs font-bold"
                      style={{ color: 'var(--color-accent)' }}
                    >
                      <AlertTriangle className="w-3.5 h-3.5" /> 核心诱因推盘
                    </h5>
                    <div
                      className="text-[13px] leading-relaxed p-3.5 rounded-lg border shadow-sm"
                      style={{
                        backgroundColor: 'var(--color-bg-secondary)',
                        borderColor: 'var(--color-border)',
                        color: 'var(--color-text-primary)',
                      }}
                    >
                      {result}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h5 className="flex items-center gap-1.5 text-xs font-bold text-emerald-700">
                      <Wrench className="w-3.5 h-3.5" /> 修复工程指引
                    </h5>
                    <ul
                      className="text-[13px] space-y-2 p-4 rounded-lg border shadow-sm"
                      style={{
                        backgroundColor: 'var(--color-bg-secondary)',
                        borderColor: 'rgba(16, 185, 129, 0.2)',
                        color: 'var(--color-text-primary)',
                      }}
                    >
                      <li className="flex gap-2">
                        <span className="text-emerald-500 font-bold">•</span>
                        <span>检查主板关键阻抗节点，推荐执行 `diag --verify` 强制复位阻抗匹配系数。</span>
                      </li>
                      <li className="flex gap-2">
                        <span className="text-emerald-500 font-bold">•</span>
                        <span>若阻抗调节无效，系统建议对相应 IC 组件执行重新校准或过站阻行操作。</span>
                      </li>
                    </ul>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}