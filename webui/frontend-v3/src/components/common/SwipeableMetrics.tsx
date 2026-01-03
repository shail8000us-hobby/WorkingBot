/**
 * Swipeable Metrics
 * 
 * Horizontally scrollable metrics for mobile.
 * Shows key stats in a touch-friendly carousel.
 */

'use client';

import { useRef, useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface MetricItem {
  label: string;
  value: string | number;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
  icon?: React.ReactNode;
}

interface SwipeableMetricsProps {
  metrics: MetricItem[];
  className?: string;
}

export function SwipeableMetrics({ metrics, className }: SwipeableMetricsProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);
  const [activeIndex, setActiveIndex] = useState(0);

  const checkScroll = () => {
    if (!scrollRef.current) return;
    const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
    setCanScrollLeft(scrollLeft > 0);
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10);
    
    // Calculate active index
    const cardWidth = 160; // Approximate card width
    setActiveIndex(Math.round(scrollLeft / cardWidth));
  };

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    container.addEventListener('scroll', checkScroll);
    checkScroll();
    return () => container.removeEventListener('scroll', checkScroll);
  }, []);

  const scroll = (direction: 'left' | 'right') => {
    if (!scrollRef.current) return;
    const scrollAmount = 160;
    scrollRef.current.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth',
    });
  };

  return (
    <div className={cn('relative', className)}>
      {/* Scroll buttons - hidden on touch devices */}
      {canScrollLeft && (
        <button
          onClick={() => scroll('left')}
          className="hidden sm:flex absolute left-0 top-1/2 -translate-y-1/2 z-10 h-8 w-8 items-center justify-center rounded-full bg-background/80 shadow-md border"
          aria-label="Scroll left"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      )}
      {canScrollRight && (
        <button
          onClick={() => scroll('right')}
          className="hidden sm:flex absolute right-0 top-1/2 -translate-y-1/2 z-10 h-8 w-8 items-center justify-center rounded-full bg-background/80 shadow-md border"
          aria-label="Scroll right"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      )}

      {/* Metrics container */}
      <div
        ref={scrollRef}
        className={cn(
          'flex gap-3 overflow-x-auto scrollbar-hide',
          'snap-x snap-mandatory',
          'pb-2 px-1',
          '-mx-1'
        )}
        style={{
          WebkitOverflowScrolling: 'touch',
        }}
      >
        {metrics.map((metric, index) => (
          <Card
            key={index}
            className={cn(
              'flex-shrink-0 snap-start',
              'min-w-[140px] w-[140px] sm:min-w-[160px] sm:w-[160px]'
            )}
          >
            <CardContent className="p-3">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground line-clamp-1">
                    {metric.label}
                  </p>
                  <p className="text-lg font-bold font-mono">
                    {typeof metric.value === 'number'
                      ? metric.value.toLocaleString()
                      : metric.value}
                  </p>
                  {metric.change && (
                    <p
                      className={cn(
                        'text-xs font-medium',
                        metric.changeType === 'positive' && 'text-green-500',
                        metric.changeType === 'negative' && 'text-red-500',
                        metric.changeType === 'neutral' && 'text-muted-foreground'
                      )}
                    >
                      {metric.change}
                    </p>
                  )}
                </div>
                {metric.icon && (
                  <div className="text-muted-foreground">
                    {metric.icon}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Dot indicators */}
      <div className="flex justify-center gap-1.5 mt-2 sm:hidden">
        {metrics.map((_, index) => (
          <div
            key={index}
            className={cn(
              'h-1.5 rounded-full transition-all',
              index === activeIndex
                ? 'w-4 bg-primary'
                : 'w-1.5 bg-muted-foreground/30'
            )}
          />
        ))}
      </div>
    </div>
  );
}

export default SwipeableMetrics;
