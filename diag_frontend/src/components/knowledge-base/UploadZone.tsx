import { useState, useRef, useCallback } from 'react';
import { UploadCloud, Plus, Share2, X, FileText } from 'lucide-react';
import { knowledgeBaseApi } from '../../api/fastapi';

interface UploadZoneProps {
  onUploaded: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export default function UploadZone({ onUploaded }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [title, setTitle] = useState('');
  const [tags, setTags] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    setFiles((prev) => [...prev, ...Array.from(newFiles)]);
  }, []);

  const removeFile = (i: number) => setFiles((prev) => prev.filter((_, idx) => idx !== i));

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    try {
      for (const file of files) {
        await knowledgeBaseApi.upload(file, title || undefined, undefined, tags || undefined);
      }
      setFiles([]);
      setTitle('');
      setTags('');
      onUploaded();
    } catch {
      // silent
    } finally {
      setUploading(false);
    }
  };

  const handleOpenPicker = () => inputRef.current?.click();

  return (
    <div>
      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center transition-all bg-white shadow-sm ${
          isDragging
            ? 'border-blue-500 bg-blue-50/50 scale-[1.01]'
            : 'border-slate-300 hover:border-blue-400 hover:bg-slate-50'
        }`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => { e.preventDefault(); setIsDragging(false); addFiles(e.dataTransfer.files); }}
      >
        <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-4 text-blue-500 shadow-sm border border-blue-100">
          <UploadCloud className="w-8 h-8" />
        </div>
        <h3 className="text-[15px] font-bold text-slate-700 mb-2">点击选择文件，或将文件拖曳至此</h3>
        <p className="text-[13px] text-slate-500 mb-6 text-center max-w-md leading-relaxed">
          支持 PDF, DOCX, TXT, CSV, Markdown 等常见文本及表格格式类型。<br/>
          引擎将自动完成排版解析、图文混排抽取与语义分块 (Chunking)。
        </p>
        <button
          onClick={handleOpenPicker}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-bold shadow-md shadow-blue-500/20 transition-all flex items-center gap-2 active:scale-95 border border-blue-700"
        >
          <Plus className="w-4 h-4" />
          选择本地文件上传
        </button>
        <p className="text-[11px] text-slate-400 mt-3">上传后自动归入默认知识库，由 AI 引擎进行切片与向量化处理</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.docx,.md,.txt,.pptx,.xlsx,.csv,.html,.json,.xml"
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {/* File List (appears after selecting files) */}
      {files.length > 0 && (
        <div className="mt-4 bg-white rounded-xl shadow-sm border border-slate-200 p-4">
          <div className="space-y-2">
            {files.map((f, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] bg-slate-50 border border-slate-200"
              >
                <FileText className="w-4 h-4 shrink-0 text-blue-500" />
                <span className="flex-1 truncate text-slate-700">{f.name}</span>
                <span className="text-slate-400 text-[12px]">{formatSize(f.size)}</span>
                <button
                  onClick={() => removeFile(i)}
                  className="p-0.5 rounded hover:opacity-70 border-0 bg-transparent cursor-pointer text-slate-400 hover:text-rose-500"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>

          {/* Metadata */}
          <div className="flex gap-3 mt-3 items-end">
            <div className="flex-1 space-y-2">
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="统一标题（可选）"
                className="w-full h-9 px-3 rounded-lg text-[13px] outline-none border border-slate-200 bg-slate-50 text-slate-700 placeholder:text-slate-400 focus:border-blue-300 focus:bg-white transition-colors"
              />
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="标签，逗号分隔（可选）"
                className="w-full h-9 px-3 rounded-lg text-[13px] outline-none border border-slate-200 bg-slate-50 text-slate-700 placeholder:text-slate-400 focus:border-blue-300 focus:bg-white transition-colors"
              />
            </div>
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="h-18 px-6 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[13px] font-bold shadow-sm transition-all flex items-center gap-2 border-0 cursor-pointer disabled:opacity-50 shrink-0 active:scale-95"
            >
              {uploading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  上传中…
                </>
              ) : (
                <>
                  <UploadCloud className="w-4 h-4" />
                  上传 {files.length} 个
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
