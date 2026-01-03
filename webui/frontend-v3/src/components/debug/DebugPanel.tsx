'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Bug, Play, Trash2, CheckCircle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

export function DebugPanel() {
  const [debugMode, setDebugMode] = useState(false);
  const [verboseLogging, setVerboseLogging] = useState(false);
  const [sqlLogging, setSqlLogging] = useState(false);
  const [apiLogging, setApiLogging] = useState(false);
  const [consoleOutput, setConsoleOutput] = useState<string[]>([]);
  const [command, setCommand] = useState('');
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const handleExecute = () => {
    if (!command.trim()) return;
    
    const output = `[${new Date().toLocaleTimeString()}] > ${command}`;
    setConsoleOutput((prev) => [...prev, output, '  ✓ Command executed']);
    setCommand('');
    showNotification('Debug command executed', 'success');
  };

  const handleClear = () => {
    setConsoleOutput([]);
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bug className="h-5 w-5" />
          Debug Utilities
        </CardTitle>
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

        <Alert variant="destructive">
          <Bug className="h-4 w-4" />
          <AlertDescription className="text-xs font-semibold">
            Debug tools for development only. Use with caution in production.
          </AlertDescription>
        </Alert>

        {/* Debug Toggles */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold">Debug Options</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <div>
                <Label>Debug Mode</Label>
                <p className="text-xs text-muted-foreground">Enable detailed debug output</p>
              </div>
              <Switch checked={debugMode} onCheckedChange={setDebugMode} />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <div>
                <Label>Verbose Logging</Label>
                <p className="text-xs text-muted-foreground">Log all operations in detail</p>
              </div>
              <Switch checked={verboseLogging} onCheckedChange={setVerboseLogging} />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <div>
                <Label>SQL Query Logging</Label>
                <p className="text-xs text-muted-foreground">Log all database queries</p>
              </div>
              <Switch checked={sqlLogging} onCheckedChange={setSqlLogging} />
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <div>
                <Label>API Request Logging</Label>
                <p className="text-xs text-muted-foreground">Log all API requests/responses</p>
              </div>
              <Switch checked={apiLogging} onCheckedChange={setApiLogging} />
            </div>
          </div>
        </div>

        {/* Debug Console */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Debug Console</h3>
            <Button variant="outline" size="sm" onClick={handleClear}>
              <Trash2 className="h-4 w-4 mr-2" />
              Clear
            </Button>
          </div>
          <ScrollArea className="h-[200px] rounded-lg bg-black p-4 font-mono text-xs">
            {consoleOutput.length === 0 ? (
              <p className="text-gray-500">Console output will appear here...</p>
            ) : (
              <div className="space-y-1">
                {consoleOutput.map((line, idx) => (
                  <div key={idx} className="text-green-400">
                    {line}
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>

        {/* Command Input */}
        <div className="space-y-2">
          <Label className="text-sm font-semibold">Execute Command</Label>
          <div className="flex gap-2">
            <Textarea
              placeholder="Enter debug command..."
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              className="font-mono text-xs"
              rows={3}
            />
            <Button onClick={handleExecute} disabled={!command.trim()}>
              <Play className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Current Status */}
        <div className="p-4 rounded-lg bg-muted space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Debug Mode:</span>
            <Badge variant={debugMode ? 'default' : 'secondary'}>
              {debugMode ? 'Enabled' : 'Disabled'}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Verbose Logging:</span>
            <Badge variant={verboseLogging ? 'default' : 'secondary'}>
              {verboseLogging ? 'On' : 'Off'}
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
