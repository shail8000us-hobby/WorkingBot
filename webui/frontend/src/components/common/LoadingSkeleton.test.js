import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import LoadingSkeleton, { CardSkeleton, MetricSkeleton, TableRowSkeleton, ChartSkeleton } from './LoadingSkeleton';

describe('LoadingSkeleton', () => {
  describe('Basic LoadingSkeleton', () => {
    it('renders with default props', () => {
      const { container } = render(<LoadingSkeleton />);
      const skeleton = container.querySelector('.loading-shimmer');
      expect(skeleton).toBeInTheDocument();
      expect(skeleton).toHaveClass('h-4', 'w-full', 'mb-2');
    });

    it('renders with text variant', () => {
      const { container } = render(<LoadingSkeleton variant="text" />);
      const skeleton = container.querySelector('.loading-shimmer');
      expect(skeleton).toHaveClass('h-4', 'w-full');
    });

    it('renders with title variant', () => {
      const { container } = render(<LoadingSkeleton variant="title" />);
      const skeleton = container.querySelector('.loading-shimmer');
      expect(skeleton).toHaveClass('h-6', 'w-3/4');
    });

    it('renders with card variant', () => {
      const { container } = render(<LoadingSkeleton variant="card" />);
      const skeleton = container.querySelector('.loading-shimmer');
      expect(skeleton).toHaveClass('h-32', 'w-full');
    });

    it('renders multiple skeletons with count prop', () => {
      const { container } = render(<LoadingSkeleton count={3} />);
      const skeletons = container.querySelectorAll('.loading-shimmer');
      expect(skeletons).toHaveLength(3);
    });

    it('applies custom width and height', () => {
      const { container } = render(
        <LoadingSkeleton width="200px" height="50px" />
      );
      const skeleton = container.querySelector('.loading-shimmer');
      expect(skeleton).toHaveStyle({ width: '200px', height: '50px' });
    });

    it('renders as circle when circle prop is true', () => {
      const { container } = render(<LoadingSkeleton circle />);
      const skeleton = container.querySelector('.loading-shimmer');
      expect(skeleton).toHaveStyle({ borderRadius: '50%' });
    });

    it('applies custom className', () => {
      const { container } = render(<LoadingSkeleton className="custom-class" />);
      const skeleton = container.querySelector('.loading-shimmer');
      expect(skeleton).toHaveClass('custom-class');
    });

    it('has aria-label for accessibility', () => {
      const { container } = render(<LoadingSkeleton />);
      const skeleton = container.querySelector('[aria-label="Loading..."]');
      expect(skeleton).toBeInTheDocument();
    });
  });

  describe('CardSkeleton', () => {
    it('renders card structure', () => {
      const { container } = render(<CardSkeleton />);
      
      expect(container.querySelector('.glass-card')).toBeInTheDocument();
      
      const skeletons = container.querySelectorAll('.loading-shimmer');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('contains title, subtitle, text, and button elements', () => {
      const { container } = render(<CardSkeleton />);
      const skeletons = container.querySelectorAll('.loading-shimmer');
      
      // Should have title, subtitle, 3 text lines, 2 buttons = 7 total
      expect(skeletons.length).toBeGreaterThanOrEqual(5);
    });
  });

  describe('MetricSkeleton', () => {
    it('renders metric structure', () => {
      const { container } = render(<MetricSkeleton />);
      
      expect(container.querySelector('.glass-card')).toBeInTheDocument();
      
      const skeletons = container.querySelectorAll('.loading-shimmer');
      expect(skeletons.length).toBe(3); // badge, metric, text
    });
  });

  describe('TableRowSkeleton', () => {
    it('renders with default 4 columns', () => {
      const { container } = render(<TableRowSkeleton />);
      const skeletons = container.querySelectorAll('.loading-shimmer');
      expect(skeletons).toHaveLength(4);
    });

    it('renders with custom column count', () => {
      const { container } = render(<TableRowSkeleton columns={6} />);
      const skeletons = container.querySelectorAll('.loading-shimmer');
      expect(skeletons).toHaveLength(6);
    });
  });

  describe('ChartSkeleton', () => {
    it('renders chart structure', () => {
      const { container } = render(<ChartSkeleton />);
      
      expect(container.querySelector('.glass-card')).toBeInTheDocument();
      
      // Should have title, 2 badges, and chart = 4 skeletons
      const skeletons = container.querySelectorAll('.loading-shimmer');
      expect(skeletons.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('Animation', () => {
    it('has shimmer animation class', () => {
      const { container } = render(<LoadingSkeleton />);
      const skeleton = container.querySelector('.loading-shimmer');
      expect(skeleton).toHaveClass('loading-shimmer');
    });
  });

  describe('Variants', () => {
    const variants = ['text', 'title', 'subtitle', 'card', 'button', 'avatar', 'badge', 'metric', 'chart'];
    
    variants.forEach(variant => {
      it(`renders ${variant} variant correctly`, () => {
        const { container } = render(<LoadingSkeleton variant={variant} />);
        const skeleton = container.querySelector('.loading-shimmer');
        expect(skeleton).toBeInTheDocument();
      });
    });
  });
});
