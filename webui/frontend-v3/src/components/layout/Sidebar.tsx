/**
 * Sidebar Component
 * 
 * Left navigation sidebar with:
 * - Navigation links
 * - Quick stats
 * - Collapsible design
 */

'use client';

import { memo, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { 
  LayoutDashboard, 
  Grid3X3, 
  Wallet, 
  ClipboardList, 
  Brain,
  Shield,
  Settings,
  Activity,
  TrendingUp,
  AlertCircle,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Code,
  BookOpen,
  RefreshCw,
  SlidersHorizontal,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useAppStore, useTradingStore } from '@/stores';
import { StatusBadge, PriceDisplay } from '@/components/common';
import { useTradingStatus, useGuardianStatus } from '@/hooks';

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string | number;
}

const mainNavItems: NavItem[] = [
  { title: 'Dashboard', href: '/', icon: LayoutDashboard },
  { title: 'Grid Trading', href: '/grid', icon: Grid3X3 },
  { title: 'Positions', href: '/positions', icon: Wallet },
  { title: 'Orders', href: '/orders', icon: ClipboardList },
  { title: 'Trade History', href: '/dashboard/trades', icon: TrendingUp },
];

const analyticsNavItems: NavItem[] = [
  { title: 'Analytics', href: '/dashboard/analytics', icon: TrendingUp },
  { title: 'Performance', href: '/dashboard/performance', icon: Activity },
  { title: 'Charts', href: '/dashboard/charts', icon: LayoutDashboard },
  { title: 'Backtest', href: '/dashboard/backtest', icon: Grid3X3 },
  { title: 'Strategy Compare', href: '/dashboard/strategy', icon: Grid3X3 },
  { title: 'RSI Monitor', href: '/rsi', icon: BarChart3 },
  { title: 'Portfolio', href: '/portfolio', icon: TrendingUp },
  { title: 'Strategy Editor', href: '/strategy-editor', icon: Grid3X3 },
];

const systemNavItems: NavItem[] = [
  { title: 'Bot Brain', href: '/brain', icon: Brain },
  { title: 'Brain Flow', href: '/brain-flow', icon: Brain },
  { title: 'Bot Actions', href: '/actions', icon: Activity },
  { title: 'Guardian', href: '/guardian', icon: Shield },
  { title: 'Health', href: '/health', icon: Activity },
  { title: 'Bot Management', href: '/bot-management', icon: Activity },
  { title: 'Intelligence', href: '/intelligence', icon: Brain },
  { title: 'Resources', href: '/dashboard/resources', icon: Activity },
  { title: 'Cache', href: '/dashboard/cache', icon: Activity },
  { title: 'Database', href: '/dashboard/database', icon: Activity },
  { title: 'Network', href: '/dashboard/network', icon: Activity },
];

const managementNavItems: NavItem[] = [
  { title: 'Settings', href: '/dashboard/settings', icon: Settings },
  { title: 'Configuration', href: '/config', icon: Settings },
  { title: 'API Keys', href: '/dashboard/api-keys', icon: Settings },
  { title: 'Risk & Safety', href: '/risk', icon: AlertCircle },
  { title: 'Risk Limits', href: '/dashboard/risk', icon: AlertCircle },
  { title: 'Scheduler', href: '/dashboard/scheduler', icon: Settings },
  { title: 'Backup', href: '/dashboard/backup', icon: Settings },
  { title: 'Audit Log', href: '/dashboard/audit', icon: Settings },
  { title: 'Symbols', href: '/dashboard/symbols', icon: Settings },
  { title: 'Integrations', href: '/dashboard/integrations', icon: Settings },
];

const monitoringNavItems: NavItem[] = [
  { title: 'API Monitor', href: '/dashboard/api-monitor', icon: Activity },
  { title: 'Debug', href: '/dashboard/debug', icon: AlertCircle },
  { title: 'Logs', href: '/logs', icon: Settings },
  { title: 'Errors', href: '/dashboard/errors', icon: AlertCircle },
  { title: 'Alerts', href: '/dashboard/alerts', icon: AlertCircle },
  { title: 'Sessions', href: '/dashboard/sessions', icon: Settings },
  { title: 'Reconciliation', href: '/dashboard/reconciliation', icon: Shield },
  { title: 'Compliance', href: '/dashboard/compliance', icon: Shield },
];

const toolsNavItems: NavItem[] = [
  { title: 'File Editor', href: '/file-editor', icon: Code },
  { title: 'Config Visual Editor', href: '/config-visual-editor', icon: SlidersHorizontal },
  { title: 'Mode Switcher', href: '/mode-switcher', icon: RefreshCw },
  { title: 'Todo List', href: '/todos', icon: BookOpen },
  { title: 'Plugins', href: '/dashboard/plugins', icon: Settings },
  { title: 'Templates', href: '/dashboard/templates', icon: Settings },
  { title: 'Scripts', href: '/dashboard/scripts', icon: Settings },
  { title: 'Webhooks', href: '/dashboard/webhooks', icon: Settings },
  { title: 'Export Data', href: '/dashboard/export', icon: Settings },
  { title: 'Market Data', href: '/dashboard/market', icon: Activity },
  { title: 'Theme', href: '/dashboard/theme', icon: Settings },
  { title: 'Help', href: '/dashboard/help', icon: AlertCircle },
];

interface SidebarProps {
  className?: string;
}

export const Sidebar = memo(function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();
  const { sidebarOpen, setSidebarOpen } = useAppStore();
  const { totalPnLINR, totalPositions, tradingAllowed } = useTradingStore();
  const { data: tradingStatus } = useTradingStatus();
  const { data: guardianStatus } = useGuardianStatus();
  
  // State for collapsed sections
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  
  const toggleSection = (section: string) => {
    setCollapsedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };
  
  const isSectionCollapsed = (section: string) => collapsedSections.has(section);
  
  if (!sidebarOpen) {
    return null;
  }
  
  return (
    <aside className={cn(
      'fixed left-0 top-14 z-40 h-[calc(100vh-3.5rem)] w-64 border-r bg-background',
      'transition-transform duration-300',
      className
    )}>
      <div className="flex h-full flex-col overflow-hidden">
        {/* Navigation */}
        <div className="flex-1 min-h-0 overflow-y-auto px-3 py-4">
            {/* Main Navigation */}
            <nav className="space-y-1">
            <button
              onClick={() => toggleSection('trading')}
              className="flex items-center justify-between w-full px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 hover:text-foreground transition-colors"
            >
              <span>Trading</span>
              {isSectionCollapsed('trading') ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronUp className="h-3 w-3" />
              )}
            </button>
            {!isSectionCollapsed('trading') && (
              <>
                {mainNavItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive 
                      ? 'bg-primary text-primary-foreground' 
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.title}
                  {item.badge && (
                    <span className={cn(
                      'ml-auto text-xs px-2 py-0.5 rounded-full',
                      isActive ? 'bg-primary-foreground/20' : 'bg-muted-foreground/20'
                    )}>
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
              </>
            )}
          </nav>
          
          <Separator className="my-4" />
          
          {/* Analytics Navigation */}
          <nav className="space-y-1">
            <button
              onClick={() => toggleSection('analytics')}
              className="flex items-center justify-between w-full px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 hover:text-foreground transition-colors"
            >
              <span>Analytics</span>
              {isSectionCollapsed('analytics') ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronUp className="h-3 w-3" />
              )}
            </button>
            {!isSectionCollapsed('analytics') && (
              <>
                {analyticsNavItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive 
                      ? 'bg-primary text-primary-foreground' 
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.title}
                </Link>
              );
            })}
              </>
            )}
          </nav>
          
          <Separator className="my-4" />
          
          {/* System Navigation */}
          <nav className="space-y-1">
            <button
              onClick={() => toggleSection('system')}
              className="flex items-center justify-between w-full px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 hover:text-foreground transition-colors"
            >
              <span>System</span>
              {isSectionCollapsed('system') ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronUp className="h-3 w-3" />
              )}
            </button>
            {!isSectionCollapsed('system') && (
              <>
                {systemNavItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive 
                      ? 'bg-primary text-primary-foreground' 
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.title}
                </Link>
              );
            })}
              </>
            )}
          </nav>
          
          <Separator className="my-4" />
          
          {/* Monitoring Navigation */}
          <nav className="space-y-1">
            <button
              onClick={() => toggleSection('monitoring')}
              className="flex items-center justify-between w-full px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 hover:text-foreground transition-colors"
            >
              <span>Monitoring</span>
              {isSectionCollapsed('monitoring') ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronUp className="h-3 w-3" />
              )}
            </button>
            {!isSectionCollapsed('monitoring') && (
              <>
                {monitoringNavItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive 
                      ? 'bg-primary text-primary-foreground' 
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.title}
                </Link>
              );
            })}
              </>
            )}
          </nav>
          
          <Separator className="my-4" />
          
          {/* Management Navigation */}
          <nav className="space-y-1">
            <button
              onClick={() => toggleSection('management')}
              className="flex items-center justify-between w-full px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 hover:text-foreground transition-colors"
            >
              <span>Management</span>
              {isSectionCollapsed('management') ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronUp className="h-3 w-3" />
              )}
            </button>
            {!isSectionCollapsed('management') && (
              <>
                {managementNavItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive 
                      ? 'bg-primary text-primary-foreground' 
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.title}
                </Link>
              );
            })}
              </>
            )}
          </nav>
          
          <Separator className="my-4" />
          
          {/* Tools Navigation */}
          <nav className="space-y-1">
            <button
              onClick={() => toggleSection('tools')}
              className="flex items-center justify-between w-full px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 hover:text-foreground transition-colors"
            >
              <span>Tools</span>
              {isSectionCollapsed('tools') ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronUp className="h-3 w-3" />
              )}
            </button>
            {!isSectionCollapsed('tools') && (
              <>
                {toolsNavItems.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                        isActive 
                          ? 'bg-primary text-primary-foreground' 
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {item.title}
                    </Link>
                  );
                })}
              </>
            )}
          </nav>
        </div>
        
        {/* Bottom Stats */}
        <div className="border-t p-4 space-y-3">
          {/* Quick Stats */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Positions</span>
              <span className="font-medium">{totalPositions}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">P&L (INR)</span>
              <PriceDisplay 
                value={totalPnLINR} 
                currency="INR" 
                colorCode 
                size="sm"
              />
            </div>
          </div>
          
          <Separator />
          
          {/* System Status */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Trading</span>
            <StatusBadge 
              status={tradingAllowed ? 'running' : 'stopped'} 
              label={tradingAllowed ? 'Enabled' : 'Blocked'}
              size="sm"
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Guardian</span>
            <StatusBadge 
              status={guardianStatus?.active || guardianStatus?.running ? 'running' : 'stopped'} 
              size="sm"
            />
          </div>
        </div>
        
        {/* Collapse Button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSidebarOpen(false)}
          className="m-2"
        >
          <ChevronLeft className="h-4 w-4 mr-1" />
          Collapse
        </Button>
      </div>
    </aside>
  );
});

export default Sidebar;
