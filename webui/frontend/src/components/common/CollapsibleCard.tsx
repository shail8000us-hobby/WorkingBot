import React, { useState, ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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
  id
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  
  const accentClasses: Record<AccentColor, string> = {
    sky: 'border-sky-500/30 bg-sky-500/5',
    emerald: 'border-emerald-500/30 bg-emerald-500/5',
    amber: 'border-amber-500/30 bg-amber-500/5',
    rose: 'border-rose-500/30 bg-rose-500/5',
    violet: 'border-violet-500/30 bg-violet-500/5'
  };
  
  return (
    <motion.section
      id={id}
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={clsx(
        'holographic-card relative overflow-visible',
        accent && accentClasses[accent],
        className
      )}
    >
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 px-5 py-4 border-b border-slate-700/30">
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {subtitle && (
            <p className="text-sm text-slate-400 mt-1">{subtitle}</p>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {actions}
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-slate-800/60 text-slate-300 hover:bg-slate-700/60 hover:text-slate-100 transition"
            aria-expanded={isOpen}
          >
            {isOpen ? (
              <ChevronUp className="w-5 h-5" />
            ) : (
              <ChevronDown className="w-5 h-5" />
            )}
          </button>
        </div>
      </header>
      
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-6 pt-0">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
};

export default CollapsibleCard;
