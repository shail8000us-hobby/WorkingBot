'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Clock, Plus, Trash2, Play, Pause, CheckCircle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface ScheduledTask {
  id: string;
  name: string;
  action: 'start_bot' | 'stop_bot' | 'backup' | 'clear_cache';
  schedule: string;
  enabled: boolean;
  last_run?: string;
  next_run: string;
}

interface SchedulerResponse {
  data: { tasks: ScheduledTask[] };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchScheduledTasks(): Promise<SchedulerResponse> {
  const response = await fetch('http://localhost:5557/api/scheduler/tasks');
  if (!response.ok) {
    throw new Error('Failed to fetch scheduled tasks');
  }
  return response.json();
}

async function toggleTask(taskId: string, enabled: boolean) {
  const response = await fetch(`http://localhost:5557/api/scheduler/tasks/${taskId}/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  return response.json();
}

export function SchedulerPanel() {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['scheduled-tasks'],
    queryFn: fetchScheduledTasks,
    refetchInterval: 30000,
  });

  const handleToggle = async (taskId: string, enabled: boolean) => {
    try {
      const result = await toggleTask(taskId, enabled);
      if (result.success) {
        showNotification(`Task ${enabled ? 'enabled' : 'disabled'} successfully`, 'success');
        refetch();
      } else {
        showNotification(result.error || 'Failed to toggle task', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error toggling task', 'error');
    }
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const getActionLabel = (action: string) => {
    switch (action) {
      case 'start_bot':
        return 'Start Bot';
      case 'stop_bot':
        return 'Stop Bot';
      case 'backup':
        return 'Create Backup';
      case 'clear_cache':
        return 'Clear Cache';
      default:
        return action;
    }
  };

  const getActionColor = (action: string) => {
    switch (action) {
      case 'start_bot':
        return 'bg-green-500';
      case 'stop_bot':
        return 'bg-red-500';
      case 'backup':
        return 'bg-blue-500';
      default:
        return 'bg-gray-500';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Task Scheduler
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading scheduled tasks...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Task Scheduler</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load scheduled tasks'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const tasks = data?.data?.tasks || [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Task Scheduler
          </CardTitle>
          <Button size="sm" onClick={() => setShowAddDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Task
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'} className="mb-4">
            <AlertDescription className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4" />
              {notification.message}
            </AlertDescription>
          </Alert>
        )}

        <Alert className="mb-4">
          <AlertDescription className="text-xs">
            Schedule automated tasks to run at specific times. Uses cron-style scheduling.
          </AlertDescription>
        </Alert>

        <ScrollArea className="h-[500px]">
          <div className="space-y-3">
            {tasks.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Clock className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>No scheduled tasks</p>
                <p className="text-xs">Add your first task to get started</p>
              </div>
            ) : (
              tasks.map((task) => (
                <Card key={task.id} className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1">
                      <div className={`p-2 rounded ${getActionColor(task.action)} mt-1`}>
                        {task.action === 'start_bot' && <Play className="h-4 w-4 text-white" />}
                        {task.action === 'stop_bot' && <Pause className="h-4 w-4 text-white" />}
                        {task.action === 'backup' && <Clock className="h-4 w-4 text-white" />}
                      </div>
                      <div className="space-y-2 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">{task.name}</span>
                          <Badge variant={task.enabled ? 'default' : 'secondary'}>
                            {task.enabled ? 'Active' : 'Disabled'}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{getActionLabel(task.action)}</Badge>
                          <Badge variant="outline" className="font-mono text-xs">
                            {task.schedule}
                          </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground space-y-1">
                          {task.last_run && (
                            <p>Last run: {new Date(task.last_run).toLocaleString()}</p>
                          )}
                          <p>Next run: {new Date(task.next_run).toLocaleString()}</p>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={task.enabled}
                        onCheckedChange={(checked) => handleToggle(task.id, checked)}
                      />
                      <Button variant="ghost" size="sm">
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
