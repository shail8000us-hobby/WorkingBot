'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Layout, Grid3x3, Columns, Rows, Save, RotateCcw, Check } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

type LayoutPreset = 'default' | 'trading' | 'monitoring' | 'analytics' | 'custom';

interface LayoutConfig {
  name: string;
  description: string;
  icon: React.ReactNode;
  grid: string;
}

export function DashboardLayoutPanel() {
  const [selectedLayout, setSelectedLayout] = useState<LayoutPreset>('default');
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const layouts: Record<LayoutPreset, LayoutConfig> = {
    default: {
      name: 'Default Layout',
      description: 'Balanced view with all panels visible',
      icon: <Layout className="h-5 w-5" />,
      grid: 'grid-cols-2 grid-rows-3',
    },
    trading: {
      name: 'Trading Focus',
      description: 'Emphasizes orders, positions, and execution',
      icon: <Grid3x3 className="h-5 w-5" />,
      grid: 'grid-cols-3 grid-rows-2',
    },
    monitoring: {
      name: 'System Monitoring',
      description: 'Health, logs, and performance metrics',
      icon: <Columns className="h-5 w-5" />,
      grid: 'grid-cols-1 grid-rows-4',
    },
    analytics: {
      name: 'Analytics Dashboard',
      description: 'Charts, statistics, and insights',
      icon: <Rows className="h-5 w-5" />,
      grid: 'grid-cols-2 grid-rows-2',
    },
    custom: {
      name: 'Custom Layout',
      description: 'Your saved custom configuration',
      icon: <Grid3x3 className="h-5 w-5" />,
      grid: 'grid-cols-2 grid-rows-3',
    },
  };

  const handleLayoutChange = (layout: LayoutPreset) => {
    setSelectedLayout(layout);
    localStorage.setItem('dashboard-layout', layout);
    showNotification(`Layout changed to ${layouts[layout].name}`, 'success');
  };

  const handleSaveCustom = () => {
    localStorage.setItem('dashboard-layout-custom', JSON.stringify(selectedLayout));
    showNotification('Custom layout saved successfully', 'success');
  };

  const handleReset = () => {
    setSelectedLayout('default');
    localStorage.removeItem('dashboard-layout');
    localStorage.removeItem('dashboard-layout-custom');
    showNotification('Layout reset to default', 'success');
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Layout className="h-5 w-5" />
            Dashboard Layout
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleSaveCustom}>
              <Save className="h-4 w-4 mr-2" />
              Save Custom
            </Button>
            <Button variant="outline" size="sm" onClick={handleReset}>
              <RotateCcw className="h-4 w-4 mr-2" />
              Reset
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'}>
            <AlertDescription className="flex items-center gap-2">
              <Check className="h-4 w-4" />
              {notification.message}
            </AlertDescription>
          </Alert>
        )}

        {/* Layout Selection */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Select Layout Preset</span>
            <Badge variant="outline">{layouts[selectedLayout].name}</Badge>
          </div>
          <Select value={selectedLayout} onValueChange={(value) => handleLayoutChange(value as LayoutPreset)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(layouts).map(([key, config]) => (
                <SelectItem key={key} value={key}>
                  <div className="flex items-center gap-2">
                    {config.icon}
                    <div>
                      <div className="font-medium">{config.name}</div>
                      <div className="text-xs text-muted-foreground">{config.description}</div>
                    </div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Layout Preview Cards */}
        <div className="grid grid-cols-2 gap-4">
          {Object.entries(layouts).map(([key, config]) => {
            const isSelected = selectedLayout === key;
            return (
              <div
                key={key}
                className={`relative p-4 rounded-lg border-2 cursor-pointer transition-all ${
                  isSelected
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50'
                }`}
                onClick={() => handleLayoutChange(key as LayoutPreset)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    {config.icon}
                    <span className="font-semibold text-sm">{config.name}</span>
                  </div>
                  {isSelected && (
                    <Badge variant="default" className="h-5">
                      <Check className="h-3 w-3" />
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mb-3">{config.description}</p>
                
                {/* Visual Grid Preview */}
                <div className={`grid ${config.grid} gap-1 h-24`}>
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="bg-muted rounded" />
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Layout Configuration */}
        <div className="p-4 rounded-lg bg-muted space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Current Layout:</span>
            <Badge variant="outline">{layouts[selectedLayout].name}</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Grid Configuration:</span>
            <Badge variant="outline">{layouts[selectedLayout].grid}</Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Changes are saved automatically and will persist across sessions
          </p>
        </div>

        {/* Panel Visibility (Future Enhancement) */}
        <Alert>
          <AlertDescription className="text-xs">
            <strong>💡 Tip:</strong> You can customize which panels are visible in each layout.
            This feature will allow you to show/hide specific components.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
