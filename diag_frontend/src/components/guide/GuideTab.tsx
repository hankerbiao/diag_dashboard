import { useEffect, useRef, useState } from 'react';
import { BookOpen, Info } from 'lucide-react';
import { GUIDE_SECTIONS, type GuideBlock } from './guideSections';

function GuideBlockView({ block }: { block: GuideBlock }) {
  if (block.type === 'paragraph') {
    return (
      <p className="text-[13px] leading-relaxed mb-4" style={{ color: 'var(--color-text-secondary)' }}>
        {block.text}
      </p>
    );
  }

  if (block.type === 'steps') {
    return (
      <ol className="list-decimal list-inside space-y-2 mb-4 text-[13px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
        {block.items.map((item, i) => (
          <li key={i} className="pl-1">
            {item}
          </li>
        ))}
      </ol>
    );
  }

  if (block.type === 'note') {
    return (
      <div
        className="flex gap-3 rounded-lg border px-4 py-3 mb-4 text-[12px] leading-relaxed"
        style={{
          backgroundColor: 'rgba(59, 130, 246, 0.06)',
          borderColor: 'rgba(59, 130, 246, 0.2)',
          color: 'var(--color-text-secondary)',
        }}
      >
        <Info className="w-4 h-4 shrink-0 mt-0.5" style={{ color: 'var(--color-accent)' }} />
        <div>
          {block.title && (
            <span className="font-semibold block mb-1" style={{ color: 'var(--color-text-primary)' }}>
              {block.title}
            </span>
          )}
          {block.text}
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto mb-4 rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
      <table className="w-full text-left text-[12px]">
        <thead style={{ backgroundColor: 'var(--color-bg-secondary)' }}>
          <tr>
            {block.headers.map((h) => (
              <th
                key={h}
                className="px-4 py-2.5 font-semibold border-b"
                style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, ri) => (
            <tr key={ri} className="border-b last:border-b-0" style={{ borderColor: 'var(--color-border)' }}>
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  className="px-4 py-2.5 align-top"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function GuideTab({ embedded = false }: { embedded?: boolean }) {
  const [activeId, setActiveId] = useState(GUIDE_SECTIONS[0]?.id ?? '');
  const contentRef = useRef<HTMLDivElement>(null);
  const sectionPrefix = embedded ? 'settings-guide-' : '';

  useEffect(() => {
    const root = contentRef.current;
    if (!root) return;

    const headings = GUIDE_SECTIONS.map((s) =>
      root.querySelector(`#${sectionPrefix}${s.id}`),
    ).filter(Boolean) as HTMLElement[];
    if (headings.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]?.target?.id) {
          setActiveId(visible[0].target.id.replace(sectionPrefix, ''));
        }
      },
      { root, rootMargin: '-20% 0px -60% 0px', threshold: [0, 0.25, 0.5] },
    );

    headings.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [sectionPrefix]);

  const scrollToSection = (id: string) => {
    setActiveId(id);
    document.getElementById(`${sectionPrefix}${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div
      className={
        embedded
          ? 'flex min-h-[420px] max-h-[640px] rounded-lg border overflow-hidden'
          : 'flex-1 flex min-h-0 overflow-hidden'
      }
      style={{
        backgroundColor: 'var(--color-bg-primary)',
        borderColor: embedded ? 'var(--color-border)' : undefined,
      }}
    >
      <nav
        className="w-52 shrink-0 border-r overflow-y-auto custom-scrollbar py-5 px-3"
        style={{
          backgroundColor: 'var(--color-bg-secondary)',
          borderColor: 'var(--color-border)',
        }}
      >
        <div className="flex items-center gap-2 px-2 mb-4">
          <BookOpen className="w-4 h-4" style={{ color: 'var(--color-accent)' }} />
          <span className="text-[12px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
            目录
          </span>
        </div>
        <ul className="space-y-0.5">
          {GUIDE_SECTIONS.map((section) => (
            <li key={section.id}>
              <button
                type="button"
                onClick={() => scrollToSection(section.id)}
                className="w-full text-left px-2 py-2 rounded-md text-[12px] transition-colors"
                style={
                  activeId === section.id
                    ? {
                        backgroundColor: 'var(--color-accent-light)',
                        color: 'var(--color-accent)',
                        fontWeight: 600,
                      }
                    : { color: 'var(--color-text-secondary)' }
                }
              >
                {section.title}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div ref={contentRef} className="flex-1 overflow-y-auto custom-scrollbar">
        <div className={embedded ? 'px-5 py-5' : 'max-w-3xl mx-auto px-8 py-8'}>
          {!embedded && (
            <div className="mb-8">
              <h2 className="text-lg font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                WeaveEye 使用文档
              </h2>
              <p className="text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
                面向产线操作人员的快速指南。开发部署说明请参阅项目 docs 文档站。
              </p>
            </div>
          )}

          {GUIDE_SECTIONS.map((section) => (
            <section key={section.id} id={`${sectionPrefix}${section.id}`} className="scroll-mt-6 mb-10">
              <h3
                className="text-[15px] font-bold mb-4 pb-2 border-b"
                style={{ color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }}
              >
                {section.title}
              </h3>
              {section.blocks.map((block, i) => (
                <GuideBlockView key={i} block={block} />
              ))}
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
