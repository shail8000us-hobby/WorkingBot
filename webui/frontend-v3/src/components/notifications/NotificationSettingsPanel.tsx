'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Bell, Save, CheckCircle } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface NotificationSettings {
  telegram_enabled: boolean;
  email_enabled: boolean;
  webhook_enabled: boolean;
  notifications: {
    order_filled: boolean;
    trade_opened: boolean;
    trade_closed: boolean;
    error_occurred: boolean;
    bot_started: boolean;
    bot_stopped: boolean;
    margin_warning: boolean;
    pnl_threshold: boolean;
  };
  min_severity: 'info' | 'warning' | 'error';
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
}

interface NotificationSettingsResponse {
  data: NotificationSettings;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchNotificationSettings(): Promise<NotificationSettingsResponse> {
  const response = await fetch('http://localhost:5557/api/settings/notifications');
  if (!response.ok) {
    throw new Error('Failed to fetch notification settings');
  }
  return response.json();
}

async function saveNotificationSettings(settings: NotificationSettings) {
  const response = await fetch('http://localhost:5557/api/settings/notifications/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  return response.json();
}

export function NotificationSettingsPanel() {
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['notification-settings'],
    queryFn: fetchNotificationSettings,
    refetchInterval: false,
  });

  // Initialize settings from data
  React.useEffect(() => {
    if (data?.data && !settings) {
      setSettings(data.data);
    }
  }, [data, settings]);

  const handleToggle = (key: keyof NotificationSettings, value: boolean) => {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
    setHasChanges(true);
  };

  const handleNotificationToggle = (key: keyof NotificationSettings['notifications'], value: boolean) => {
    if (!settings) return;
    setSettings({
      ...settings,
      notifications: { ...settings.notifications, [key]: value },
    });
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!settings) return;
    try {
      const result = await saveNotificationSettings(settings);
      if (result.success) {
        showNotification('Notification settings saved successfully', 'success');
        setHasChanges(false);
        refetch();
      } else {
        showNotification(result.error || 'Failed to save settings', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error saving settings', 'error');
    }
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notification Settings
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading settings...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Notification Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load notification settings'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const currentSettings = settings || data?.data;
  if (!currentSettings) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notification Settings
          </CardTitle>
          <div className="flex items-center gap-2">
            {hasChanges && <Badge variant="destructive">Unsaved Changes</Badge>}
            <Button size="sm" onClick={handleSave} disabled={!hasChanges}>
              <Save className="h-4 w-4 mr-2" />
              Save Changes
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'}>
            <AlertDescription className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4" />
              {notification.message}
            </AlertDescription>
          </Alert>
        )}

        {/* Notification Channels */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Notification Channels</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <Label>Telegram Notifications</Label>
                <p className="text-xs text-muted-foreground">Send alerts via Telegram bot</p>
              </div>
              <Switch
                checked={currentSettings.telegram_enabled}
                onCheckedChange={(checked) => handleToggle('telegram_enabled', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <Label>Email Notifications</Label>
                <p className="text-xs text-muted-foreground">Send alerts via email</p>
              </div>
              <Switch
                checked={currentSettings.email_enabled}
                onCheckedChange={(checked) => handleToggle('email_enabled', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <Label>Webhook Notifications</Label>
                <p className="text-xs text-muted-foreground">Send alerts to configured webhooks</p>
              </div>
              <Switch
                checked={currentSettings.webhook_enabled}
                onCheckedChange={(checked) => handleToggle('webhook_enabled', checked)}
              />
            </div>
          </div>
        </div>

        {/* Event Types */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Event Types</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <Label className="text-sm">Order Filled</Label>
              <Switch
                checked={currentSettings.notifications.order_filled}
                onCheckedChange={(checked) => handleNotificationToggle('order_filled', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <Label className="text-sm">Trade Opened</Label>
              <Switch
                checked={currentSettings.notifications.trade_opened}
                onCheckedChange={(checked) => handleNotificationToggle('trade_opened', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <Label className="text-sm">Trade Closed</Label>
              <Switch
                checked={currentSettings.notifications.trade_closed}
                onCheckedChange={(checked) => handleNotificationToggle('trade_closed', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <Label className="text-sm">Error Occurred</Label>
              <Switch
                checked={currentSettings.notifications.error_occurred}
                onCheckedChange={(checked) => handleNotificationToggle('error_occurred', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <Label className="text-sm">Bot Started</Label>
              <Switch
                checked={currentSettings.notifications.bot_started}
                onCheckedChange={(checked) => handleNotificationToggle('bot_started', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <Label className="text-sm">Bot Stopped</Label>
              <Switch
                checked={currentSettings.notifications.bot_stopped}
                onCheckedChange={(checked) => handleNotificationToggle('bot_stopped', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <Label className="text-sm">Margin Warning</Label>
              <Switch
                checked={currentSettings.notifications.margin_warning}
                onCheckedChange={(checked) => handleNotificationToggle('margin_warning', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <Label className="text-sm">P&L Threshold</Label>
              <Switch
                checked={currentSettings.notifications.pnl_threshold}
                onCheckedChange={(checked) => handleNotificationToggle('pnl_threshold', checked)}
              />
            </div>
          </div>
        </div>

        {/* Severity Filter */}
        <div className="space-y-3">
          <Label className="text-base font-semibold">Minimum Severity</Label>
          <Select
            value={currentSettings.min_severity}
            onValueChange={(value) => {
              if (!settings) return;
              setSettings({ ...settings, min_severity: value as 'info' | 'warning' | 'error' });
              setHasChanges(true);
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="info">Info and above</SelectItem>
              <SelectItem value="warning">Warning and above</SelectItem>
              <SelectItem value="error">Error only</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Only notifications with this severity or higher will be sent
          </p>
        </div>

        {/* Quiet Hours */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-base font-semibold">Quiet Hours</Label>
              <p className="text-xs text-muted-foreground">Suppress notifications during specified hours</p>
            </div>
            <Switch
              checked={currentSettings.quiet_hours_enabled}
              onCheckedChange={(checked) => handleToggle('quiet_hours_enabled', checked)}
            />
          </div>
          {currentSettings.quiet_hours_enabled && (
            <div className="grid grid-cols-2 gap-4 pl-4">
              <div className="space-y-2">
                <Label className="text-sm">Start Time</Label>
                <Badge variant="outline">{currentSettings.quiet_hours_start || '22:00'}</Badge>
              </div>
              <div className="space-y-2">
                <Label className="text-sm">End Time</Label>
                <Badge variant="outline">{currentSettings.quiet_hours_end || '08:00'}</Badge>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
