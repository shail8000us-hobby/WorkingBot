/**
 * Performance Monitor Component
 * 
 * Phase 3: Real-time performance tracking with animations
 */

'use client';

import { useEffect, useState } from 'react';
import { Activity, Zap, Clock, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from './card';

interface PerformanceMetrics {
  fps: number;
  loadTime: number;
  apiLatency: number;
  memoryUsage: number;
}

export function PerformanceMonitor({ className }: { className?: string }) {
  const [metrics, setMetrics] = useState<PerformanceMetrics>({
    fps: 60,
    loadTime: 0,
    apiLatency: 0,
    memoryUsage: 0,
  });

  const [show, setShow] = useState(false);

  useEffect(() => {
    // Only show in development
    if (process.env.NODE_ENV === 'development') {
      setShow(true);
    }

    // FPS Counter
    let frameCount = 0;
    let lastTime = performance.now();

    const measureFPS = () => {
      frameCount++;
      const currentTime = performance.now();
      
      if (currentTime >= lastTime + 1000) {
        setMetrics((prev) => ({ ...prev, fps: frameCount }));
        frameCount = 0;
        lastTime = currentTime;
      }

      requestAnimationFrame(measureFPS);
    };

    const rafId = requestAnimationFrame(measureFPS);

    // Load time
    if (performance.timing) {
      const loadTime = performance.timing.loadEventEnd - performance.timing.navigationStart;
      setMetrics((prev) => ({ ...prev, loadTime: loadTime / 1000 }));
    }

    // Memory usage (if available)
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      const usedMemory = memory.usedJSHeapSize / 1048576; // Convert to MB
      setMetrics((prev) => ({ ...prev, memoryUsage: usedMemory }));
    }

    return () => cancelAnimationFrame(rafId);
  }, []);

  if (!show) return null;

  const getPerformanceColor = (value: number, thresholds: { good: number; warning: number }) => {
    if (value >= thresholds.good) return 'success';
    if (value >= thresholds.warning) return 'warning';
    return 'error';
  };

  const fpsColor = getPerformanceColor(metrics.fps, { good: 55, warning: 30 });

  return (
    <Card className={cn('glass-strong border-primary/20', className)}>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <Activity className="h-4 w-4" />
          Performance Monitor
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <PerformanceBar
          icon={Zap}
          label="FPS"
          value={metrics.fps}
          max={60}
          suffix=" fps"
          variant={fpsColor}
        />
        <PerformanceBar
          icon={Clock}
          label="Load Time"
          value={metrics.loadTime}
          max={5}
          suffix="s"
          variant={metrics.loadTime < 2 ? 'success' : 'warning'}
        />
        {metrics.memoryUsage > 0 && (
          <PerformanceBar
            icon={TrendingUp}
            label="Memory"
            value={metrics.memoryUsage}
            max={500}
            suffix=" MB"
            variant={metrics.memoryUsage < 200 ? 'success' : 'warning'}
          />
        )}
      </CardContent>
    </Card>
  );
}

interface PerformanceBarProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  max: number;
  suffix: string;
  variant: 'success' | 'warning' | 'error';
}

function PerformanceBar({ icon: Icon, label, value, max, suffix, variant }: PerformanceBarProps) {
  const percentage = Math.min((value / max) * 100, 100);

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5">
          <Icon className="h-3 w-3" />
          <span className="text-muted-foreground">{label}</span>
        </div>
        <span className="font-mono font-semibold">
          {value.toFixed(value < 10 ? 2 : 0)}{suffix}
        </span>
      </div>
      <div className="performance-graph h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className={cn('performance-bar h-full', variant)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export default PerformanceMonitor;
