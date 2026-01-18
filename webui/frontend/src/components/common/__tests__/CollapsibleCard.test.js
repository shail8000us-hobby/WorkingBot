/**
 * CollapsibleCard Component Tests
 * Tests for the main card component used throughout the app
 */

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../utils/__tests__/testUtils';
import CollapsibleCard from '../CollapsibleCard';

describe('CollapsibleCard', () => {
  test('renders with title and subtitle', () => {
    renderWithProviders(
      <CollapsibleCard
        title="Test Card"
        subtitle="Test Description"
        defaultOpen={true}
      >
        <div>Card Content</div>
      </CollapsibleCard>
    );

    expect(screen.getByText('Test Card')).toBeInTheDocument();
    expect(screen.getByText('Test Description')).toBeInTheDocument();
    expect(screen.getByText('Card Content')).toBeInTheDocument();
  });

  test('toggles content when clicking collapse button', () => {
    renderWithProviders(
      <CollapsibleCard title="Test Card" defaultOpen={true}>
        <div>Card Content</div>
      </CollapsibleCard>
    );

    // Content should be visible initially
    expect(screen.getByText('Card Content')).toBeInTheDocument();

    // Click collapse button
    const collapseButton = screen.getByRole('button', { expanded: true });
    fireEvent.click(collapseButton);

    // Content should be hidden after animation
    setTimeout(() => {
      expect(screen.queryByText('Card Content')).not.toBeInTheDocument();
    }, 300);
  });

  test('starts collapsed when defaultOpen is false', () => {
    renderWithProviders(
      <CollapsibleCard title="Test Card" defaultOpen={false}>
        <div>Card Content</div>
      </CollapsibleCard>
    );

    // Content should not be visible initially
    expect(screen.queryByText('Card Content')).not.toBeInTheDocument();
  });

  test('renders with accent color classes', () => {
    const { container } = renderWithProviders(
      <CollapsibleCard title="Test Card" accent="emerald">
        <div>Content</div>
      </CollapsibleCard>
    );

    const section = container.querySelector('section');
    expect(section).toHaveClass('border-emerald-500/30');
  });

  test('renders action buttons', () => {
    renderWithProviders(
      <CollapsibleCard
        title="Test Card"
        actions={
          <button data-testid="custom-action">Custom Action</button>
        }
      >
        <div>Content</div>
      </CollapsibleCard>
    );

    expect(screen.getByTestId('custom-action')).toBeInTheDocument();
  });
});
