/**
 * EmptyStates Component Tests
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@/test/utils';
import { 
  EmptyState, 
  EmptyOrders, 
  EmptyPositions, 
  EmptyGrid,
  EmptyFailed 
} from '@/components/common';

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(
      <EmptyState 
        title="No Data" 
        description="There is no data to display" 
      />
    );
    
    expect(screen.getByText('No Data')).toBeInTheDocument();
    expect(screen.getByText('There is no data to display')).toBeInTheDocument();
  });

  it('renders action button when provided', () => {
    const handleClick = vi.fn();
    render(
      <EmptyState 
        title="No Data" 
        action={{ label: 'Refresh', onClick: handleClick }}
      />
    );
    
    const button = screen.getByRole('button', { name: 'Refresh' });
    expect(button).toBeInTheDocument();
    
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders secondary action button when provided', () => {
    const handlePrimary = vi.fn();
    const handleSecondary = vi.fn();
    
    render(
      <EmptyState 
        title="No Data" 
        action={{ label: 'Primary', onClick: handlePrimary }}
        secondaryAction={{ label: 'Secondary', onClick: handleSecondary }}
      />
    );
    
    expect(screen.getByRole('button', { name: 'Primary' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Secondary' })).toBeInTheDocument();
  });

  it('applies size classes correctly', () => {
    const { container } = render(
      <EmptyState title="No Data" size="lg" />
    );
    
    expect(container.firstChild).toHaveClass('py-20');
  });
});

describe('EmptyOrders', () => {
  it('renders with correct title', () => {
    render(<EmptyOrders />);
    expect(screen.getByText('No Orders')).toBeInTheDocument();
  });

  it('renders refresh button when onRefresh provided', () => {
    const handleRefresh = vi.fn();
    render(<EmptyOrders onRefresh={handleRefresh} />);
    
    const button = screen.getByRole('button', { name: 'Refresh' });
    fireEvent.click(button);
    expect(handleRefresh).toHaveBeenCalled();
  });
});

describe('EmptyPositions', () => {
  it('renders with correct title', () => {
    render(<EmptyPositions />);
    expect(screen.getByText('No Open Positions')).toBeInTheDocument();
  });
});

describe('EmptyGrid', () => {
  it('renders with correct title', () => {
    render(<EmptyGrid />);
    expect(screen.getByText('No Grid Levels')).toBeInTheDocument();
  });

  it('renders configure button when onConfigure provided', () => {
    const handleConfigure = vi.fn();
    render(<EmptyGrid onConfigure={handleConfigure} />);
    
    const button = screen.getByRole('button', { name: 'Configure Grid' });
    fireEvent.click(button);
    expect(handleConfigure).toHaveBeenCalled();
  });
});

describe('EmptyFailed', () => {
  it('renders with correct title', () => {
    render(<EmptyFailed />);
    expect(screen.getByText('Failed to Load')).toBeInTheDocument();
  });

  it('displays custom error message', () => {
    render(<EmptyFailed message="Custom error message" />);
    expect(screen.getByText('Custom error message')).toBeInTheDocument();
  });

  it('renders retry button when onRetry provided', () => {
    const handleRetry = vi.fn();
    render(<EmptyFailed onRetry={handleRetry} />);
    
    const button = screen.getByRole('button', { name: 'Try Again' });
    fireEvent.click(button);
    expect(handleRetry).toHaveBeenCalled();
  });
});
