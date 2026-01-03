/**
 * PriceDisplay Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/utils';
import { PriceDisplay } from '@/components/common';

describe('PriceDisplay', () => {
  it('renders price with default formatting', () => {
    render(<PriceDisplay value={50000} />);
    expect(screen.getByText(/\$50,000/)).toBeInTheDocument();
  });

  it('shows USD currency symbol by default', () => {
    render(<PriceDisplay value={50000} />);
    expect(screen.getByText(/\$/)).toBeInTheDocument();
  });

  it('shows BTC currency symbol when specified', () => {
    render(<PriceDisplay value={0.5} currency="BTC" />);
    expect(screen.getByText(/₿/)).toBeInTheDocument();
  });

  it('shows INR currency symbol when specified', () => {
    render(<PriceDisplay value={50000} currency="INR" />);
    expect(screen.getByText(/₹/)).toBeInTheDocument();
  });

  it('applies green color for positive values when colorCode is true', () => {
    const { container } = render(<PriceDisplay value={100} colorCode />);
    expect(container.firstChild).toHaveClass('text-green-500');
  });

  it('applies red color for negative values when colorCode is true', () => {
    const { container } = render(<PriceDisplay value={-100} colorCode />);
    expect(container.firstChild).toHaveClass('text-red-500');
  });

  it('shows plus sign when showPlusSign is true', () => {
    render(<PriceDisplay value={100} showPlusSign />);
    expect(screen.getByText(/\+\$/)).toBeInTheDocument();
  });

  it('applies size classes correctly', () => {
    const { container } = render(<PriceDisplay value={50000} size="lg" />);
    expect(container.firstChild).toHaveClass('text-lg');
  });

  it('applies xl size with font-semibold', () => {
    const { container } = render(<PriceDisplay value={50000} size="xl" />);
    expect(container.firstChild).toHaveClass('text-2xl');
    expect(container.firstChild).toHaveClass('font-semibold');
  });
});
