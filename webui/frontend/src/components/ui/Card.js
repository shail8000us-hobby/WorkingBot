/**
 * Card Component - Standardized card/panel styles
 * Part of Design System consolidation
 */

import React from 'react';
import clsx from 'clsx';
import { motion } from 'framer-motion';

const cardVariants = {
  default: 'bg-slate-900/60 border-slate-800/60',
  sky: 'bg-slate-900/60 border-sky-500/30',
  emerald: 'bg-slate-900/60 border-emerald-500/30',
  amber: 'bg-slate-900/60 border-amber-500/30',
  rose: 'bg-slate-900/60 border-rose-500/30',
  violet: 'bg-slate-900/60 border-violet-500/30',
};

const Card = React.memo(function Card({
  children,
  variant = 'default',
  padding = 'normal',
  hover = false,
  className = '',
  ...props
}) {
  const paddingClasses = {
    none: '',
    sm: 'p-4',
    normal: 'p-6',
    lg: 'p-8',
  };

  return (
    <motion.div
      className={clsx(
        'rounded-2xl border backdrop-blur shadow-lg ring-1 ring-inset ring-white/5',
        cardVariants[variant],
        paddingClasses[padding],
        hover && 'transition-all hover:shadow-xl hover:-translate-y-0.5',
        className
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
});

export default Card;
