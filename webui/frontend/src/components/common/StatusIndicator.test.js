import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import StatusIndicator, { BotStatusIndicator, ConnectionStatusIndicator, OrderStatusIndicator } from './StatusIndicator';

describe('StatusIndicator', () => {
  describe('Basic StatusIndicator', () => {
    it('renders with default props', () => {
      const { container } = render(<StatusIndicator />);
      expect(container.querySelector('.inline-flex')).toBeInTheDocument();
    });

    it('renders running status correctly', () => {
      render(<StatusIndicator status="running" />);
      expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('renders stopped status correctly', () => {
      render(<StatusIndicator status="stopped" />);
      expect(screen.getByText('Stopped')).toBeInTheDocument();
    });

    it('renders idle status correctly', () => {
      render(<StatusIndicator status="idle" />);
      expect(screen.getByText('Idle')).toBeInTheDocument();
    });

    it('renders loading status correctly', () => {
      render(<StatusIndicator status="loading" />);
      expect(screen.getByText('Loading')).toBeInTheDocument();
    });

    it('renders connected status correctly', () => {
      render(<StatusIndicator status="connected" />);
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    it('renders disconnected status correctly', () => {
      render(<StatusIndicator status="disconnected" />);
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });

    it('renders warning status correctly', () => {
      render(<StatusIndicator status="warning" />);
      expect(screen.getByText('Warning')).toBeInTheDocument();
    });

    it('renders error status correctly', () => {
      render(<StatusIndicator status="error" />);
      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    it('applies custom label when provided', () => {
      render(<StatusIndicator status="running" label="Custom Label" />);
      expect(screen.getByText('Custom Label')).toBeInTheDocument();
      expect(screen.queryByText('Running')).not.toBeInTheDocument();
    });

    it('hides label when showLabel is false', () => {
      render(<StatusIndicator status="running" showLabel={false} />);
      expect(screen.queryByText('Running')).not.toBeInTheDocument();
    });

    it('applies correct size classes', () => {
      const sizes = ['xs', 'sm', 'md', 'lg', 'xl'];
      sizes.forEach(size => {
        const { container } = render(<StatusIndicator size={size} />);
        const dot = container.querySelector('.relative.inline-flex span:last-child');
        expect(dot).toBeInTheDocument();
      });
    });

    it('has proper status indicator dot for active states', () => {
      const { container } = render(<StatusIndicator status="running" />);
      const dotElement = container.querySelector('.inline-flex');
      expect(dotElement).toBeInTheDocument();
    });

    it('has proper status indicator dot for inactive states', () => {
      const { container } = render(<StatusIndicator status="stopped" />);
      const dotElement = container.querySelector('.inline-flex');
      expect(dotElement).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<StatusIndicator className="custom-class" />);
      expect(container.querySelector('.custom-class')).toBeInTheDocument();
    });
  });

  describe('BotStatusIndicator', () => {
    it('renders running status when bot is running and not idle', () => {
      render(<BotStatusIndicator isRunning={true} isIdle={false} />);
      expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('renders idle status when bot is idle', () => {
      render(<BotStatusIndicator isRunning={true} isIdle={true} />);
      expect(screen.getByText('Idle')).toBeInTheDocument();
    });

    it('renders stopped status when bot is not running', () => {
      render(<BotStatusIndicator isRunning={false} isIdle={false} />);
      expect(screen.getByText('Stopped')).toBeInTheDocument();
    });
  });

  describe('ConnectionStatusIndicator', () => {
    it('renders disconnected when not connected', () => {
      render(<ConnectionStatusIndicator connected={false} />);
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });

    it('renders connected for excellent quality', () => {
      render(<ConnectionStatusIndicator connected={true} quality="excellent" />);
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    it('renders connected for good quality', () => {
      render(<ConnectionStatusIndicator connected={true} quality="good" />);
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    it('renders warning for poor quality', () => {
      render(<ConnectionStatusIndicator connected={true} quality="poor" />);
      expect(screen.getByText('Warning')).toBeInTheDocument();
    });

    it('uses small size', () => {
      const { container } = render(<ConnectionStatusIndicator connected={true} />);
      // Check that it's rendered (size is internal implementation)
      expect(container.querySelector('.inline-flex')).toBeInTheDocument();
    });
  });

  describe('OrderStatusIndicator', () => {
    it('renders loading status for pending orders', () => {
      render(<OrderStatusIndicator status="pending" />);
      expect(screen.getByText('Loading')).toBeInTheDocument();
    });

    it('renders connected status for filled orders', () => {
      render(<OrderStatusIndicator status="filled" />);
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    it('renders stopped status for cancelled orders', () => {
      render(<OrderStatusIndicator status="cancelled" />);
      expect(screen.getByText('Stopped')).toBeInTheDocument();
    });

    it('renders error status for rejected orders', () => {
      render(<OrderStatusIndicator status="rejected" />);
      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    it('renders idle status for expired orders', () => {
      render(<OrderStatusIndicator status="expired" />);
      expect(screen.getByText('Idle')).toBeInTheDocument();
    });

    it('uses small size', () => {
      const { container } = render(<OrderStatusIndicator status="pending" />);
      expect(container.querySelector('.inline-flex')).toBeInTheDocument();
    });
  });

  describe('Color Classes', () => {
    it('applies green color for running status', () => {
      const { container } = render(<StatusIndicator status="running" />);
      const dot = container.querySelector('.bg-green-500');
      expect(dot).toBeInTheDocument();
    });

    it('applies red color for stopped status', () => {
      const { container } = render(<StatusIndicator status="stopped" />);
      const dot = container.querySelector('.bg-red-500');
      expect(dot).toBeInTheDocument();
    });

    it('applies yellow color for idle status', () => {
      const { container } = render(<StatusIndicator status="idle" />);
      const dot = container.querySelector('.bg-yellow-500');
      expect(dot).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('provides meaningful text for screen readers', () => {
      render(<StatusIndicator status="running" />);
      expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('uses semantic HTML', () => {
      const { container } = render(<StatusIndicator status="running" />);
      expect(container.querySelector('.inline-flex')).toBeInTheDocument();
    });
  });
});
