'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Download, FileDown, Database, TrendingUp, Activity, Calendar } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';

type ExportType = 'trades' | 'orders' | 'positions' | 'pnl' | 'config' | 'logs';
type ExportFormat = 'csv' | 'json' | 'excel';

async function exportData(type: ExportType, format: ExportFormat, startDate?: string, endDate?: string) {
  const params = new URLSearchParams({ format });
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const response = await fetch(`http://localhost:5555/api/export/${type}?${params}`);
  if (!response.ok) {
    throw new Error('Export failed');
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${type}-export-${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : format}`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ExportDataPanel() {
  const [exportType, setExportType] = useState<ExportType>('trades');
  const [format, setFormat] = useState<ExportFormat>('csv');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [exporting, setExporting] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const handleExport = async () => {
    setExporting(true);
    setNotification(null);

    try {
      await exportData(exportType, format, startDate, endDate);
      setNotification({ message: `${exportType} exported successfully`, type: 'success' });
    } catch (error) {
      setNotification({ message: (error as Error).message || 'Export failed', type: 'error' });
    } finally {
      setExporting(false);
    }
  };

  const exportOptions: { value: ExportType; label: string; icon: any }[] = [
    { value: 'trades', label: 'Trade History', icon: TrendingUp },
    { value: 'orders', label: 'Order History', icon: Activity },
    { value: 'positions', label: 'Positions', icon: Database },
    { value: 'pnl', label: 'P&L History', icon: TrendingUp },
    { value: 'config', label: 'Configuration', icon: Database },
    { value: 'logs', label: 'System Logs', icon: FileDown },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="h-5 w-5" />
          Export Data
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'}>
            <AlertDescription>{notification.message}</AlertDescription>
          </Alert>
        )}

        {/* Export Type Selection */}
        <div className="space-y-2">
          <Label>Data to Export</Label>
          <Select value={exportType} onValueChange={(value: ExportType) => setExportType(value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {exportOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  <div className="flex items-center gap-2">
                    <option.icon className="h-4 w-4" />
                    {option.label}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Format Selection */}
        <div className="space-y-2">
          <Label>Export Format</Label>
          <Select value={format} onValueChange={(value: ExportFormat) => setFormat(value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="csv">CSV (Comma-Separated)</SelectItem>
              <SelectItem value="json">JSON (JavaScript Object)</SelectItem>
              <SelectItem value="excel">Excel (XLSX)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Date Range (for time-series data) */}
        {['trades', 'orders', 'pnl', 'logs'].includes(exportType) && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Start Date (Optional)</Label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                placeholder="Start date"
              />
            </div>
            <div className="space-y-2">
              <Label>End Date (Optional)</Label>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                placeholder="End date"
              />
            </div>
          </div>
        )}

        {/* Export Info */}
        <div className="p-4 bg-muted rounded-lg">
          <div className="text-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Export Type:</span>
              <Badge variant="outline">{exportOptions.find((o) => o.value === exportType)?.label}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Format:</span>
              <Badge variant="outline">{format.toUpperCase()}</Badge>
            </div>
            {startDate && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">From:</span>
                <span className="font-medium">{startDate}</span>
              </div>
            )}
            {endDate && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">To:</span>
                <span className="font-medium">{endDate}</span>
              </div>
            )}
          </div>
        </div>

        {/* Export Button */}
        <Button onClick={handleExport} disabled={exporting} className="w-full" size="lg">
          <Download className="h-4 w-4 mr-2" />
          {exporting ? 'Exporting...' : 'Export Data'}
        </Button>

        <div className="text-xs text-center text-muted-foreground">
          Exported files will be downloaded to your Downloads folder
        </div>
      </CardContent>
    </Card>
  );
}
