/**
 * AppShell Component
 * 
 * Client-side wrapper for the main application layout.
 * Wraps children with providers and layout components.
 */

'use client';

import { QueryProvider, ThemeProvider, FocusModeProvider } from "@/components/providers";
import { Header, Sidebar, BrainPanel, MobileNav } from "@/components/layout";
import { ShortcutsHelp, CommandPalette } from "@/components/common";
import { useAppStore, useUIStore } from "@/stores";
import { useKeyboardShortcuts } from "@/hooks";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { sidebarOpen, brainPanelOpen } = useAppStore();
  const { focusMode } = useUIStore();
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  
  // Initialize keyboard shortcuts
  useKeyboardShortcuts({
    enabled: true,
    enableCommandMode: true,
    onCommandModeOpen: () => setCommandPaletteOpen(true),
  });
  
  // In zen mode, hide sidebar by default
  const showSidebar = focusMode === 'zen' ? false : sidebarOpen;
  const showBrainPanel = focusMode === 'zen' ? false : brainPanelOpen;
  
  return (
    <QueryProvider>
      <ThemeProvider>
        <FocusModeProvider>
          <div className="min-h-screen bg-background">
            <Header />
            {/* Desktop sidebar - hidden on mobile */}
            <div className="hidden md:block">
              {showSidebar && <Sidebar />}
            </div>
            {showBrainPanel && <BrainPanel />}
            <main className={cn(
              "transition-all duration-300 pt-14",
              "pb-20 md:pb-0", // Bottom padding for mobile nav
              showSidebar && "md:pl-64",
              showBrainPanel && "md:pr-80"
            )}>
              <div className="container mx-auto p-4 md:p-6">
                {children}
              </div>
            </main>
            
            {/* Mobile bottom navigation */}
            <MobileNav />
            
            {/* Global dialogs */}
            <ShortcutsHelp />
            <CommandPalette 
              open={commandPaletteOpen} 
              onOpenChange={setCommandPaletteOpen} 
            />
          </div>
        </FocusModeProvider>
      </ThemeProvider>
    </QueryProvider>
  );
}

export default AppShell;
