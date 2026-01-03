/**
 * StatusBadge Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/utils';
import { StatusBadge } from '@/components/common';

describe('StatusBadge', () => {
  it('renders connected status correctly', () => {
    render(<StatusBadge status="connected" />);
    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  it('renders disconnected status correctly', () => {
    render(<StatusBadge status="disconnected" />);
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });

  it('renders error status correctly', () => {
    render(<StatusBadge status="error" />);
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('renders running status correctly', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByText('Running')).toBeInTheDocument();
  });

  it('renders stopped status correctly', () => {
    render(<StatusBadge status="stopped" />);
    expect(screen.getByText('Stopped')).toBeInTheDocument();
  });

  it('renders pending status correctly', () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('renders healthy status correctly', () => {
    render(<StatusBadge status="healthy" />);
    expect(screen.getByText('Healthy')).toBeInTheDocument();
  });

  it('applies correct size class for sm size', () => {
    const { container } = render(<StatusBadge status="connected" size="sm" />);
    expect(container.firstChild).toHaveClass('text-xs');
  });

  it('applies correct size class for lg size', () => {
    const { container } = render(<StatusBadge status="connected" size="lg" />);
    expect(container.firstChild).toHaveClass('text-base');
  });

  it('applies custom className', () => {
    const { container } = render(<StatusBadge status="connected" className="custom-class" />);
    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('uses custom label when provided', () => {
    render(<StatusBadge status="connected" label="Custom Label" />);
    expect(screen.getByText('Custom Label')).toBeInTheDocument();
  });

  it('shows pulse animation for running status by default', () => {
    const { container } = render(<StatusBadge status="running" />);
    expect(container.querySelector('.animate-ping')).toBeInTheDocument();
  });

  it('shows pulse animation when pulse prop is true', () => {
    const { container } = render(<StatusBadge status="stopped" pulse />);
    expect(container.querySelector('.animate-ping')).toBeInTheDocument();
  });

  it('hides pulse animation when pulse prop is false', () => {
    const { container } = render(<StatusBadge status="running" pulse={false} />);
    expect(container.querySelector('.animate-ping')).not.toBeInTheDocument();
  });
});
