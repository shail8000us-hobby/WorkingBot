/**
 * Animated Counter Component
 * 
 * Phase 3: Number animations with easing
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

interface AnimatedCounterProps {
  value: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  animate?: boolean;
}

export function AnimatedCounter({
  value,
  duration = 1000,
  decimals = 0,
  prefix = '',
  suffix = '',
  className,
  animate = true,
}: AnimatedCounterProps) {
  const [count, setCount] = useState(animate ? 0 : value);
  const countRef = useRef(value);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (!animate) {
      setCount(value);
      return;
    }

    countRef.current = value;
    startTimeRef.current = null;

    const animateCount = (timestamp: number) => {
      if (!startTimeRef.current) {
        startTimeRef.current = timestamp;
      }

      const progress = Math.min((timestamp - startTimeRef.current) / duration, 1);
      
      // Easing function (ease-out-cubic)
      const easeOut = 1 - Math.pow(1 - progress, 3);
      
      setCount(easeOut * countRef.current);

      if (progress < 1) {
        requestAnimationFrame(animateCount);
      }
    };

    requestAnimationFrame(animateCount);
  }, [value, duration, animate]);

  const formattedValue = count.toFixed(decimals);

  return (
    <span className={cn('metric-counter tabular-nums', className)}>
      {prefix}{formattedValue}{suffix}
    </span>
  );
}

interface FlippingCounterProps {
  value: number;
  className?: string;
}

export function FlippingCounter({ value, className }: FlippingCounterProps) {
  const [currentValue, setCurrentValue] = useState(value);
  const [isFlipping, setIsFlipping] = useState(false);

  useEffect(() => {
    if (value !== currentValue) {
      setIsFlipping(true);
      setTimeout(() => {
        setCurrentValue(value);
        setIsFlipping(false);
      }, 300);
    }
  }, [value, currentValue]);

  return (
    <span className={cn('inline-block tabular-nums', isFlipping && 'number-flip', className)}>
      {currentValue}
    </span>
  );
}

export default AnimatedCounter;
