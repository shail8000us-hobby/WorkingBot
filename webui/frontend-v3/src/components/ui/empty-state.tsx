/**
 * Empty State Illustrations Component
 * 
 * Phase 3: Custom SVG illustrations for empty states
 */

'use client';

import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  variant?: 'default' | 'minimal' | 'illustrated';
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  variant = 'default',
  className,
}: EmptyStateProps) {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center py-12 px-6 text-center',
      className
    )}>
      {/* Animated Icon Container */}
      {Icon && variant !== 'minimal' && (
        <div className="relative mb-6">
          {/* Glow Effect */}
          <div className="absolute inset-0 bg-primary/20 rounded-full blur-2xl animate-pulse" />
          
          {/* Icon with Animation */}
          <div className="relative bg-muted rounded-full p-6 float-animation">
            <Icon className="h-12 w-12 text-muted-foreground" />
          </div>
        </div>
      )}
      
      {/* Minimal Icon */}
      {Icon && variant === 'minimal' && (
        <Icon className="h-12 w-12 text-muted-foreground mb-4 opacity-50" />
      )}
      
      {/* Title */}
      <h3 className={cn(
        'font-semibold tracking-tight mb-2',
        variant === 'illustrated' ? 'text-2xl' : 'text-lg'
      )}>
        {title}
      </h3>
      
      {/* Description */}
      {description && (
        <p className="text-sm text-muted-foreground max-w-sm mb-6">
          {description}
        </p>
      )}
      
      {/* Action */}
      {action && (
        <div className="mt-2">
          {action}
        </div>
      )}
    </div>
  );
}

// SVG Illustration Components
export function NoDataIllustration() {
  return (
    <svg
      className="w-48 h-48 float-animation"
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Empty Chart */}
      <rect
        x="20"
        y="50"
        width="160"
        height="120"
        rx="8"
        className="fill-muted stroke-border"
        strokeWidth="2"
      />
      
      {/* Grid Lines */}
      <line x1="20" y1="90" x2="180" y2="90" className="stroke-border" strokeWidth="1" opacity="0.5" />
      <line x1="20" y1="130" x2="180" y2="130" className="stroke-border" strokeWidth="1" opacity="0.5" />
      
      {/* Flat Line */}
      <path
        d="M 40 110 L 80 110 L 120 110 L 160 110"
        className="stroke-muted-foreground"
        strokeWidth="2"
        strokeLinecap="round"
        strokeDasharray="4 4"
        opacity="0.3"
      />
      
      {/* Magnifying Glass */}
      <circle cx="150" cy="80" r="15" className="fill-background stroke-primary" strokeWidth="3" />
      <line x1="162" y1="92" x2="175" y2="105" className="stroke-primary" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function NoPositionsIllustration() {
  return (
    <svg
      className="w-48 h-48 scale-pulse"
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Wallet */}
      <rect
        x="40"
        y="60"
        width="120"
        height="80"
        rx="12"
        className="fill-muted stroke-border"
        strokeWidth="2"
      />
      
      {/* Wallet Flap */}
      <path
        d="M 40 80 Q 100 70 160 80"
        className="stroke-border"
        strokeWidth="2"
        fill="none"
      />
      
      {/* Empty Symbol */}
      <circle cx="100" cy="110" r="20" className="stroke-muted-foreground" strokeWidth="2" strokeDasharray="4 4" opacity="0.5" />
      <line x1="85" y1="110" x2="115" y2="110" className="stroke-muted-foreground" strokeWidth="2" opacity="0.5" />
    </svg>
  );
}

export function NoTradesIllustration() {
  return (
    <svg
      className="w-48 h-48 float-animation"
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Trading Graph */}
      <rect
        x="30"
        y="40"
        width="140"
        height="120"
        rx="8"
        className="fill-muted/50 stroke-border"
        strokeWidth="2"
      />
      
      {/* Candlesticks (Faded) */}
      <rect x="50" y="80" width="8" height="40" className="fill-muted-foreground" opacity="0.2" />
      <rect x="70" y="70" width="8" height="50" className="fill-muted-foreground" opacity="0.2" />
      <rect x="90" y="90" width="8" height="30" className="fill-muted-foreground" opacity="0.2" />
      <rect x="110" y="75" width="8" height="45" className="fill-muted-foreground" opacity="0.2" />
      <rect x="130" y="85" width="8" height="35" className="fill-muted-foreground" opacity="0.2" />
      
      {/* Play Button */}
      <circle cx="100" cy="100" r="25" className="fill-primary/20 stroke-primary" strokeWidth="2" />
      <path d="M 95 90 L 95 110 L 110 100 Z" className="fill-primary" />
    </svg>
  );
}

export function ErrorIllustration() {
  return (
    <svg
      className="w-48 h-48 shake-error"
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Warning Triangle */}
      <path
        d="M 100 40 L 160 150 L 40 150 Z"
        className="fill-destructive/10 stroke-destructive"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      
      {/* Exclamation Mark */}
      <line x1="100" y1="80" x2="100" y2="110" className="stroke-destructive" strokeWidth="4" strokeLinecap="round" />
      <circle cx="100" cy="130" r="3" className="fill-destructive" />
    </svg>
  );
}

export function SuccessIllustration() {
  return (
    <svg
      className="w-48 h-48"
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Success Circle */}
      <circle
        cx="100"
        cy="100"
        r="60"
        className="fill-green-500/10 stroke-green-500"
        strokeWidth="3"
      />
      
      {/* Checkmark */}
      <path
        d="M 70 100 L 90 120 L 130 80"
        className="stroke-green-500 checkmark-animate"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default EmptyState;
