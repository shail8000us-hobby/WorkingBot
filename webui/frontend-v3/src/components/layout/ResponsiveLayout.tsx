/**
 * Responsive Grid Layout
 * 
 * Responsive grid that adapts from single column on mobile
 * to multi-column on larger screens.
 */

'use client';

import { cn } from '@/lib/utils';

interface ResponsiveGridProps {
  children: React.ReactNode;
  className?: string;
  /** Columns on mobile (default: 1) */
  mobile?: 1 | 2;
  /** Columns on tablet (default: 2) */
  tablet?: 1 | 2 | 3 | 4;
  /** Columns on desktop (default: 3) */
  desktop?: 1 | 2 | 3 | 4 | 5 | 6;
  /** Gap between items (default: 4) */
  gap?: 2 | 3 | 4 | 5 | 6;
}

export function ResponsiveGrid({
  children,
  className,
  mobile = 1,
  tablet = 2,
  desktop = 3,
  gap = 4,
}: ResponsiveGridProps) {
  const colClasses = {
    mobile: {
      1: 'grid-cols-1',
      2: 'grid-cols-2',
    },
    tablet: {
      1: 'sm:grid-cols-1',
      2: 'sm:grid-cols-2',
      3: 'sm:grid-cols-3',
      4: 'sm:grid-cols-4',
    },
    desktop: {
      1: 'lg:grid-cols-1',
      2: 'lg:grid-cols-2',
      3: 'lg:grid-cols-3',
      4: 'lg:grid-cols-4',
      5: 'lg:grid-cols-5',
      6: 'lg:grid-cols-6',
    },
  };

  const gapClasses = {
    2: 'gap-2',
    3: 'gap-3',
    4: 'gap-4',
    5: 'gap-5',
    6: 'gap-6',
  };

  return (
    <div
      className={cn(
        'grid',
        colClasses.mobile[mobile],
        colClasses.tablet[tablet],
        colClasses.desktop[desktop],
        gapClasses[gap],
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * Mobile-First Stack
 * Stacks items vertically on mobile, horizontally on larger screens
 */
interface ResponsiveStackProps {
  children: React.ReactNode;
  className?: string;
  /** Breakpoint to switch to horizontal (default: md) */
  breakpoint?: 'sm' | 'md' | 'lg';
  /** Gap between items (default: 4) */
  gap?: 2 | 3 | 4 | 5 | 6;
  /** Alignment when horizontal */
  align?: 'start' | 'center' | 'end' | 'stretch';
  /** Justify content when horizontal */
  justify?: 'start' | 'center' | 'end' | 'between' | 'around';
}

export function ResponsiveStack({
  children,
  className,
  breakpoint = 'md',
  gap = 4,
  align = 'center',
  justify = 'start',
}: ResponsiveStackProps) {
  const breakpointClasses = {
    sm: 'sm:flex-row',
    md: 'md:flex-row',
    lg: 'lg:flex-row',
  };

  const gapClasses = {
    2: 'gap-2',
    3: 'gap-3',
    4: 'gap-4',
    5: 'gap-5',
    6: 'gap-6',
  };

  const alignClasses = {
    start: 'items-start',
    center: 'items-center',
    end: 'items-end',
    stretch: 'items-stretch',
  };

  const justifyClasses = {
    start: 'justify-start',
    center: 'justify-center',
    end: 'justify-end',
    between: 'justify-between',
    around: 'justify-around',
  };

  return (
    <div
      className={cn(
        'flex flex-col',
        breakpointClasses[breakpoint],
        gapClasses[gap],
        alignClasses[align],
        justifyClasses[justify],
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * Hide on Mobile
 * Utility component to hide content on small screens
 */
interface HideOnMobileProps {
  children: React.ReactNode;
  /** Breakpoint above which content is visible (default: md) */
  showAbove?: 'sm' | 'md' | 'lg' | 'xl';
}

export function HideOnMobile({ children, showAbove = 'md' }: HideOnMobileProps) {
  const classes = {
    sm: 'hidden sm:block',
    md: 'hidden md:block',
    lg: 'hidden lg:block',
    xl: 'hidden xl:block',
  };

  return <div className={classes[showAbove]}>{children}</div>;
}

/**
 * Show on Mobile Only
 * Utility component to show content only on small screens
 */
interface ShowOnMobileOnlyProps {
  children: React.ReactNode;
  /** Breakpoint below which content is visible (default: md) */
  hideAbove?: 'sm' | 'md' | 'lg' | 'xl';
}

export function ShowOnMobileOnly({ children, hideAbove = 'md' }: ShowOnMobileOnlyProps) {
  const classes = {
    sm: 'sm:hidden',
    md: 'md:hidden',
    lg: 'lg:hidden',
    xl: 'xl:hidden',
  };

  return <div className={classes[hideAbove]}>{children}</div>;
}

export default ResponsiveGrid;
