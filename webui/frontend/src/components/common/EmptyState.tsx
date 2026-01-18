import React from 'react';
import { LucideIcon, Package } from 'lucide-react';
import clsx from 'clsx';

/**
 * EmptyState Component
 * Placeholder for empty data states
 *
 * Created: January 18, 2026 (Migrated to TypeScript)
 * Safe: Pure UI component, no functional changes
 */

interface EmptyStateProps {
  icon?: LucideIcon;
  title?: string;
  description?: string;
  action?: () => void;
  actionLabel?: string;
  className?: string;
}

const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = Package,
  title = 'No data available',
  description = 'There is nothing to display at the moment.',
  action,
  actionLabel = 'Get Started',
  className,
}) => {
  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center py-12 px-4 text-center',
        className
      )}
    >
      {/* Animated background */}
      <div className="relative mb-6">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-800/40 to-slate-900/40 rounded-full blur-2xl" />
        <div className="relative bg-slate-800/60 rounded-full p-6 backdrop-blur-sm">
          <Icon className="w-12 h-12 text-slate-400" />
        </div>
      </div>

      {/* Content */}
      <h3 className="text-xl font-semibold text-slate-100 mb-2">{title}</h3>
      <p className="text-sm text-slate-400 max-w-md mb-6">{description}</p>

      {/* Optional action button */}
      {action && (
        <button
          onClick={action}
          className="glass-button px-6 py-2 rounded-lg font-medium transition-all hover:scale-105"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};

// Specialized empty states
interface NoDataEmptyStateProps {
  onRefresh?: () => void;
}

export const NoDataEmptyState: React.FC<NoDataEmptyStateProps> = ({ onRefresh }) => {
  const { TrendingUp } = require('lucide-react');
  return (
    <EmptyState
      icon={TrendingUp}
      title="No data available"
      description="There are no records to display at this time. Try refreshing or adjusting your filters."
      action={onRefresh}
      actionLabel="Refresh"
    />
  );
};

interface SearchEmptyStateProps {
  searchTerm: string;
  onClear?: () => void;
}

export const SearchEmptyState: React.FC<SearchEmptyStateProps> = ({ searchTerm, onClear }) => {
  const { Search } = require('lucide-react');
  return (
    <EmptyState
      icon={Search}
      title="No results found"
      description={`No items match "${searchTerm}". Try a different search term or clear your filters.`}
      action={onClear}
      actionLabel="Clear Search"
    />
  );
};

interface NoPositionsEmptyStateProps {
  onAddPosition?: () => void;
}

export const NoPositionsEmptyState: React.FC<NoPositionsEmptyStateProps> = ({ onAddPosition }) => {
  return (
    <EmptyState
      icon={Package}
      title="No open positions"
      description="You don't have any open positions at the moment. Start trading to see your positions here."
      action={onAddPosition}
      actionLabel="Open Position"
    />
  );
};

export default EmptyState;
