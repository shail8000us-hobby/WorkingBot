'use client';

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';

type NotificationSeverity = 'success' | 'error' | 'warning' | 'info';

interface Notification {
  id: string;
  message: string;
  severity: NotificationSeverity;
  duration: number | null;
  title?: string;
  timestamp: Date;
}

interface NotificationContextType {
  notifications: Notification[];
  history: Notification[];
  showNotification: (message: string, options?: NotificationOptions) => string;
  hideNotification: (id: string) => void;
  clearAll: () => void;
  success: (message: string, options?: Omit<NotificationOptions, 'severity'>) => string;
  error: (message: string, options?: Omit<NotificationOptions, 'severity'>) => string;
  warning: (message: string, options?: Omit<NotificationOptions, 'severity'>) => string;
  info: (message: string, options?: Omit<NotificationOptions, 'severity'>) => string;
}

interface NotificationOptions {
  severity?: NotificationSeverity;
  duration?: number;
  title?: string;
  persist?: boolean;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export function useNotification() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within NotificationProvider');
  }
  return context;
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [history, setHistory] = useState<Notification[]>([]);

  const showNotification = useCallback((message: string, options: NotificationOptions = {}) => {
    const {
      severity = 'info',
      duration = severity === 'error' ? 6000 : 4000,
      title,
      persist = false,
    } = options;

    const notification: Notification = {
      id: `${Date.now()}-${Math.random()}`,
      message,
      severity,
      duration: persist ? null : duration,
      title,
      timestamp: new Date(),
    };

    setNotifications((prev) => [...prev, notification]);
    setHistory((prev) => [notification, ...prev.slice(0, 49)]); // Keep last 50

    // Auto-hide if not persistent
    if (!persist && duration) {
      setTimeout(() => {
        hideNotification(notification.id);
      }, duration);
    }

    return notification.id;
  }, []);

  const hideNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  const success = useCallback(
    (message: string, options: Omit<NotificationOptions, 'severity'> = {}) => {
      return showNotification(message, { ...options, severity: 'success' });
    },
    [showNotification]
  );

  const error = useCallback(
    (message: string, options: Omit<NotificationOptions, 'severity'> = {}) => {
      return showNotification(message, { ...options, severity: 'error' });
    },
    [showNotification]
  );

  const warning = useCallback(
    (message: string, options: Omit<NotificationOptions, 'severity'> = {}) => {
      return showNotification(message, { ...options, severity: 'warning' });
    },
    [showNotification]
  );

  const info = useCallback(
    (message: string, options: Omit<NotificationOptions, 'severity'> = {}) => {
      return showNotification(message, { ...options, severity: 'info' });
    },
    [showNotification]
  );

  const value: NotificationContextType = {
    showNotification,
    hideNotification,
    clearAll,
    success,
    error,
    warning,
    info,
    notifications,
    history,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <NotificationQueue notifications={notifications} onClose={hideNotification} />
    </NotificationContext.Provider>
  );
}

function NotificationQueue({
  notifications,
  onClose,
}: {
  notifications: Notification[];
  onClose: (id: string) => void;
}) {
  const getIcon = (severity: NotificationSeverity) => {
    switch (severity) {
      case 'success':
        return <CheckCircle className="h-4 w-4" />;
      case 'error':
        return <AlertCircle className="h-4 w-4" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4" />;
      case 'info':
      default:
        return <Info className="h-4 w-4" />;
    }
  };

  const getVariant = (
    severity: NotificationSeverity
  ): 'default' | 'destructive' | undefined => {
    if (severity === 'error') return 'destructive';
    return 'default';
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md">
      {notifications.map((notification, index) => (
        <Alert
          key={notification.id}
          variant={getVariant(notification.severity)}
          className="shadow-lg animate-in slide-in-from-right"
        >
          <div className="flex items-start gap-2">
            {getIcon(notification.severity)}
            <div className="flex-1">
              {notification.title && (
                <AlertTitle className="font-bold">{notification.title}</AlertTitle>
              )}
              <AlertDescription>{notification.message}</AlertDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={() => onClose(notification.id)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </Alert>
      ))}
    </div>
  );
}
