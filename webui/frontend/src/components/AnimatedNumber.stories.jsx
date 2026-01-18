import React from 'react';
import AnimatedNumber from './AnimatedNumber';

export default {
  title: 'Components/AnimatedNumber',
  component: AnimatedNumber,
  tags: ['autodocs'],
  argTypes: {
    value: {
      control: { type: 'number' },
      description: 'Numeric value to display',
    },
    prefix: {
      control: 'text',
      description: 'Prefix (e.g., $)',
    },
    suffix: {
      control: 'text',
      description: 'Suffix (e.g., %)',
    },
    decimals: {
      control: { type: 'number', min: 0, max: 4 },
      description: 'Number of decimal places',
    },
    duration: {
      control: { type: 'number', min: 100, max: 2000, step: 100 },
      description: 'Animation duration in ms',
    },
    highlightOnChange: {
      control: 'boolean',
      description: 'Flash on value change (disabled in Phase 4)',
    },
  },
};

export const Default = {
  args: {
    value: 1234.56,
  },
};

export const Currency = {
  args: {
    value: 5678.99,
    prefix: '$',
    decimals: 2,
  },
};

export const Percentage = {
  args: {
    value: 12.5,
    suffix: '%',
    decimals: 1,
  },
};

export const LargeNumber = {
  args: {
    value: 123456789,
    decimals: 0,
  },
};

export const NegativeNumber = {
  args: {
    value: -999.99,
    prefix: '$',
    decimals: 2,
  },
};

export const FastAnimation = {
  args: {
    value: 42,
    duration: 300,
  },
};

export const SlowAnimation = {
  args: {
    value: 42,
    duration: 2000,
  },
};

// Interactive demo with changing values
export const Interactive = () => {
  const [value, setValue] = React.useState(100);

  return (
    <div style={{ padding: '20px', background: '#0f172a', color: 'white' }}>
      <div style={{ marginBottom: '20px' }}>
        <AnimatedNumber value={value} prefix="$" decimals={2} />
      </div>
      <div style={{ display: 'flex', gap: '10px' }}>
        <button 
          onClick={() => setValue(v => v + 100)}
          style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: '4px', color: 'white', cursor: 'pointer' }}
        >
          +$100
        </button>
        <button 
          onClick={() => setValue(v => v - 100)}
          style={{ padding: '8px 16px', background: '#ef4444', border: 'none', borderRadius: '4px', color: 'white', cursor: 'pointer' }}
        >
          -$100
        </button>
        <button 
          onClick={() => setValue(Math.random() * 10000)}
          style={{ padding: '8px 16px', background: '#3b82f6', border: 'none', borderRadius: '4px', color: 'white', cursor: 'pointer' }}
        >
          Random
        </button>
      </div>
    </div>
  );
};
