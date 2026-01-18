import React from 'react';
import EmptyState from './EmptyState';

export default {
  title: 'Components/EmptyState',
  component: EmptyState,
  tags: ['autodocs'],
  argTypes: {
    icon: {
      control: 'text',
      description: 'Icon component or emoji',
    },
    title: {
      control: 'text',
      description: 'Title text',
    },
    description: {
      control: 'text',
      description: 'Description text',
    },
    action: {
      description: 'Action button configuration',
    },
  },
  decorators: [
    (Story) => (
      <div style={{ padding: '40px', background: '#0f172a', minHeight: '400px' }}>
        <Story />
      </div>
    ),
  ],
};

export const Default = {
  args: {
    icon: '📭',
    title: 'No data available',
    description: 'There is no data to display at the moment.',
  },
};

export const NoPositions = {
  args: {
    icon: '📊',
    title: 'No active positions',
    description: 'You have no open positions. Start trading to see them here.',
    action: {
      label: 'Start Trading',
      onClick: () => alert('Navigate to trading'),
    },
  },
};

export const NoNotifications = {
  args: {
    icon: '🔔',
    title: 'No notifications',
    description: "You're all caught up! No new notifications.",
  },
};

export const NoResults = {
  args: {
    icon: '🔍',
    title: 'No results found',
    description: 'Try adjusting your search or filter criteria.',
    action: {
      label: 'Clear Filters',
      onClick: () => alert('Clear filters'),
    },
  },
};

export const ConnectionError = {
  args: {
    icon: '⚠️',
    title: 'Connection Error',
    description: 'Unable to connect to the server. Please check your connection.',
    action: {
      label: 'Retry',
      onClick: () => alert('Retry connection'),
    },
  },
};

export const CustomIcon = {
  args: {
    icon: '🎯',
    title: 'Welcome!',
    description: 'Get started by configuring your first trading bot.',
    action: {
      label: 'Configure Bot',
      onClick: () => alert('Configure bot'),
    },
  },
};
