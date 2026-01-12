'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Database, Download, Upload, RotateCcw, CheckCircle, AlertTriangle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface BackupEntry {
  id: string;
  filename: string;
  size: number;
  created_at: string;
  includes: string[];
}

interface BackupResponse {
  data: { backups: BackupEntry[] };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchBackups(): Promise<BackupResponse> {
  const response = await fetch('http://localhost:5557/api/backup/list');
  if (!response.ok) {
    throw new Error('Failed to fetch backups');
  }
  return response.json();
}

async function createBackup() {
  const response = await fetch('http://localhost:5557/api/backup/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      include: ['config', 'trades', 'positions', 'orders'],
    }),
  });
  return response.json();
}

async function restoreBackup(backupId: string) {
  const response = await fetch('http://localhost:5557/api/backup/restore', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ backup_id: backupId }),
  });
  return response.json();
}

async function downloadBackup(backupId: string) {
  const response = await fetch(`http://localhost:5557/api/backup/download/${backupId}`);
  if (!response.ok) {
    throw new Error('Failed to download backup');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `backup_${backupId}.zip`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

export function BackupPanel() {
  const [creating, setCreating] = useState(false);
  const [showRestoreDialog, setShowRestoreDialog] = useState(false);
  const [selectedBackup, setSelectedBackup] = useState<BackupEntry | null>(null);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['backups'],
    queryFn: fetchBackups,
    refetchInterval: false,
  });

  const handleCreateBackup = async () => {
    setCreating(true);
    try {
      const result = await createBackup();
      if (result.success) {
        showNotification('Backup created successfully', 'success');
        refetch();
      } else {
        showNotification(result.error || 'Failed to create backup', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error creating backup', 'error');
    } finally {
      setCreating(false);
    }
  };

  const handleRestore = async () => {
    if (!selectedBackup) return;
    try {
      const result = await restoreBackup(selectedBackup.id);
      if (result.success) {
        showNotification('Backup restored successfully', 'success');
        setShowRestoreDialog(false);
        setSelectedBackup(null);
      } else {
        showNotification(result.error || 'Failed to restore backup', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error restoring backup', 'error');
    }
  };

  const handleDownload = async (backup: BackupEntry) => {
    try {
      await downloadBackup(backup.id);
      showNotification('Backup downloaded successfully', 'success');
    } catch (err) {
      showNotification((err as Error).message || 'Error downloading backup', 'error');
    }
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Backup & Restore
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading backups...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backup & Restore</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load backups'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const backups = data?.data?.backups || [];

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Backup & Restore
            </CardTitle>
            <Button size="sm" onClick={handleCreateBackup} disabled={creating}>
              <Upload className="h-4 w-4 mr-2" />
              {creating ? 'Creating...' : 'Create Backup'}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Notification */}
          {notification && (
            <Alert variant={notification.type === 'error' ? 'destructive' : 'default'} className="mb-4">
              <AlertDescription className="flex items-center gap-2">
                {notification.type === 'success' ? (
                  <CheckCircle className="h-4 w-4" />
                ) : (
                  <AlertTriangle className="h-4 w-4" />
                )}
                {notification.message}
              </AlertDescription>
            </Alert>
          )}

          <Alert className="mb-4">
            <AlertDescription className="text-xs">
              <strong>💾 Important:</strong> Backups include configuration, trades, positions, and orders.
              Always create a backup before making major changes.
            </AlertDescription>
          </Alert>

          <ScrollArea className="h-[500px]">
            <div className="space-y-3">
              {backups.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Database className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>No backups available</p>
                  <p className="text-xs">Create your first backup to get started</p>
                </div>
              ) : (
                backups.map((backup) => (
                  <Card key={backup.id} className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="space-y-2 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold font-mono text-sm">{backup.filename}</span>
                          <Badge variant="outline">{formatSize(backup.size)}</Badge>
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                          {backup.includes.map((item) => (
                            <Badge key={item} variant="secondary" className="text-xs">
                              {item}
                            </Badge>
                          ))}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Created: {new Date(backup.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDownload(backup)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedBackup(backup);
                            setShowRestoreDialog(true);
                          }}
                        >
                          <RotateCcw className="h-4 w-4" />
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

      {/* Restore Confirmation Dialog */}
      <Dialog open={showRestoreDialog} onOpenChange={setShowRestoreDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Restore</DialogTitle>
            <DialogDescription>
              Are you sure you want to restore from this backup? This will overwrite your current
              configuration and data.
            </DialogDescription>
          </DialogHeader>
          {selectedBackup && (
            <div className="p-4 rounded-lg bg-muted space-y-2">
              <p className="font-semibold text-sm">{selectedBackup.filename}</p>
              <p className="text-xs text-muted-foreground">
                Created: {new Date(selectedBackup.created_at).toLocaleString()}
              </p>
              <div className="flex gap-2 flex-wrap">
                {selectedBackup.includes.map((item) => (
                  <Badge key={item} variant="secondary" className="text-xs">
                    {item}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRestoreDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleRestore}>
              <RotateCcw className="h-4 w-4 mr-2" />
              Restore
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
