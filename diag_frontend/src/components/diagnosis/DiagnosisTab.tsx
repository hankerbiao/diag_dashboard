import { useState } from 'react';
import { Bot, ChevronUp, Paperclip, Mic } from 'lucide-react';
import type { AppSettings } from '../../types';
import type { FactorySite } from '../../api/fastapi';
import DiagnosisInput from './DiagnosisInput';
import DiagnosisResult from './DiagnosisResult';
import ReferenceData from './ReferenceData';

interface DiagnosisTabProps {
  settings: AppSettings;
  factory: string;
  factorySites: FactorySite[];
}

export default function DiagnosisTab({ settings, factory, factorySites }: DiagnosisTabProps) {
  const [sn, setSn] = useState('CN-0M3821-72911-39A-0021');

  return (
    <div
      className="flex-1 flex flex-col min-h-0"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      <DiagnosisInput sn={sn} onSnChange={setSn} />

      <div className="flex-1 flex min-h-0">
        <DiagnosisResult sn={sn} />
        <ReferenceData factory={factory} factorySites={factorySites} />
      </div>

      <div
        className="p-4 border-t flex items-center gap-3 shrink-0 shadow-[0_-10px_20px_rgba(0,0,0,0.02)] z-10"
        style={{
          backgroundColor: 'var(--color-bg-secondary)',
          borderColor: 'var(--color-border)',
        }}
      >
        <button
          className="p-2.5 rounded-full shrink-0 transition-colors"
          style={{
            backgroundColor: 'var(--color-bg-primary)',
            color: 'var(--color-text-secondary)',
          }}
        >
          <Paperclip className="w-5 h-5" />
        </button>
        <div className="flex-1 relative group">
          <input
            type="text"
            placeholder="键入补充自然语言提问，或下达追加分析指令..."
            className="w-full h-11 rounded-full pl-5 pr-12 text-[13px] outline-none transition-all shadow-sm"
            style={{
              border: '1px solid var(--color-border)',
              backgroundColor: 'var(--color-bg-primary)',
              color: 'var(--color-text-primary)',
            }}
          />
          <button
            className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            <Mic className="w-5 h-5" />
          </button>
        </div>
        <button
          className="w-11 h-11 text-white rounded-full flex items-center justify-center shadow-lg transition-all hover:scale-105 active:scale-95 shrink-0"
          style={{
            backgroundColor: 'var(--color-accent)',
            boxShadow: '0 4px 10px -2px var(--color-shadow)',
          }}
        >
          <ChevronUp className="w-6 h-6" />
        </button>
      </div>
    </div>
  );
}