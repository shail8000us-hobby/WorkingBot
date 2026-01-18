import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

/**
 * AnimatedNumber Component
 * Smooth count-up animation for numbers
 * 
 * Created: January 18, 2026
 * Safe: Pure UI component, no functional changes
 */

const AnimatedNumber = ({
  value,
  duration = 0.8,
  decimals = 2,
  prefix = '',
  suffix = '',
  className = '',
  highlightOnChange = true
}) => {
  const [displayValue, setDisplayValue] = useState(value);
  const [isChanged, setIsChanged] = useState(false);
  
  useEffect(() => {
    if (value === displayValue) return;
    
    // Trigger highlight effect
    if (highlightOnChange) {
      setIsChanged(true);
      setTimeout(() => setIsChanged(false), 300);
    }
    
    const startValue = displayValue;
    const endValue = value;
    const startTime = performance.now();
    const durationMs = duration * 1000;
    
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      
      // Easing function (ease-out)
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = startValue + (endValue - startValue) * eased;
      
      setDisplayValue(current);
      
      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };
    
    requestAnimationFrame(animate);
  }, [value, displayValue, duration, highlightOnChange]);
  
  const formattedValue = typeof displayValue === 'number'
    ? displayValue.toFixed(decimals)
    : displayValue;
  
  return (
    <motion.span
      className={`number-highlight tabular-nums ${className} ${isChanged ? 'changed' : ''}`}
      animate={isChanged ? { scale: [1, 1.05, 1] } : {}}
      transition={{ duration: 0.3 }}
    >
      {prefix}{formattedValue}{suffix}
    </motion.span>
  );
};

// Preset number components
export const AnimatedPNL = ({ value }) => {
  const isPositive = value >= 0;
  const color = isPositive ? 'text-success' : 'text-danger';
  const prefix = isPositive ? '+$' : '-$';
  
  return (
    <AnimatedNumber
      value={Math.abs(value)}
      decimals={2}
      prefix={prefix}
      className={`text-2xl font-semibold ${color}`}
    />
  );
};

export const AnimatedPercentage = ({ value }) => {
  const isPositive = value >= 0;
  const color = isPositive ? 'text-success' : 'text-danger';
  const prefix = isPositive ? '+' : '';
  
  return (
    <AnimatedNumber
      value={value}
      decimals={2}
      prefix={prefix}
      suffix="%"
      className={`font-medium ${color}`}
    />
  );
};

export const AnimatedPrice = ({ value, currency = '$' }) => {
  return (
    <AnimatedNumber
      value={value}
      decimals={2}
      prefix={currency}
      className="text-xl font-mono text-primary"
    />
  );
};

export default AnimatedNumber;
