'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { TrendingUp, Activity, AlertTriangle, CheckCircle, Clock, Play, Square } from 'lucide-react';

interface Symbol {
  name: string;
  enabled: boolean;
  product_id: number;
  mode: string;
  status?: 'active' | 'stale' | 'disabled' | 'not_running';
  grid?: {
    lower: number;
    upper: number;
    step: number;
  };
}

export function SymbolSwitcher() {
  const queryClient = useQueryClient();
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [showSwitchConfirm, setShowSwitchConfirm] = useState(false);
  const [targetSymbol, setTargetSymbol] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Fetch available symbols
  const { data: symbolsData, isLoading } = useQuery({
    queryKey: ['symbols-list'],
    queryFn: async () => {
      const res = await fetch('/api/symbols');
      if (!res.ok) throw new Error('Failed to fetch symbols');
      return res.json() as Promise<{ symbols: Symbol[]; enabled_count: number }>;
    },
    refetchInterval: 10000, // Poll every 10 seconds
  });

  // Start symbol process mutation
  const startSymbolMutation = useMutation({
    mutationFn: async (symbolName: string) => {
      const res = await fetch(`/api/symbols/${symbolName}/process/start`, {
        method: 'POST',
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || `Failed to start ${symbolName}`);
      }
      return res.json();
    },
    onSuccess: (data, symbolName) => {
      setFeedback({
        message: `Successfully started trading ${symbolName}`,
        type: 'success',
      });
      setSelectedSymbol(symbolName);
      queryClient.invalidateQueries({ queryKey: ['symbols-list'] });
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
    onError: (error: Error) => {
      setFeedback({ message: error.message, type: 'error' });
    },
  });

  // Stop symbol process mutation
  const stopSymbolMutation = useMutation({
    mutationFn: async (symbolName: string) => {
      const res = await fetch(`/api/symbols/${symbolName}/process/stop`, {
        method: 'POST',
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || `Failed to stop ${symbolName}`);
      }
      return res.json();
    },
    onSuccess: (data, symbolName) => {
      setFeedback({
        message: `Successfully stopped ${symbolName}`,
        type: 'success',
      });
      queryClient.invalidateQueries({ queryKey: ['symbols-list'] });
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
    onError: (error: Error) => {
      setFeedback({ message: error.message, type: 'error' });
    },
  });

  const handleSymbolChange = (value: string) => {
    setTargetSymbol(value);
    setShowSwitchConfirm(true);
  };

  const confirmSwitch = () => {
    setShowSwitchConfirm(false);
    if (targetSymbol) {
      setFeedback({ message: `Switching to ${targetSymbol}...`, type: 'info' });
      // Stop current if running, then start new
      if (selectedSymbol) {
        stopSymbolMutation.mutate(selectedSymbol);
      }
      startSymbolMutation.mutate(targetSymbol);
    }
  };

  const handleStartSymbol = (symbolName: string) => {
    setFeedback({ message: `Starting ${symbolName}...`, type: 'info' });
    startSymbolMutation.mutate(symbolName);
  };

  const handleStopSymbol = (symbolName: string) => {
    setFeedback({ message: `Stopping ${symbolName}...`, type: 'info' });
    stopSymbolMutation.mutate(symbolName);
  };

  const getStatusIcon = (symbol: Symbol) => {
    switch (symbol.status) {
      case 'active':
        return <Activity className="h-3 w-3 text-green-500 animate-pulse" />;
      case 'stale':
        return <Clock className="h-3 w-3 text-amber-500" />;
      case 'disabled':
        return <AlertTriangle className="h-3 w-3 text-gray-500" />;
      default:
        return <CheckCircle className="h-3 w-3 text-gray-400" />;
    }
  };

  const getStatusBadge = (symbol: Symbol) => {
    if (!symbol.enabled) {
      return <Badge variant="outline" className="text-xs">Disabled</Badge>;
    }
    
    switch (symbol.status) {
      case 'active':
        return <Badge variant="default" className="text-xs bg-green-500">Active</Badge>;
      case 'stale':
        return <Badge variant="outline" className="text-xs text-amber-500">Stale</Badge>;
      default:
        return <Badge variant="outline" className="text-xs">Stopped</Badge>;
    }
  };

  const symbols = symbolsData?.symbols || [];
  const enabledSymbols = symbols.filter(s => s.enabled);
  const activeSymbol = symbols.find(s => s.status === 'active');

  return (
    <>
      <Card className="border-2">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                Symbol Selector
              </CardTitle>
              <CardDescription>Switch trading instruments</CardDescription>
            </div>
            
            <Badge variant="outline" className="gap-1">
              {enabledSymbols.length} of {symbols.length} enabled
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Feedback Alert */}
          {feedback && (
            <Alert variant={feedback.type === 'error' ? 'destructive' : 'default'}>
              <AlertDescription>{feedback.message}</AlertDescription>
            </Alert>
          )}

          {/* Symbol Selector */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Select Symbol</label>
            <Select
              value={selectedSymbol || activeSymbol?.name || ''}
              onValueChange={handleSymbolChange}
              disabled={isLoading}
            >
              <SelectTrigger>
                <SelectValue placeholder="Choose a trading symbol..." />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>Available Symbols</SelectLabel>
                  {symbols.map((symbol) => (
                    <SelectItem
                      key={symbol.name}
                      value={symbol.name}
                      disabled={!symbol.enabled}
                    >
                      <div className="flex items-center justify-between w-full gap-2">
                        <span>{symbol.name}</span>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(symbol)}
                          <span className="text-xs text-muted-foreground">{symbol.mode}</span>
                        </div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>

          {/* Current Active Symbol Info */}
          {activeSymbol && (
            <div className="bg-muted p-3 rounded space-y-2">
              <div className="flex items-center justify-between">
                <div className="font-medium">Currently Trading:</div>
                {getStatusBadge(activeSymbol)}
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <div className="text-muted-foreground">Symbol</div>
                  <div className="font-mono">{activeSymbol.name}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Mode</div>
                  <div className="font-medium">{activeSymbol.mode}</div>
                </div>
                {activeSymbol.grid && (
                  <>
                    <div>
                      <div className="text-muted-foreground">Grid Range</div>
                      <div className="font-mono text-xs">
                        {activeSymbol.grid.lower} - {activeSymbol.grid.upper}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Grid Step</div>
                      <div className="font-mono text-xs">{activeSymbol.grid.step}</div>
                    </div>
                  </>
                )}
              </div>
              
              <div className="flex gap-2 pt-2">
                <Button
                  size="sm"
                  variant="destructive"
                  className="flex-1 gap-1"
                  onClick={() => handleStopSymbol(activeSymbol.name)}
                  disabled={stopSymbolMutation.isPending}
                >
                  <Square className="h-3 w-3" />
                  Stop
                </Button>
              </div>
            </div>
          )}

          {/* Info */}
          <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
            ℹ️ Switching symbols will stop the current bot instance and start trading the selected symbol.
            Make sure to cancel open orders if needed before switching.
          </div>
        </CardContent>
      </Card>

      {/* Switch Confirmation Dialog */}
      <AlertDialog open={showSwitchConfirm} onOpenChange={setShowSwitchConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Switch Trading Symbol?</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              {selectedSymbol && (
                <p>This will stop trading <span className="font-mono font-medium">{selectedSymbol}</span></p>
              )}
              <p>And start trading <span className="font-mono font-medium">{targetSymbol}</span></p>
              <p className="font-medium text-foreground">
                ⚠️ Existing open orders will remain active. Cancel manually if needed.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmSwitch}>
              Yes, Switch Symbol
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
