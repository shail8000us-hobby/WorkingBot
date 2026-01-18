import React from 'react';
import { motion } from 'framer-motion';
import clsx from 'clsx';

/**
 * AnimatedNumber Component
 * Smooth number transitions with formatting
 * 
 * Created: January 18, 2026 (Migrated to TypeScript)
 * Safe: Pure UI component, no functional changes
 */

interface AnimatedNumberProps {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  duration?: number;
  highlightOnChange?: boolean;
}

const AnimatedNumber: React.FC<AnimatedNumberProps> = ({
  value,
  decimals = 2,
  prefix = '',
  suffix = '',
  className,
  duration = 0.5,
  highlightOnChange = false
}) => {
  const formattedValue = value?.toFixed(decimals) ?? '0.00';
  
  return (
    <motion.span
      key={value}
      initial={{ opacity: 1 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0 }}
      className={clsx('tabular-nums', className)}
    >
      {prefix}{formattedValue}{suffix}
    </motion.span>
  );
};

// Specialized number displays
interface AnimatedPNLProps {
  value: number;
  className?: string;
}

export const AnimatedPNL: React.FC<AnimatedPNLProps> = ({ value, className }) => {
  const isPositive = value >= 0;
  const sign = isPositive ? '+' : '-';
  const colorClass = isPositive ? 'text-success' : 'text-danger';
  
  return (
    <AnimatedNumber
      value={Math.abs(value)}
      prefix={`${sign}$`}
      className={clsx('text-2xl font-semibold', colorClass, className)}
    />
  );
};

interface AnimatedPercentageProps {
  value: number;
  className?: string;
}

export const AnimatedPercentage: React.FC<AnimatedPercentageProps> = ({ value, className }) => {
  const isPositive = value >= 0;
  const sign = isPositive ? '+' : '';
  const colorClass = isPositive ? 'text-success' : 'text-danger';
  
  return (
    <AnimatedNumber
      value={value}
      prefix={sign}
      suffix="%"
      className={clsx('font-medium', colorClass, className)}
    />
  );
};

interface AnimatedPriceProps {
  value: number;
  currency?: string;
  className?: string;
}

export const AnimatedPrice: React.FC<AnimatedPriceProps> = ({ 
  value, 
  currency = '$', 
  className 
}) => {
  return (
    <AnimatedNumber
      value={value}
      prefix={currency}
      className={clsx('text-xl font-mono text-primary', className)}
    />
  );
};

export default AnimatedNumber;
