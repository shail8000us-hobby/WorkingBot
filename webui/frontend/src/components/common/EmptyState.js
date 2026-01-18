import React from 'react';
import { TrendingUp, Package, Search } from 'lucide-react';
import '../../styles/animations.css';

/**
 * EmptyState Component
 * Beautiful empty state placeholders
 * 
 * Created: January 18, 2026
 * Safe: Pure UI component, no functional changes
 */

const EmptyState = ({
  icon: Icon = Package,
  title = 'No data available',
  description = 'There is nothing to display at the moment.',
  action,
  actionLabel = 'Get Started',
  className = ''
}) => {
  return (
    <div className={`flex flex-col items-center justify-center py-16 px-4 ${className}`}>
      <div className="relative mb-6">
        {/* Animated background circle */}
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-full blur-2xl animate-pulse" />
        
        {/* Icon container */}
        <div className="relative bg-slate-800/60 backdrop-blur-sm rounded-full p-6 border border-slate-700/50">
          <Icon className="h-12 w-12 text-slate-400" strokeWidth={1.5} />
        </div>
      </div>
      
      {/* Title */}
      <h3 className="text-xl font-semibold text-slate-200 mb-2 text-center">
        {title}
      </h3>
      
      {/* Description */}
      <p className="text-sm text-slate-400 mb-6 text-center max-w-md">
        {description}
      </p>
      
      {/* Action button */}
      {action && (
        <button
          onClick={action}
          className="glass-button px-6 py-3 text-sm font-medium hover:scale-105 transition-transform"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};

// Preset empty states
export const NoDataEmptyState = ({ onRefresh }) => (
  <EmptyState
    icon={TrendingUp}
    title="No data available"
    description="There are no records to display. Start trading to see your data here."
    action={onRefresh}
    actionLabel="Refresh"
  />
);

export const SearchEmptyState = ({ searchTerm, onClear }) => (
  <EmptyState
    icon={Search}
    title="No results found"
    description={`We couldn't find anything matching "${searchTerm}". Try a different search term.`}
    action={onClear}
    actionLabel="Clear Search"
  />
);

export const NoPositionsEmptyState = ({ onAddPosition }) => (
  <EmptyState
    icon={Package}
    title="No open positions"
    description="You don't have any open positions. Start trading to see your positions here."
    action={onAddPosition}
    actionLabel="Open Position"
  />
);

export default EmptyState;
