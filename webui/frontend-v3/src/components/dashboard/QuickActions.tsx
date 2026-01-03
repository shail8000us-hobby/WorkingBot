/**
 * QuickActions Component
 * 
 * Critical action buttons with safety gates:
 * - Pause/Resume Trading
 * - Emergency Kill All
 * - Clear Emergency Flag
 */

'use client';

import { memo, useState, useMemo } from 'react';
import { 
  Pause, 
  Play, 
  AlertOctagon, 
  ShieldOff,
  Loader2,
  CheckCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { SafetyCheck, type SafetyCheckItem } from '@/components/common';
import { 
  useBotStatus, 
  useStartBot, 
  useStopBot,
  useEmergencyKillAll,
  useClearEmergencyFlag,
  useEmergencyFlag,
  useGuardianStatus,
  usePositions,
} from '@/hooks';
import { useAppStore } from '@/stores';
import { cn } from '@/lib/utils';

interface QuickActionsProps {
  className?: string;
}

export const QuickActions = memo(function QuickActions({ className }: QuickActionsProps) {
  const { confirmDangerousActions } = useAppStore();
  const [showEmergencyDialog, setShowEmergencyDialog] = useState(false);
  
  // Data fetching
  const { data: botStatus } = useBotStatus();
  const { data: emergencyFlag } = useEmergencyFlag();
  const { data: guardianStatus } = useGuardianStatus();
  const { data: positionsData } = usePositions();
  
  // Mutations
  const startBot = useStartBot();
  const stopBot = useStopBot();
  const emergencyKill = useEmergencyKillAll();
  const clearEmergency = useClearEmergencyFlag();
  
  const isRunning = botStatus?.running ?? false;
  const hasEmergency = emergencyFlag?.exists ?? false;
  const positionCount = positionsData?.positions?.length ?? 0;
  
  // Safety checks for emergency kill
  const emergencySafetyChecks: SafetyCheckItem[] = useMemo(() => [
    {
      id: 'positions-open',
      label: `${positionCount} open position(s) will be affected`,
      passed: true, // Always show as info, not blocker
      severity: 'warning',
      details: positionCount > 0 ? 'All positions will remain open but no new orders will be placed' : 'No positions to affect',
    },
    {
      id: 'bot-running',
      label: isRunning ? 'Bot is currently running' : 'Bot is already stopped',
      passed: true,
      severity: 'warning',
    },
    {
      id: 'guardian-active',
      label: guardianStatus?.running ? 'Guardian is active' : 'Guardian is not active',
      passed: true,
    },
  ], [positionCount, isRunning, guardianStatus]);
  
  // Handle pause/resume
  const handleToggleBot = async () => {
    if (isRunning) {
      await stopBot.mutateAsync();
    } else {
      await startBot.mutateAsync();
    }
  };
  
  // Handle emergency kill
  const handleEmergencyKill = async () => {
    await emergencyKill.mutateAsync({});
    setShowEmergencyDialog(false);
  };
  
  // Handle clear emergency
  const handleClearEmergency = async () => {
    await clearEmergency.mutateAsync();
  };
  
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle>Quick Actions</CardTitle>
        <CardDescription>Control your trading bot</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Pause/Resume Button */}
        <Button
          variant={isRunning ? 'outline' : 'default'}
          className={cn(
            'w-full justify-start gap-2',
            isRunning && 'border-yellow-500 text-yellow-600 hover:bg-yellow-50 dark:hover:bg-yellow-950'
          )}
          onClick={handleToggleBot}
          disabled={startBot.isPending || stopBot.isPending}
        >
          {startBot.isPending || stopBot.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : isRunning ? (
            <Pause className="h-4 w-4" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          {isRunning ? 'Pause Trading' : 'Resume Trading'}
        </Button>
        
        {/* Emergency Kill Button */}
        <AlertDialog open={showEmergencyDialog} onOpenChange={setShowEmergencyDialog}>
          <AlertDialogTrigger asChild>
            <Button
              variant="destructive"
              className="w-full justify-start gap-2"
              disabled={hasEmergency}
            >
              <AlertOctagon className="h-4 w-4" />
              Emergency Kill All
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent className="max-w-lg">
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2 text-destructive">
                <AlertOctagon className="h-5 w-5" />
                Emergency Kill All
              </AlertDialogTitle>
              <AlertDialogDescription>
                This will immediately stop the bot and cancel all pending orders.
                Open positions will NOT be closed automatically.
              </AlertDialogDescription>
            </AlertDialogHeader>
            
            {/* Safety Checks Display */}
            <div className="py-4">
              <SafetyCheck 
                checks={emergencySafetyChecks}
                title="What will happen"
                actionName="Emergency Kill"
              />
            </div>
            
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleEmergencyKill}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                disabled={emergencyKill.isPending}
              >
                {emergencyKill.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <AlertOctagon className="h-4 w-4 mr-2" />
                )}
                Confirm Emergency Kill
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        
        {/* Clear Emergency Flag (only shown when emergency is active) */}
        {hasEmergency && (
          <Button
            variant="outline"
            className="w-full justify-start gap-2 border-green-500 text-green-600 hover:bg-green-50 dark:hover:bg-green-950"
            onClick={handleClearEmergency}
            disabled={clearEmergency.isPending}
          >
            {clearEmergency.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ShieldOff className="h-4 w-4" />
            )}
            Clear Emergency Flag
          </Button>
        )}
        
        {/* Status indicator */}
        <div className="pt-2 border-t">
          <div className="flex items-center gap-2 text-sm">
            <div className={cn(
              'h-2 w-2 rounded-full',
              isRunning ? 'bg-green-500' : 'bg-gray-400'
            )} />
            <span className="text-muted-foreground">
              Bot is {isRunning ? 'running' : 'stopped'}
            </span>
          </div>
          {hasEmergency && (
            <div className="flex items-center gap-2 text-sm mt-1">
              <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-red-500">Emergency mode active</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
});

export default QuickActions;
