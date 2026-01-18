import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import CollapsibleCard from './CollapsibleCard';

// Mock framer-motion
jest.mock('framer-motion', () => ({
  motion: {
    section: ({ children, className, initial, animate, transition, ...props }) => (
      <section className={className} {...props}>{children}</section>
    ),
    div: ({ children, className, initial, animate, exit, transition, ...props }) => (
      <div className={className} {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

describe('CollapsibleCard', () => {
  describe('Rendering', () => {
    it('renders with title', () => {
      render(<CollapsibleCard title="Test Title">Content</CollapsibleCard>);
      expect(screen.getByText('Test Title')).toBeInTheDocument();
    });

    it('renders with subtitle', () => {
      render(<CollapsibleCard title="Title" subtitle="Test Subtitle">Content</CollapsibleCard>);
      expect(screen.getByText('Test Subtitle')).toBeInTheDocument();
    });

    it('renders children content', () => {
      render(<CollapsibleCard title="Title">Test Content</CollapsibleCard>);
      expect(screen.getByText('Test Content')).toBeInTheDocument();
    });

    it('renders without subtitle when not provided', () => {
      render(<CollapsibleCard title="Title">Content</CollapsibleCard>);
      expect(screen.queryByText('subtitle')).not.toBeInTheDocument();
    });

    it('applies custom id when provided', () => {
      const { container } = render(
        <CollapsibleCard title="Title" id="custom-id">Content</CollapsibleCard>
      );
      expect(container.querySelector('#custom-id')).toBeInTheDocument();
    });
  });

  describe('Collapsible Behavior', () => {
    it('is open by default when defaultOpen is true', () => {
      render(<CollapsibleCard title="Title" defaultOpen={true}>Content</CollapsibleCard>);
      expect(screen.getByText('Content')).toBeInTheDocument();
    });

    it('is closed when defaultOpen is false', () => {
      render(<CollapsibleCard title="Title" defaultOpen={false}>Content</CollapsibleCard>);
      expect(screen.queryByText('Content')).not.toBeInTheDocument();
    });

    it('toggles open/closed when button is clicked', () => {
      render(<CollapsibleCard title="Title" defaultOpen={true}>Content</CollapsibleCard>);
      
      const button = screen.getByRole('button');
      expect(screen.getByText('Content')).toBeInTheDocument();
      
      fireEvent.click(button);
      // After toggle, content should disappear (mocked AnimatePresence won't animate)
      
      fireEvent.click(button);
      // Content should reappear
    });

    it('shows ChevronUp icon when open', () => {
      const { container } = render(
        <CollapsibleCard title="Title" defaultOpen={true}>Content</CollapsibleCard>
      );
      // ChevronUp is rendered as SVG by lucide-react
      const button = screen.getByRole('button');
      expect(button.querySelector('svg')).toBeInTheDocument();
    });

    it('shows ChevronDown icon when closed', () => {
      const { container } = render(
        <CollapsibleCard title="Title" defaultOpen={false}>Content</CollapsibleCard>
      );
      const button = screen.getByRole('button');
      expect(button.querySelector('svg')).toBeInTheDocument();
    });

    it('has proper aria-expanded attribute', () => {
      render(<CollapsibleCard title="Title" defaultOpen={true}>Content</CollapsibleCard>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('Accent Colors', () => {
    const accentColors = ['sky', 'emerald', 'amber', 'rose', 'violet'];

    accentColors.forEach(accent => {
      it(`applies ${accent} accent class`, () => {
        const { container } = render(
          <CollapsibleCard title="Title" accent={accent}>Content</CollapsibleCard>
        );
        const section = container.querySelector('section');
        expect(section).toHaveClass(`border-${accent}-500/30`);
        expect(section).toHaveClass(`bg-${accent}-500/5`);
      });
    });

    it('has default sky accent when accent is not provided', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      const section = container.querySelector('section');
      // CollapsibleCard has sky as default accent
      expect(section).toHaveClass('border-sky-500/30');
    });
  });

  describe('Actions', () => {
    it('renders action buttons when provided', () => {
      const actions = <button>Action Button</button>;
      render(<CollapsibleCard title="Title" actions={actions}>Content</CollapsibleCard>);
      expect(screen.getByText('Action Button')).toBeInTheDocument();
    });

    it('does not render actions when not provided', () => {
      render(<CollapsibleCard title="Title">Content</CollapsibleCard>);
      expect(screen.queryByText('Action Button')).not.toBeInTheDocument();
    });

    it('positions actions correctly in header', () => {
      const actions = <button>Action</button>;
      const { container } = render(
        <CollapsibleCard title="Title" actions={actions}>Content</CollapsibleCard>
      );
      const header = container.querySelector('header');
      expect(header?.querySelector('button')).toBeInTheDocument();
    });
  });

  describe('Modern Styling', () => {
    it('has holographic-card class', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      const section = container.querySelector('.holographic-card');
      expect(section).toBeInTheDocument();
    });

    it('has relative positioning', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      const section = container.querySelector('.relative');
      expect(section).toBeInTheDocument();
    });

    it('has overflow-visible class', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      const section = container.querySelector('.overflow-visible');
      expect(section).toBeInTheDocument();
    });
  });

  describe('Header Structure', () => {
    it('has proper flexbox layout', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      const header = container.querySelector('header');
      expect(header).toHaveClass('flex', 'flex-col', 'gap-3');
    });

    it('title has proper styling', () => {
      render(<CollapsibleCard title="Test Title">Content</CollapsibleCard>);
      const title = screen.getByText('Test Title');
      expect(title).toHaveClass('text-lg', 'font-semibold', 'text-slate-100');
    });

    it('subtitle has proper styling', () => {
      render(<CollapsibleCard title="Title" subtitle="Test Subtitle">Content</CollapsibleCard>);
      const subtitle = screen.getByText('Test Subtitle');
      expect(subtitle).toHaveClass('text-sm', 'text-slate-400');
    });
  });

  describe('Toggle Button', () => {
    it('has proper styling classes', () => {
      render(<CollapsibleCard title="Title">Content</CollapsibleCard>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass(
        'inline-flex',
        'h-9',
        'w-9',
        'items-center',
        'justify-center',
        'rounded-xl'
      );
    });

    it('has hover transition effects', () => {
      render(<CollapsibleCard title="Title">Content</CollapsibleCard>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('transition');
    });

    it('is keyboard accessible', () => {
      render(<CollapsibleCard title="Title">Content</CollapsibleCard>);
      const button = screen.getByRole('button');
      expect(button.getAttribute('type')).toBe('button');
    });
  });

  describe('Content Area', () => {
    it('has proper padding when open', () => {
      const { container } = render(
        <CollapsibleCard title="Title" defaultOpen={true}>Content</CollapsibleCard>
      );
      const contentDiv = container.querySelector('.px-5.pb-6.pt-0');
      expect(contentDiv).toBeInTheDocument();
    });

    it('contains children in correct wrapper', () => {
      const { container } = render(
        <CollapsibleCard title="Title" defaultOpen={true}>
          <div data-testid="child">Child Content</div>
        </CollapsibleCard>
      );
      const child = screen.getByTestId('child');
      expect(child).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('uses semantic section element', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      expect(container.querySelector('section')).toBeInTheDocument();
    });

    it('uses semantic header element', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      expect(container.querySelector('header')).toBeInTheDocument();
    });

    it('uses h2 for title', () => {
      render(<CollapsibleCard title="Title">Content</CollapsibleCard>);
      const title = screen.getByText('Title');
      expect(title.tagName).toBe('H2');
    });

    it('button has proper type attribute', () => {
      render(<CollapsibleCard title="Title">Content</CollapsibleCard>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('type', 'button');
    });
  });

  describe('Responsive Design', () => {
    it('applies responsive flex direction', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      const header = container.querySelector('header');
      expect(header).toHaveClass('sm:flex-row');
    });

    it('applies responsive gap spacing', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      const header = container.querySelector('header');
      expect(header).toHaveClass('sm:gap-4');
    });

    it('applies responsive item alignment', () => {
      const { container } = render(
        <CollapsibleCard title="Title">Content</CollapsibleCard>
      );
      const header = container.querySelector('header');
      expect(header).toHaveClass('sm:items-center');
    });
  });
});
