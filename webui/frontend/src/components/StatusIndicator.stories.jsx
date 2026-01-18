import React from 'react';
import StatusIndicator from './StatusIndicator';

export default {
  title: 'Components/StatusIndicator',
  component: StatusIndicator,
  tags: ['autodocs'],
  argTypes: {
    status: {
      control: 'select',
      options: ['running', 'stopped', 'loading', 'warning', 'error', 'unknown'],
      description: 'Status type to display',
    },
    label: {
      control: 'text',
      description: 'Label text to display',
    },
    size: {
      control: 'select',
      options: ['small', 'medium', 'large'],
      description: 'Size of the indicator',
    },
    pulse: {
      control: 'boolean',
      description: 'Whether the indicator should pulse (disabled in Phase 4)',
    },
  },
};

// Default story
export const Running = {
  args: {
    status: 'running',
    label: 'Running',
  },
};

export const Stopped = {
  args: {
    status: 'stopped',
    label: 'Stopped',
  },
};

export const Loading = {
  args: {
    status: 'loading',
    label: 'Loading...',
  },
};

export const Warning = {
  args: {
    status: 'warning',
    label: 'Warning',
  },
};

export const Error = {
  args: {
    status: 'error',
    label: 'Error',
  },
};

export const Unknown = {
  args: {
    status: 'unknown',
    label: 'Unknown',
  },
};

export const Small = {
  args: {
    status: 'running',
    label: 'Small Running',
    size: 'small',
  },
};

export const Large = {
  args: {
    status: 'running',
    label: 'Large Running',
    size: 'large',
  },
};

// All statuses in one view
export const AllStatuses = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '20px', background: '#0f172a' }}>
    <StatusIndicator status="running" label="Running" />
    <StatusIndicator status="stopped" label="Stopped" />
    <StatusIndicator status="loading" label="Loading" />
    <StatusIndicator status="warning" label="Warning" />
    <StatusIndicator status="error" label="Error" />
    <StatusIndicator status="unknown" label="Unknown" />
  </div>
);
