import { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import clsx from 'clsx';
import React from 'react';

const CollapsibleCard = React.memo(function CollapsibleCard({
  title,
  subtitle,
  defaultOpen = true,
  accent = 'sky',
  actions,
  children,
  id
}) {
  const [open, setOpen] = useState(defaultOpen);

  useEffect(() => {
    setOpen(defaultOpen);
  }, [defaultOpen]);

  const accentClasses = {
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
      className={clsx(
        'relative overflow-hidden rounded-2xl border border-slate-800/60 bg-slate-900/60 shadow-lg ring-1 ring-inset ring-white/5 backdrop-blur',
        accent ? accentClasses[accent] : null
      )}
    >
      <header className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {subtitle && <p className="text-sm text-slate-400">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          <button
            type="button"
            onClick={() => setOpen((prev) => !prev)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-700/60 bg-slate-800/80 text-slate-300 transition hover:border-slate-600 hover:text-white"
            aria-expanded={open}
          >
            {open ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
          </button>
        </div>
      </header>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
          >
            <div className="px-5 pb-6 pt-0">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
});

export default CollapsibleCard;
