/**
 * Toast Notification System
 * 
 * Phase 3: Animated notifications with variants
 */

'use client';

import { createContext, useContext, useState, useCallback } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Toast {
  id: string;
  title: string;
  description?: string;
  variant?: 'success' | 'error' | 'warning' | 'info';
  duration?: number;
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substring(7);
    const newToast = { ...toast, id };
    
    setToasts((prev) => [...prev, newToast]);

    // Auto remove after duration
    const duration = toast.duration || 5000;
    setTimeout(() => {
      removeToast(id);
    }, duration);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}

function ToastContainer({
  toasts,
  onRemove,
}: {
  toasts: Toast[];
  onRemove: (id: string) => void;
}) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
      ))}
    </div>
  );
}

function ToastItem({
  toast,
  onRemove,
}: {
  toast: Toast;
  onRemove: (id: string) => void;
}) {
  const variants = {
    success: {
      icon: CheckCircle,
      className: 'border-green-500/50 bg-green-500/10 text-green-600 dark:text-green-400',
      iconColor: 'text-green-500',
    },
    error: {
      icon: AlertCircle,
      className: 'border-red-500/50 bg-red-500/10 text-red-600 dark:text-red-400',
      iconColor: 'text-red-500',
    },
    warning: {
      icon: AlertTriangle,
      className: 'border-yellow-500/50 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
      iconColor: 'text-yellow-500',
    },
    info: {
      icon: Info,
      className: 'border-blue-500/50 bg-blue-500/10 text-blue-600 dark:text-blue-400',
      iconColor: 'text-blue-500',
    },
  };

  const variant = variants[toast.variant || 'info'];
  const Icon = variant.icon;

  return (
    <div
      className={cn(
        'glass-strong border rounded-lg p-4 shadow-lg fade-in-up flex items-start gap-3 min-w-[320px]',
        variant.className
      )}
      role="alert"
    >
      <Icon className={cn('h-5 w-5 flex-shrink-0 mt-0.5', variant.iconColor)} />
      
      <div className="flex-1 min-w-0">
        <h4 className="font-semibold text-sm mb-1">{toast.title}</h4>
        {toast.description && (
          <p className="text-sm opacity-90">{toast.description}</p>
        )}
      </div>
      
      <button
        onClick={() => onRemove(toast.id)}
        className="flex-shrink-0 p-1 hover:bg-white/10 rounded transition-colors"
        aria-label="Close notification"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export default ToastProvider;
