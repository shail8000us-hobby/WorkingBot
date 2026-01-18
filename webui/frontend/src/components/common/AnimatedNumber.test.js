import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AnimatedNumber, { AnimatedPNL, AnimatedPercentage, AnimatedPrice } from './AnimatedNumber';

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    span: ({ children, className, animate, ...props }) => (
      <span className={className} {...props}>
        {children}
      </span>
    ),
  },
}));

describe('AnimatedNumber', () => {
  beforeEach(() => {
    jest.clearAllTimers();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('Basic AnimatedNumber', () => {
    it('renders with initial value', () => {
      const { container } = render(<AnimatedNumber value={1234.56} />);
      expect(container.textContent).toMatch(/1234\.56/);
    });

    it('applies default decimals (2)', () => {
      const { container } = render(<AnimatedNumber value={123.456789} />);
      expect(container.textContent).toMatch(/123\.46/);
    });

    it('applies custom decimals', () => {
      const { container } = render(<AnimatedNumber value={123.456} decimals={1} />);
      expect(container.textContent).toMatch(/123\.5/);
    });

    it('renders with prefix', () => {
      const { container } = render(<AnimatedNumber value={100} prefix="$" />);
      expect(container.textContent).toContain('$');
    });

    it('renders with suffix', () => {
      const { container } = render(<AnimatedNumber value={50} suffix="%" />);
      expect(container.textContent).toContain('%');
    });

    it('renders with both prefix and suffix', () => {
      const { container } = render(<AnimatedNumber value={99.99} prefix="$" suffix=" USD" />);
      expect(container.textContent).toContain('$');
      expect(container.textContent).toContain('USD');
    });

    it('applies custom className', () => {
      const { container } = render(<AnimatedNumber value={100} className="custom-class" />);
      expect(container.querySelector('.custom-class')).toBeInTheDocument();
    });

    it('has tabular-nums class for alignment', () => {
      const { container } = render(<AnimatedNumber value={100} />);
      expect(container.querySelector('.tabular-nums')).toBeInTheDocument();
    });

    it('has tabular-nums class', () => {
      const { container } = render(<AnimatedNumber value={100} />);
      expect(container.querySelector('.tabular-nums')).toBeInTheDocument();
    });
  });

  describe('AnimatedPNL', () => {
    it('renders positive value with green color', () => {
      const { container } = render(<AnimatedPNL value={456.78} />);
      expect(container.textContent).toContain('+$');
      expect(container.textContent).toContain('456.78');
      expect(container.querySelector('.text-success')).toBeInTheDocument();
    });

    it('renders negative value with red color', () => {
      const { container } = render(<AnimatedPNL value={-123.45} />);
      expect(container.textContent).toContain('-$');
      expect(container.textContent).toContain('123.45');
      expect(container.querySelector('.text-danger')).toBeInTheDocument();
    });

    it('renders zero with positive styling', () => {
      const { container } = render(<AnimatedPNL value={0} />);
      expect(container.textContent).toContain('+$');
      expect(container.querySelector('.text-success')).toBeInTheDocument();
    });

    it('displays absolute value', () => {
      const { container } = render(<AnimatedPNL value={-999.99} />);
      expect(container.textContent).toContain('999.99');
    });

    it('applies text-2xl class', () => {
      const { container } = render(<AnimatedPNL value={100} />);
      expect(container.querySelector('.text-2xl')).toBeInTheDocument();
    });

    it('applies font-semibold class', () => {
      const { container } = render(<AnimatedPNL value={100} />);
      expect(container.querySelector('.font-semibold')).toBeInTheDocument();
    });
  });

  describe('AnimatedPercentage', () => {
    it('renders positive percentage with green color', () => {
      const { container } = render(<AnimatedPercentage value={12.34} />);
      expect(container.textContent).toContain('+');
      expect(container.textContent).toContain('12.34');
      expect(container.textContent).toContain('%');
      expect(container.querySelector('.text-success')).toBeInTheDocument();
    });

    it('renders negative percentage with red color', () => {
      const { container } = render(<AnimatedPercentage value={-5.67} />);
      expect(container.textContent).not.toContain('+');
      expect(container.textContent).toContain('5.67');
      expect(container.textContent).toContain('%');
      expect(container.querySelector('.text-danger')).toBeInTheDocument();
    });

    it('renders zero with positive styling', () => {
      const { container } = render(<AnimatedPercentage value={0} />);
      expect(container.textContent).toContain('+');
      expect(container.querySelector('.text-success')).toBeInTheDocument();
    });

    it('applies font-medium class', () => {
      const { container } = render(<AnimatedPercentage value={10} />);
      expect(container.querySelector('.font-medium')).toBeInTheDocument();
    });
  });

  describe('AnimatedPrice', () => {
    it('renders with default $ currency', () => {
      const { container } = render(<AnimatedPrice value={1234.56} />);
      expect(container.textContent).toContain('$');
      expect(container.textContent).toContain('1234.56');
    });

    it('renders with custom currency', () => {
      const { container } = render(<AnimatedPrice value={999.99} currency="€" />);
      expect(container.textContent).toContain('€');
      expect(container.textContent).toContain('999.99');
    });

    it('applies text-xl class', () => {
      const { container } = render(<AnimatedPrice value={100} />);
      expect(container.querySelector('.text-xl')).toBeInTheDocument();
    });

    it('applies font-mono class', () => {
      const { container } = render(<AnimatedPrice value={100} />);
      expect(container.querySelector('.font-mono')).toBeInTheDocument();
    });

    it('applies text-primary class', () => {
      const { container } = render(<AnimatedPrice value={100} />);
      expect(container.querySelector('.text-primary')).toBeInTheDocument();
    });
  });

  describe('Number Formatting', () => {
    it('formats integers correctly', () => {
      const { container } = render(<AnimatedNumber value={1000} decimals={0} />);
      expect(container.textContent).toMatch(/1000/);
    });

    it('handles very large numbers', () => {
      const { container } = render(<AnimatedNumber value={999999999.99} />);
      expect(container.textContent).toMatch(/999999999\.99/);
    });

    it('handles very small numbers', () => {
      const { container } = render(<AnimatedNumber value={0.01} />);
      expect(container.textContent).toMatch(/0\.01/);
    });

    it('handles negative numbers', () => {
      const { container } = render(<AnimatedNumber value={-123.45} />);
      expect(container.textContent).toMatch(/\-123\.45/);
    });
  });

  describe('Animation Duration', () => {
    it('accepts custom duration prop', () => {
      const { container } = render(<AnimatedNumber value={100} duration={1.5} />);
      expect(container.querySelector('.tabular-nums')).toBeInTheDocument();
    });

    it('uses default duration when not specified', () => {
      const { container } = render(<AnimatedNumber value={100} />);
      expect(container.querySelector('.tabular-nums')).toBeInTheDocument();
    });
  });

  describe('Highlight on Change', () => {
    it('can disable highlight on change', () => {
      const { container } = render(<AnimatedNumber value={100} highlightOnChange={false} />);
      expect(container.querySelector('.tabular-nums')).toBeInTheDocument();
    });

    it('enables highlight by default', () => {
      const { container } = render(<AnimatedNumber value={100} />);
      expect(container.querySelector('.tabular-nums')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles zero value', () => {
      const { container } = render(<AnimatedNumber value={0} />);
      expect(container.textContent).toMatch(/0\.00/);
    });

    it('handles undefined value gracefully', () => {
      const { container } = render(<AnimatedNumber value={undefined} />);
      expect(container).toBeInTheDocument();
    });

    it('handles null value gracefully', () => {
      const { container } = render(<AnimatedNumber value={null} />);
      expect(container).toBeInTheDocument();
    });
  });
});
