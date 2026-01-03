'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Terminal, 
  Activity, 
  Cpu, 
  HardDrive, 
  RefreshCw, 
  PlayCircle, 
  StopCircle, 
  RotateCw, 
  FileText, 
  Trash2, 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  Shield, 
  Heart, 
  TrendingUp, 
  Info, 
  Layers 
} from 'lucide-react';

// ===== TypeScript Interfaces =====
interface PM2Process {
  name: string;
  status: 'online' | 'stopped' | 'errored' | 'stopping';
  pid: number | null;
  cpu: number;
  memory: number;
  uptime: number | null;
  restarts: number;
}

interface PM2Status {
  total: number;
  online: number;
  stopped: number;
  errored: number;
  processes: PM2Process[];
  summary: {
    total_cpu: number;
    total_memory: number;
    total_restarts: number;
  };
}

interface PM2Enabled {
  enabled: boolean;
}

interface PM2Logs {
  success: boolean;
  logs: {
    out: string[];
    err: string[];
  };
}

interface ActionResult {
  success: boolean;
  message?: string;
}

interface SymbolGroup {
  [symbol: string]: PM2Process[];
}

interface GroupedProcesses {
  symbols: SymbolGroup;
  system: PM2Process[];
}

interface Notification {
  message: string;
  type: 'success' | 'error';
}

// API URL constant
const API_URL = typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5555')
  : 'http://localhost:5555';

// ===== PM2Panel Component =====
export default function PM2Panel() {
  const [selectedProcess, setSelectedProcess] = useState<PM2Process | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logs, setLogs] = useState<{ out: string[]; err: string[] }>({ out: [], err: [] });
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'symbol' | 'live' | 'demo' | 'all'>('symbol');
  const [notification, setNotification] = useState<Notification | null>(null);

  // ===== API Queries =====
  
  // Check if PM2 is enabled
  const { data: pm2EnabledData, isLoading: enabledLoading, error: enabledError } = useQuery<PM2Enabled>({
    queryKey: ['pm2-enabled'],
    queryFn: async () => {
      try {
        const res = await fetch(`${API_URL}/api/pm2/enabled`);
        if (!res.ok) {
          // If endpoint doesn't exist or returns error, assume PM2 is not enabled
          console.warn('PM2 enabled check failed:', res.status, res.statusText);
          return { enabled: false };
        }
        const data = await res.json();
        // API returns { enabled: true, available: true, config_file: "...", version: "..." }
        // Log for debugging
        console.log('PM2 API Response:', data);
        // Return the enabled field - ensure it's a boolean
        const enabled = data.enabled === true || data.enabled === 'true';
        console.log('PM2 Enabled:', enabled);
        return { enabled };
      } catch (error) {
        console.error('Error checking PM2 status:', error);
        return { enabled: false };
      }
    },
    refetchInterval: 10000,
    retry: false, // Don't retry on error - just assume PM2 is not enabled
  });

  // Get PM2 process status
  const { data: pm2Status, isLoading: statusLoading, refetch } = useQuery<PM2Status>({
    queryKey: ['pm2-status'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/pm2/status`);
      if (!res.ok) throw new Error('Failed to fetch PM2 status');
      return res.json();
    },
    refetchInterval: 5000,
    enabled: pm2EnabledData?.enabled === true,
  });

  const isLoading = enabledLoading || statusLoading;
  // Check if PM2 is enabled - API returns { enabled: true, available: true, ... }
  const pm2Enabled = pm2EnabledData?.enabled === true;
  
  // Debug logging
  if (typeof window !== 'undefined') {
    if (pm2EnabledData) {
      console.log('[PM2Panel] PM2 Enabled Data:', pm2EnabledData, 'pm2Enabled:', pm2Enabled);
    }
    if (enabledError) {
      console.error('[PM2Panel] Error loading PM2 status:', enabledError);
    }
  }

  // ===== Helper Functions =====

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const formatUptime = (milliseconds: number | null): string => {
    if (!milliseconds) return 'N/A';
    const now = Date.now();
    const uptime = now - milliseconds;
    const seconds = Math.floor(uptime / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  };

  const extractSymbolFromProcess = (processName: string): string | null => {
    const symbolMatch = processName.match(/-(BTCUSD|ETHUSD|[A-Z]{6})(?:-|$)/i);
    if (symbolMatch) return symbolMatch[1].toUpperCase();
    if (processName.includes('-live') || processName.includes('-demo')) return null;
    return null; // System process
  };

  const groupProcessesBySymbol = (): GroupedProcesses => {
    if (!pm2Status?.processes) return { symbols: {}, system: [] };

    const groups: GroupedProcesses = { symbols: {}, system: [] };

    pm2Status.processes.forEach((process) => {
      const symbol = extractSymbolFromProcess(process.name);
      if (symbol) {
        if (!groups.symbols[symbol]) groups.symbols[symbol] = [];
        groups.symbols[symbol].push(process);
      } else {
        groups.system.push(process);
      }
    });

    return groups;
  };

  const getProcessDisplayName = (name: string): string => {
    const displayNames: Record<string, string> = {
      'gridbot-live': 'Trading Bot (Real Money)',
      'gridbot-demo': 'Trading Bot (Demo)',
      'guardian-live': 'Guardian Monitor (Live)',
      'guardian-demo': 'Guardian Monitor (Demo)',
      'heartbeat-monitor': 'Heartbeat Monitor',
    };
    return displayNames[name] || name;
  };

  const getProcessIcon = (name: string) => {
    if (name.includes('gridbot')) return <TrendingUp size={20} className="text-blue-500" />;
    if (name.includes('guardian')) return <Shield size={20} className="text-green-500" />;
    if (name.includes('heartbeat')) return <Heart size={20} className="text-red-500" />;
    return <Terminal size={20} className="text-gray-500" />;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'stopped':
        return <XCircle className="w-5 h-5 text-gray-400" />;
      case 'errored':
      case 'stopping':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <AlertCircle className="w-5 h-5 text-yellow-500" />;
    }
  };

  const getStatusBadgeVariant = (status: string): 'default' | 'secondary' | 'destructive' => {
    switch (status) {
      case 'online':
        return 'default';
      case 'stopped':
        return 'secondary';
      case 'errored':
      case 'stopping':
        return 'destructive';
      default:
        return 'secondary';
    }
  };

  const getFilteredProcesses = (): PM2Process[] => {
    if (!pm2Status?.processes) return [];

    switch (activeTab) {
      case 'live':
        return pm2Status.processes.filter(
          (p) =>
            p.name === 'gridbot-live' ||
            p.name === 'guardian-live' ||
            p.name === 'heartbeat-monitor'
        );
      case 'demo':
        return pm2Status.processes.filter(
          (p) =>
            p.name === 'gridbot-demo' ||
            p.name === 'guardian-demo' ||
            p.name === 'heartbeat-monitor'
        );
      case 'all':
      default:
        return pm2Status.processes;
    }
  };

  // ===== Process Control Actions =====

  const handleStart = async (name: string) => {
    setActionInProgress(`start-${name}`);
    try {
      const res = await fetch(`${API_URL}/api/pm2/${name}/start`, { method: 'POST' });
      const result: ActionResult = await res.json();
      if (result.success) {
        showNotification(`${name} started successfully`, 'success');
        refetch();
      } else {
        showNotification(result.message || 'Failed to start process', 'error');
      }
    } catch (err: any) {
      showNotification(err.message || 'Error starting process', 'error');
    }
    setActionInProgress(null);
  };

  const handleStop = async (name: string) => {
    setActionInProgress(`stop-${name}`);
    try {
      const res = await fetch(`${API_URL}/api/pm2/${name}/stop`, { method: 'POST' });
      const result: ActionResult = await res.json();
      if (result.success) {
        showNotification(`${name} stopped successfully (graceful shutdown)`, 'success');
        refetch();
      } else {
        showNotification(result.message || 'Failed to stop process', 'error');
      }
    } catch (err: any) {
      showNotification(err.message || 'Error stopping process', 'error');
    }
    setActionInProgress(null);
  };

  const handleRestart = async (name: string) => {
    setActionInProgress(`restart-${name}`);
    try {
      const res = await fetch(`${API_URL}/api/pm2/${name}/restart`, { method: 'POST' });
      const result: ActionResult = await res.json();
      if (result.success) {
        showNotification(`${name} restarted successfully`, 'success');
        refetch();
      } else {
        showNotification(result.message || 'Failed to restart process', 'error');
      }
    } catch (err: any) {
      showNotification(err.message || 'Error restarting process', 'error');
    }
    setActionInProgress(null);
  };

  const handleViewLogs = async (process: PM2Process) => {
    setSelectedProcess(process);
    setShowLogs(true);
    setLogsLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/pm2/${process.name}/logs?lines=100`);
      const result: PM2Logs = await res.json();
      if (result.success) {
        setLogs(result.logs);
      } else {
        setLogs({ out: [], err: ['Failed to load logs'] });
      }
    } catch (err: any) {
      setLogs({ out: [], err: [`Error: ${err.message}`] });
    }
    setLogsLoading(false);
  };

  const handleFlushLogs = async () => {
    if (!window.confirm('Are you sure you want to clear all PM2 logs?')) return;

    setActionInProgress('flush-logs');
    try {
      const res = await fetch(`${API_URL}/api/pm2/flush-logs`, { method: 'POST' });
      const result: ActionResult = await res.json();
      if (result.success) {
        showNotification('All PM2 logs cleared', 'success');
      } else {
        showNotification(result.message || 'Failed to flush logs', 'error');
      }
    } catch (err: any) {
      showNotification(err.message || 'Error flushing logs', 'error');
    }
    setActionInProgress(null);
  };

  // Symbol-specific controls
  const handleStartSymbol = async (symbol: string) => {
    setActionInProgress(`start-${symbol}`);
    try {
      const res = await fetch(`/api/symbols/${symbol}/process/start`, { method: 'POST' });
      const result: ActionResult = await res.json();
      if (result.success) {
        showNotification(`${symbol} trading processes started`, 'success');
        refetch();
      } else {
        showNotification(result.message || `Failed to start ${symbol}`, 'error');
      }
    } catch (err: any) {
      showNotification(err.message || `Error starting ${symbol}`, 'error');
    }
    setActionInProgress(null);
  };

  const handleStopSymbol = async (symbol: string) => {
    setActionInProgress(`stop-${symbol}`);
    try {
      const res = await fetch(`/api/symbols/${symbol}/process/stop`, { method: 'POST' });
      const result: ActionResult = await res.json();
      if (result.success) {
        showNotification(`${symbol} trading processes stopped`, 'success');
        refetch();
      } else {
        showNotification(result.message || `Failed to stop ${symbol}`, 'error');
      }
    } catch (err: any) {
      showNotification(err.message || `Error stopping ${symbol}`, 'error');
    }
    setActionInProgress(null);
  };

  const handleStartAllSymbols = async () => {
    setActionInProgress('start-all');
    try {
      const res = await fetch('/api/symbols/all/start', { method: 'POST' });
      const result: ActionResult = await res.json();
      if (result.success) {
        showNotification('All enabled symbols started', 'success');
        refetch();
      } else {
        showNotification(result.message || 'Failed to start all symbols', 'error');
      }
    } catch (err: any) {
      showNotification(err.message || 'Error starting all symbols', 'error');
    }
    setActionInProgress(null);
  };

  const handleStopAllSymbols = async () => {
    setActionInProgress('stop-all');
    try {
      const res = await fetch('/api/symbols/all/stop', { method: 'POST' });
      const result: ActionResult = await res.json();
      if (result.success) {
        showNotification('All symbol trading stopped', 'success');
        refetch();
      } else {
        showNotification(result.message || 'Failed to stop all symbols', 'error');
      }
    } catch (err: any) {
      showNotification(err.message || 'Error stopping all symbols', 'error');
    }
    setActionInProgress(null);
  };

  // ===== Render States =====

  // PM2 not enabled state - show info message but don't block the UI
  if (!pm2Enabled && !isLoading && !enabledError) {
    return (
      <div className="space-y-4">
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-3">
              <p className="font-semibold">PM2 Process Manager Not Enabled</p>
              <p className="text-sm text-muted-foreground">
                PM2 process manager is not currently enabled for this system. This panel requires PM2 to function.
              </p>
              <div className="space-y-2 text-sm">
                <p className="font-medium">To enable PM2:</p>
                <ol className="list-decimal list-inside space-y-1 text-muted-foreground ml-2">
                  <li>
                    Run: <code className="bg-muted px-2 py-1 rounded text-xs">./toggle_pm2.sh enable</code>
                  </li>
                  <li>
                    Restart WebUI backend:{' '}
                    <code className="bg-muted px-2 py-1 rounded text-xs">
                      launchctl restart com.gridbot.webui.enhanced
                    </code>
                  </li>
                  <li>Refresh this page</li>
                </ol>
              </div>
            </div>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <Card className="w-full">
        <CardContent className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-2">
            <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Loading PM2 status...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const groupedProcesses = groupProcessesBySymbol();
  const filteredProcesses = getFilteredProcesses();

  // ===== Main Render =====
  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="w-6 h-6" />
              <CardTitle>PM2 Process Manager</CardTitle>
            </div>
            <Button onClick={() => refetch()} variant="outline" size="sm">
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
          <CardDescription>Multi-symbol process management and monitoring</CardDescription>
        </CardHeader>
      </Card>

      {/* Notification */}
      {notification && (
        <Alert variant={notification.type === 'error' ? 'destructive' : 'default'}>
          <div className="flex items-center gap-2">
            {notification.type === 'success' ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              <AlertCircle className="w-4 h-4" />
            )}
            <AlertDescription>{notification.message}</AlertDescription>
          </div>
        </Alert>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as any)}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="symbol" className="flex items-center gap-2">
            <Layers className="w-4 h-4" />
            By Symbol
            <Badge variant="secondary" className="ml-1">
              {Object.keys(groupedProcesses.symbols).length}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="live" className="flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Live
            <Badge variant="secondary" className="ml-1">
              {
                pm2Status?.processes?.filter(
                  (p) =>
                    p.name === 'gridbot-live' ||
                    p.name === 'guardian-live' ||
                    p.name === 'heartbeat-monitor'
                ).length || 0
              }
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="demo" className="flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Demo
            <Badge variant="secondary" className="ml-1">
              {
                pm2Status?.processes?.filter(
                  (p) =>
                    p.name === 'gridbot-demo' ||
                    p.name === 'guardian-demo' ||
                    p.name === 'heartbeat-monitor'
                ).length || 0
              }
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="all" className="flex items-center gap-2">
            <Terminal className="w-4 h-4" />
            All
            <Badge variant="secondary" className="ml-1">
              {pm2Status?.total || 0}
            </Badge>
          </TabsTrigger>
        </TabsList>

        {/* Symbol-Grouped View */}
        <TabsContent value="symbol" className="space-y-4">
          {/* Start/Stop All Controls */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Bulk Controls</CardTitle>
            </CardHeader>
            <CardContent className="flex gap-2">
              <Button
                onClick={handleStartAllSymbols}
                disabled={actionInProgress === 'start-all'}
                variant="default"
              >
                <PlayCircle className="w-4 h-4 mr-2" />
                {actionInProgress === 'start-all' ? 'Starting...' : 'Start All Symbols'}
              </Button>
              <Button
                onClick={handleStopAllSymbols}
                disabled={actionInProgress === 'stop-all'}
                variant="destructive"
              >
                <StopCircle className="w-4 h-4 mr-2" />
                {actionInProgress === 'stop-all' ? 'Stopping...' : 'Stop All Symbols'}
              </Button>
            </CardContent>
          </Card>

          {/* Symbol Groups */}
          <div className="grid gap-4">
            {Object.entries(groupedProcesses.symbols).map(([symbol, processes]) => {
              const onlineCount = processes.filter((p) => p.status === 'online').length;
              const isAllOnline = onlineCount === processes.length && processes.length > 0;
              const isAllStopped = onlineCount === 0;

              return (
                <Card key={symbol}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-base font-bold">
                          {symbol}
                        </Badge>
                        <span className="text-sm text-muted-foreground">
                          {onlineCount}/{processes.length} online
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          onClick={() => handleStartSymbol(symbol)}
                          disabled={isAllOnline || actionInProgress === `start-${symbol}`}
                          size="sm"
                          variant="default"
                        >
                          <PlayCircle className="w-3 h-3 mr-1" />
                          {actionInProgress === `start-${symbol}` ? '...' : 'Start'}
                        </Button>
                        <Button
                          onClick={() => handleStopSymbol(symbol)}
                          disabled={isAllStopped || actionInProgress === `stop-${symbol}`}
                          size="sm"
                          variant="destructive"
                        >
                          <StopCircle className="w-3 h-3 mr-1" />
                          {actionInProgress === `stop-${symbol}` ? '...' : 'Stop'}
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {processes.map((process) => (
                        <div
                          key={process.name}
                          className="flex items-center justify-between p-3 border rounded-lg"
                        >
                          <div className="flex items-center gap-2">
                            {getProcessIcon(process.name)}
                            <div>
                              <div className="font-medium text-sm">
                                {process.name.includes('gridbot') ? 'Trading' : 'Guardian'}
                              </div>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>CPU: {process.cpu?.toFixed(0) || 0}%</span>
                                <span>Mem: {process.memory?.toFixed(0) || 0}MB</span>
                              </div>
                            </div>
                          </div>
                          {getStatusIcon(process.status)}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              );
            })}

            {/* System Processes Group */}
            {groupedProcesses.system.length > 0 && (
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-base font-bold">
                      SYSTEM
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {groupedProcesses.system.filter((p) => p.status === 'online').length}/
                      {groupedProcesses.system.length} online
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {groupedProcesses.system.map((process) => (
                      <div
                        key={process.name}
                        className="flex items-center justify-between p-3 border rounded-lg"
                      >
                        <div className="flex items-center gap-2">
                          {getProcessIcon(process.name)}
                          <div>
                            <div className="font-medium text-sm">
                              {getProcessDisplayName(process.name)}
                            </div>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span>CPU: {process.cpu?.toFixed(0) || 0}%</span>
                              <span>Mem: {process.memory?.toFixed(0) || 0}MB</span>
                            </div>
                          </div>
                        </div>
                        {getStatusIcon(process.status)}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* Live/Demo/All Tabs - Summary Statistics */}
        {(activeTab === 'live' || activeTab === 'demo' || activeTab === 'all') && (
          <>
            <TabsContent value={activeTab} className="space-y-4">
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-5 h-5 text-green-500" />
                      <div>
                        <div className="text-2xl font-bold">{pm2Status?.online || 0}</div>
                        <div className="text-xs text-muted-foreground">Online</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2">
                      <XCircle className="w-5 h-5 text-gray-400" />
                      <div>
                        <div className="text-2xl font-bold">{pm2Status?.stopped || 0}</div>
                        <div className="text-xs text-muted-foreground">Stopped</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="w-5 h-5 text-red-500" />
                      <div>
                        <div className="text-2xl font-bold">{pm2Status?.errored || 0}</div>
                        <div className="text-xs text-muted-foreground">Errored</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-5 h-5 text-blue-500" />
                      <div>
                        <div className="text-2xl font-bold">
                          {pm2Status?.summary?.total_cpu?.toFixed(1) || 0}%
                        </div>
                        <div className="text-xs text-muted-foreground">Total CPU</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2">
                      <HardDrive className="w-5 h-5 text-purple-500" />
                      <div>
                        <div className="text-2xl font-bold">
                          {pm2Status?.summary?.total_memory?.toFixed(0) || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">Total MB</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2">
                      <RotateCw className="w-5 h-5 text-orange-500" />
                      <div>
                        <div className="text-2xl font-bold">
                          {pm2Status?.summary?.total_restarts || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">Restarts</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Process List Table */}
              <Card>
                <CardHeader>
                  <CardTitle>Processes</CardTitle>
                </CardHeader>
                <CardContent>
                  {filteredProcesses.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                      <AlertCircle className="w-12 h-12 text-muted-foreground mb-4" />
                      <h3 className="font-semibold mb-2">No Processes Found</h3>
                      <p className="text-sm text-muted-foreground">
                        {activeTab === 'live' && 'No live trading processes are currently running.'}
                        {activeTab === 'demo' && 'No demo trading processes are currently running.'}
                        {activeTab === 'all' && 'No PM2 processes found.'}
                      </p>
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Process</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>PID</TableHead>
                          <TableHead>CPU</TableHead>
                          <TableHead>Memory</TableHead>
                          <TableHead>Uptime</TableHead>
                          <TableHead>Restarts</TableHead>
                          <TableHead>Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredProcesses.map((process) => (
                          <TableRow key={process.name}>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                {getProcessIcon(process.name)}
                                <div>
                                  <div className="font-medium">
                                    {getProcessDisplayName(process.name)}
                                  </div>
                                  <div className="text-xs text-muted-foreground">
                                    {process.name}
                                  </div>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant={getStatusBadgeVariant(process.status)}>
                                {process.status.toUpperCase()}
                              </Badge>
                            </TableCell>
                            <TableCell>{process.pid || 'N/A'}</TableCell>
                            <TableCell>{process.cpu?.toFixed(1) || 0}%</TableCell>
                            <TableCell>{process.memory?.toFixed(1) || 0} MB</TableCell>
                            <TableCell>{formatUptime(process.uptime)}</TableCell>
                            <TableCell>
                              <span className={process.restarts > 0 ? 'text-orange-500' : ''}>
                                {process.restarts}
                              </span>
                            </TableCell>
                            <TableCell>
                              {process.name.includes('guardian') ? (
                                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                  <Info className="w-3 h-3" />
                                  LaunchAgent
                                </div>
                              ) : (
                                <div className="flex gap-1">
                                  <Button
                                    onClick={() => handleStart(process.name)}
                                    disabled={
                                      process.status === 'online' ||
                                      actionInProgress === `start-${process.name}`
                                    }
                                    size="sm"
                                    variant="outline"
                                  >
                                    <PlayCircle className="w-3 h-3" />
                                  </Button>
                                  <Button
                                    onClick={() => handleStop(process.name)}
                                    disabled={
                                      process.status !== 'online' ||
                                      actionInProgress === `stop-${process.name}`
                                    }
                                    size="sm"
                                    variant="outline"
                                  >
                                    <StopCircle className="w-3 h-3" />
                                  </Button>
                                  <Button
                                    onClick={() => handleRestart(process.name)}
                                    disabled={actionInProgress === `restart-${process.name}`}
                                    size="sm"
                                    variant="outline"
                                  >
                                    <RotateCw className="w-3 h-3" />
                                  </Button>
                                  <Button
                                    onClick={() => handleViewLogs(process)}
                                    size="sm"
                                    variant="outline"
                                  >
                                    <FileText className="w-3 h-3" />
                                  </Button>
                                </div>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              {/* Quick Control Actions */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Quick Controls</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  <Button
                    onClick={() => handleStart('gridbot-live')}
                    disabled={
                      actionInProgress === 'start-gridbot-live' ||
                      pm2Status?.processes?.find((p) => p.name === 'gridbot-live')?.status ===
                        'online'
                    }
                    variant="default"
                  >
                    <PlayCircle className="w-4 h-4 mr-2" />
                    {actionInProgress === 'start-gridbot-live' ? 'Starting...' : 'Start Trading Bot'}
                  </Button>

                  <Button
                    onClick={() => handleStop('gridbot-live')}
                    disabled={
                      actionInProgress === 'stop-gridbot-live' ||
                      pm2Status?.processes?.find((p) => p.name === 'gridbot-live')?.status !==
                        'online'
                    }
                    variant="destructive"
                  >
                    <StopCircle className="w-4 h-4 mr-2" />
                    {actionInProgress === 'stop-gridbot-live' ? 'Stopping...' : 'Stop Trading Bot'}
                  </Button>

                  <Button
                    onClick={() => handleRestart('heartbeat-monitor')}
                    disabled={actionInProgress === 'restart-heartbeat-monitor'}
                    variant="outline"
                  >
                    <RotateCw className="w-4 h-4 mr-2" />
                    {actionInProgress === 'restart-heartbeat-monitor'
                      ? 'Restarting...'
                      : 'Restart Heartbeat'}
                  </Button>

                  <Button
                    onClick={handleFlushLogs}
                    disabled={actionInProgress === 'flush-logs'}
                    variant="outline"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    {actionInProgress === 'flush-logs' ? 'Flushing...' : 'Flush Logs'}
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>
          </>
        )}
      </Tabs>

      {/* Logs Modal */}
      <Dialog open={showLogs} onOpenChange={setShowLogs}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Logs: {selectedProcess?.name}
            </DialogTitle>
            <DialogDescription>Process output and error logs</DialogDescription>
          </DialogHeader>

          {logsLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">Loading logs...</span>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Standard Output */}
              <div>
                <h4 className="font-semibold mb-2">Standard Output</h4>
                <div className="bg-muted p-4 rounded-lg max-h-64 overflow-y-auto font-mono text-xs">
                  {logs.out && logs.out.length > 0 ? (
                    logs.out.map((line, idx) => (
                      <div key={idx} className="whitespace-pre-wrap">
                        {line}
                      </div>
                    ))
                  ) : (
                    <div className="text-muted-foreground">No output logs</div>
                  )}
                </div>
              </div>

              {/* Error Output */}
              <div>
                <h4 className="font-semibold mb-2">Error Output</h4>
                <div className="bg-red-50 dark:bg-red-950 p-4 rounded-lg max-h-64 overflow-y-auto font-mono text-xs">
                  {logs.err && logs.err.length > 0 ? (
                    logs.err.map((line, idx) => (
                      <div key={idx} className="whitespace-pre-wrap text-red-600 dark:text-red-400">
                        {line}
                      </div>
                    ))
                  ) : (
                    <div className="text-muted-foreground">No error logs</div>
                  )}
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              onClick={() => selectedProcess && handleViewLogs(selectedProcess)}
              variant="outline"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Reload Logs
            </Button>
            <Button onClick={() => setShowLogs(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
