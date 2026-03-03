import React, { useState, ReactNode } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';
import clsx from 'clsx';

/**
 * CollapsibleCard Component
 * Expandable card with animations
 *
 * Created: January 18, 2026 (Migrated to TypeScript)
 * Safe: Pure UI component, no functional changes
 */

type AccentColor = 'sky' | 'emerald' | 'amber' | 'rose' | 'violet';

interface CollapsibleCardProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  accent?: AccentColor;
  actions?: ReactNode;
  className?: string;
  id?: string;
}

const CollapsibleCard: React.FC<CollapsibleCardProps> = ({
  title,
  subtitle,
  children,
  defaultOpen = true,
  accent = 'sky',
  actions,
  className,
  id,
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const accentClasses: Record<AccentColor, string> = {
    sky: 'border-sky-500/30 bg-sky-500/5',
    emerald: 'border-emerald-500/30 bg-emerald-500/5',
    amber: 'border-amber-500/30 bg-amber-500/5',
    rose: 'border-rose-500/30 bg-rose-500/5',
    violet: 'border-violet-500/30 bg-violet-500/5',
  };

  return (
    <section
      id={id}
      className={clsx(
        'holographic-card relative overflow-visible animate-fade-slide-up',
        accent && accentClasses[accent],
        className
      )}
    >
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 px-2 py-2 border-b border-slate-700/30">
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {subtitle && <p className="text-sm text-slate-400 mt-1">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-2">
          {actions}
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-slate-800/60 text-slate-300 hover:bg-slate-700/60 hover:text-slate-100 transition"
            aria-expanded={isOpen}
          >
            {isOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>
      </header>

      <div
        className="grid transition-[grid-template-rows] duration-200 ease-in-out"
        style={{ gridTemplateRows: isOpen ? '1fr' : '0fr' }}
      >
        <div className="overflow-hidden">
          <div className="px-1 pb-2 pt-0">{children}</div>
        </div>
      </div>
    </section>
  );
};

export default React.memo(CollapsibleCard);
