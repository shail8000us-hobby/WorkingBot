import React from 'react';
import LoadingSkeleton from './LoadingSkeleton';

export default {
  title: 'Components/LoadingSkeleton',
  component: LoadingSkeleton,
  tags: ['autodocs'],
  argTypes: {
    type: {
      control: 'select',
      options: ['text', 'title', 'card', 'list', 'chart', 'table'],
      description: 'Type of skeleton to display',
    },
    count: {
      control: { type: 'number', min: 1, max: 10 },
      description: 'Number of skeleton elements (for list/table)',
    },
    width: {
      control: 'text',
      description: 'Custom width',
    },
    height: {
      control: 'text',
      description: 'Custom height',
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

export const Text = {
  args: {
    type: 'text',
  },
};

export const Title = {
  args: {
    type: 'title',
  },
};

export const Card = {
  args: {
    type: 'card',
  },
};

export const List = {
  args: {
    type: 'list',
    count: 5,
  },
};

export const Chart = {
  args: {
    type: 'chart',
  },
};

export const Table = {
  args: {
    type: 'table',
    count: 4,
  },
};

export const CustomSize = {
  args: {
    type: 'text',
    width: '300px',
    height: '60px',
  },
};

// Showcase all types
export const AllTypes = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
    <div>
      <h3 style={{ color: '#94a3b8', marginBottom: '12px' }}>Text</h3>
      <LoadingSkeleton type="text" />
    </div>
    <div>
      <h3 style={{ color: '#94a3b8', marginBottom: '12px' }}>Title</h3>
      <LoadingSkeleton type="title" />
    </div>
    <div>
      <h3 style={{ color: '#94a3b8', marginBottom: '12px' }}>Card</h3>
      <LoadingSkeleton type="card" />
    </div>
    <div>
      <h3 style={{ color: '#94a3b8', marginBottom: '12px' }}>List (3 items)</h3>
      <LoadingSkeleton type="list" count={3} />
    </div>
    <div>
      <h3 style={{ color: '#94a3b8', marginBottom: '12px' }}>Chart</h3>
      <LoadingSkeleton type="chart" />
    </div>
    <div>
      <h3 style={{ color: '#94a3b8', marginBottom: '12px' }}>Table (3 rows)</h3>
      <LoadingSkeleton type="table" count={3} />
    </div>
  </div>
);
