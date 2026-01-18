import React from 'react';
import CollapsibleCard from './CollapsibleCard';

export default {
  title: 'Components/CollapsibleCard',
  component: CollapsibleCard,
  tags: ['autodocs'],
  argTypes: {
    title: {
      control: 'text',
      description: 'Card title',
    },
    defaultExpanded: {
      control: 'boolean',
      description: 'Whether card starts expanded',
    },
    icon: {
      control: 'text',
      description: 'Icon to display',
    },
  },
  decorators: [
    (Story) => (
      <div style={{ padding: '20px', background: '#0f172a', minHeight: '300px' }}>
        <Story />
      </div>
    ),
  ],
};

export const Default = {
  args: {
    title: 'Collapsible Card',
    children: (
      <div>
        <p style={{ color: '#cbd5e1' }}>This is the card content.</p>
        <p style={{ color: '#cbd5e1' }}>It can be collapsed and expanded.</p>
      </div>
    ),
  },
};

export const WithIcon = {
  args: {
    title: 'Settings',
    icon: '⚙️',
    children: (
      <div>
        <p style={{ color: '#cbd5e1' }}>Settings content goes here.</p>
      </div>
    ),
  },
};

export const InitiallyExpanded = {
  args: {
    title: 'Expanded by Default',
    defaultExpanded: true,
    children: (
      <div>
        <p style={{ color: '#cbd5e1' }}>This card starts in the expanded state.</p>
      </div>
    ),
  },
};

export const InitiallyCollapsed = {
  args: {
    title: 'Collapsed by Default',
    defaultExpanded: false,
    children: (
      <div>
        <p style={{ color: '#cbd5e1' }}>This card starts collapsed.</p>
      </div>
    ),
  },
};

export const LongContent = {
  args: {
    title: 'Long Content Example',
    icon: '📝',
    defaultExpanded: true,
    children: (
      <div style={{ color: '#cbd5e1' }}>
        <h3 style={{ color: '#f1f5f9', marginBottom: '12px' }}>Detailed Information</h3>
        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>
        <p>Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>
        <ul style={{ marginTop: '12px' }}>
          <li>Feature 1</li>
          <li>Feature 2</li>
          <li>Feature 3</li>
        </ul>
      </div>
    ),
  },
};

export const Multiple = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
    <CollapsibleCard title="Card 1" icon="1️⃣" defaultExpanded={true}>
      <p style={{ color: '#cbd5e1' }}>Content for card 1</p>
    </CollapsibleCard>
    <CollapsibleCard title="Card 2" icon="2️⃣" defaultExpanded={false}>
      <p style={{ color: '#cbd5e1' }}>Content for card 2</p>
    </CollapsibleCard>
    <CollapsibleCard title="Card 3" icon="3️⃣" defaultExpanded={false}>
      <p style={{ color: '#cbd5e1' }}>Content for card 3</p>
    </CollapsibleCard>
  </div>
);
