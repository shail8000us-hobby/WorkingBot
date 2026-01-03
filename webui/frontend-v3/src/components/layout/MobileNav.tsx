/**
 * Mobile Bottom Navigation
 * 
 * Touch-friendly navigation bar for mobile devices.
 * Replaces sidebar on small screens.
 */

'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { 
  LayoutDashboard, 
  Activity, 
  ShoppingCart, 
  TrendingUp,
  Bot,
  Settings,
} from 'lucide-react';

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  badge?: number;
}

const navItems: NavItem[] = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/grid', label: 'Grid', icon: Activity },
  { href: '/orders', label: 'Orders', icon: ShoppingCart },
  { href: '/positions', label: 'Positions', icon: TrendingUp },
  { href: '/instances', label: 'Bots', icon: Bot },
];

interface MobileNavProps {
  className?: string;
}

export function MobileNav({ className }: MobileNavProps) {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <nav
      className={cn(
        'fixed bottom-0 left-0 right-0 z-50 md:hidden',
        'bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80',
        'border-t border-border',
        'safe-area-inset-bottom',
        className
      )}
    >
      <div className="flex items-center justify-around h-16 px-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex flex-col items-center justify-center',
                'min-w-[60px] py-1.5 px-2 rounded-lg',
                'transition-colors touch-manipulation',
                active
                  ? 'text-primary bg-primary/10'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted'
              )}
            >
              <div className="relative">
                <Icon className="h-5 w-5" />
                {item.badge && item.badge > 0 && (
                  <span className="absolute -top-1 -right-1 h-4 min-w-[16px] flex items-center justify-center text-[10px] font-medium bg-destructive text-destructive-foreground rounded-full px-1">
                    {item.badge > 99 ? '99+' : item.badge}
                  </span>
                )}
              </div>
              <span className={cn(
                'text-[10px] mt-1 font-medium',
                active && 'text-primary'
              )}>
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export default MobileNav;
