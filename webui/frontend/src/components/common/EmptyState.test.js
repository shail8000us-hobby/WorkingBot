import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import EmptyState, {
  NoDataEmptyState,
  SearchEmptyState,
  NoPositionsEmptyState,
} from './EmptyState';
import { Package, TrendingUp, Search } from 'lucide-react';

describe('EmptyState', () => {
  describe('Basic EmptyState', () => {
    it('renders with default props', () => {
      render(<EmptyState />);
      expect(screen.getByText('No data available')).toBeInTheDocument();
      expect(screen.getByText('There is nothing to display at the moment.')).toBeInTheDocument();
    });

    it('renders custom title', () => {
      render(<EmptyState title="Custom Title" />);
      expect(screen.getByText('Custom Title')).toBeInTheDocument();
    });

    it('renders custom description', () => {
      render(<EmptyState description="Custom description text" />);
      expect(screen.getByText('Custom description text')).toBeInTheDocument();
    });

    it('renders default icon (Package)', () => {
      const { container } = render(<EmptyState />);
      // lucide-react icons have an SVG element
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('renders custom icon', () => {
      const { container } = render(<EmptyState icon={TrendingUp} />);
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<EmptyState className="custom-class" />);
      expect(container.querySelector('.custom-class')).toBeInTheDocument();
    });
  });

  describe('Action Button', () => {
    it('does not render action button when action is not provided', () => {
      render(<EmptyState />);
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('renders action button when action is provided', () => {
      const mockAction = jest.fn();
      render(<EmptyState action={mockAction} />);
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('renders default action label', () => {
      const mockAction = jest.fn();
      render(<EmptyState action={mockAction} />);
      expect(screen.getByText('Get Started')).toBeInTheDocument();
    });

    it('renders custom action label', () => {
      const mockAction = jest.fn();
      render(<EmptyState action={mockAction} actionLabel="Click Me" />);
      expect(screen.getByText('Click Me')).toBeInTheDocument();
    });

    it('calls action function when button is clicked', () => {
      const mockAction = jest.fn();
      render(<EmptyState action={mockAction} actionLabel="Click Me" />);

      const button = screen.getByText('Click Me');
      fireEvent.click(button);

      expect(mockAction).toHaveBeenCalledTimes(1);
    });

    it('applies glass-button class to action button', () => {
      const mockAction = jest.fn();
      render(<EmptyState action={mockAction} />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('glass-button');
    });
  });

  describe('NoDataEmptyState', () => {
    it('renders with correct title', () => {
      render(<NoDataEmptyState />);
      expect(screen.getByText('No data available')).toBeInTheDocument();
    });

    it('renders with correct description', () => {
      render(<NoDataEmptyState />);
      expect(screen.getByText(/There are no records to display/)).toBeInTheDocument();
    });

    it('uses TrendingUp icon', () => {
      const { container } = render(<NoDataEmptyState />);
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('renders refresh button when onRefresh is provided', () => {
      const mockRefresh = jest.fn();
      render(<NoDataEmptyState onRefresh={mockRefresh} />);
      expect(screen.getByText('Refresh')).toBeInTheDocument();
    });

    it('calls onRefresh when button is clicked', () => {
      const mockRefresh = jest.fn();
      render(<NoDataEmptyState onRefresh={mockRefresh} />);

      const button = screen.getByText('Refresh');
      fireEvent.click(button);

      expect(mockRefresh).toHaveBeenCalledTimes(1);
    });
  });

  describe('SearchEmptyState', () => {
    it('renders with correct title', () => {
      render(<SearchEmptyState searchTerm="test query" />);
      expect(screen.getByText('No results found')).toBeInTheDocument();
    });

    it('includes search term in description', () => {
      render(<SearchEmptyState searchTerm="test query" />);
      expect(screen.getByText(/test query/)).toBeInTheDocument();
    });

    it('uses Search icon', () => {
      const { container } = render(<SearchEmptyState searchTerm="test" />);
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('renders clear button when onClear is provided', () => {
      const mockClear = jest.fn();
      render(<SearchEmptyState searchTerm="test" onClear={mockClear} />);
      expect(screen.getByText('Clear Search')).toBeInTheDocument();
    });

    it('calls onClear when button is clicked', () => {
      const mockClear = jest.fn();
      render(<SearchEmptyState searchTerm="test" onClear={mockClear} />);

      const button = screen.getByText('Clear Search');
      fireEvent.click(button);

      expect(mockClear).toHaveBeenCalledTimes(1);
    });
  });

  describe('NoPositionsEmptyState', () => {
    it('renders with correct title', () => {
      render(<NoPositionsEmptyState />);
      expect(screen.getByText('No open positions')).toBeInTheDocument();
    });

    it('renders with correct description', () => {
      render(<NoPositionsEmptyState />);
      expect(screen.getByText(/You don't have any open positions/)).toBeInTheDocument();
    });

    it('uses Package icon', () => {
      const { container } = render(<NoPositionsEmptyState />);
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('renders add position button when onAddPosition is provided', () => {
      const mockAdd = jest.fn();
      render(<NoPositionsEmptyState onAddPosition={mockAdd} />);
      expect(screen.getByText('Open Position')).toBeInTheDocument();
    });

    it('calls onAddPosition when button is clicked', () => {
      const mockAdd = jest.fn();
      render(<NoPositionsEmptyState onAddPosition={mockAdd} />);

      const button = screen.getByText('Open Position');
      fireEvent.click(button);

      expect(mockAdd).toHaveBeenCalledTimes(1);
    });
  });

  describe('Visual Structure', () => {
    it('has correct container classes', () => {
      const { container } = render(<EmptyState />);
      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('flex', 'flex-col', 'items-center', 'justify-center');
    });

    it('contains icon container with background', () => {
      const { container } = render(<EmptyState />);
      const iconContainer = container.querySelector('.bg-slate-800\\/60');
      expect(iconContainer).toBeInTheDocument();
    });

    it('applies proper text hierarchy', () => {
      render(<EmptyState title="Title" description="Description" />);
      const title = screen.getByText('Title');
      const description = screen.getByText('Description');

      expect(title).toHaveClass('text-xl');
      expect(description).toHaveClass('text-sm');
    });
  });

  describe('Accessibility', () => {
    it('uses semantic heading for title', () => {
      render(<EmptyState title="Test Title" />);
      const title = screen.getByText('Test Title');
      expect(title.tagName).toBe('H3');
    });

    it('uses paragraph for description', () => {
      render(<EmptyState description="Test description" />);
      const description = screen.getByText('Test description');
      expect(description.tagName).toBe('P');
    });

    it('button is keyboard accessible', () => {
      const mockAction = jest.fn();
      render(<EmptyState action={mockAction} actionLabel="Test Button" />);
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });
  });

  describe('Animations', () => {
    it('has background styling', () => {
      const { container } = render(<EmptyState />);
      const bgElement = container.querySelector('.bg-gradient-to-br');
      expect(bgElement).toBeInTheDocument();
    });

    it('has gradient background on icon container', () => {
      const { container } = render(<EmptyState />);
      const gradientBg = container.querySelector('.bg-gradient-to-br');
      expect(gradientBg).toBeInTheDocument();
    });
  });
});
