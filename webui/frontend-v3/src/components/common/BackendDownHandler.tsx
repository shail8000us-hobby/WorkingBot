/**
 * Backend Down Handler
 * 
 * Full-screen overlay when backend is unreachable.
 * Shows connection status and auto-retry functionality.
 */

'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, WifiOff, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5555';

interface BackendDownProps {
  children: React.ReactNode;
  /** Interval to check backend health (ms) */
  checkInterval?: number;
  /** Show as overlay instead of replacing content */
  overlay?: boolean;
}

export function BackendDownHandler({ 
  children, 
  checkInterval = 5000,
  overlay = false 
}: BackendDownProps) {
  const [isBackendDown, setIsBackendDown] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const checkBackend = async () => {
    setIsChecking(true);
    try {
      const response = await fetch(`${API_URL}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      
      if (response.ok) {
        setIsBackendDown(false);
        setRetryCount(0);
      } else {
        setIsBackendDown(true);
        setRetryCount((c) => c + 1);
      }
    } catch {
      setIsBackendDown(true);
      setRetryCount((c) => c + 1);
    } finally {
      setIsChecking(false);
      setLastChecked(new Date());
    }
  };

  // Initial check and periodic retry
  useEffect(() => {
    checkBackend();
    
    const interval = setInterval(() => {
      if (isBackendDown) {
        checkBackend();
      }
    }, checkInterval);

    return () => clearInterval(interval);
  }, [isBackendDown, checkInterval]);

  if (!isBackendDown) {
    return <>{children}</>;
  }

  const backendDownContent = (
    <Card className="max-w-md mx-auto border-destructive">
      <CardHeader className="text-center pb-2">
        <div className="mx-auto mb-4 p-3 rounded-full bg-destructive/10 w-fit">
          <WifiOff className="h-8 w-8 text-destructive" />
        </div>
        <CardTitle className="text-xl">Backend Unavailable</CardTitle>
        <CardDescription>
          Unable to connect to the trading backend
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="text-sm text-muted-foreground space-y-2">
          <p className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
            The backend server at {API_URL} is not responding
          </p>
          <p>
            Retry attempt: <span className="font-mono">{retryCount}</span>
          </p>
          {lastChecked && (
            <p className="text-xs">
              Last checked: {lastChecked.toLocaleTimeString()}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <Button
            onClick={checkBackend}
            disabled={isChecking}
            className="w-full"
          >
            {isChecking ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Checking...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry Now
              </>
            )}
          </Button>

          <p className="text-xs text-center text-muted-foreground">
            Auto-retrying every {checkInterval / 1000}s
          </p>
        </div>

        <div className="pt-4 border-t text-xs text-muted-foreground">
          <p className="font-medium mb-1">Troubleshooting:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Check if the backend server is running</li>
            <li>Verify network connectivity</li>
            <li>Confirm the API URL is correct</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );

  if (overlay) {
    return (
      <>
        {children}
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
          {backendDownContent}
        </div>
      </>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-[400px] p-4">
      {backendDownContent}
    </div>
  );
}

export default BackendDownHandler;
