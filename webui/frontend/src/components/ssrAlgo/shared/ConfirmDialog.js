/**
 * ConfirmDialog Component
 * 
 * Modal dialog for confirming destructive or important actions.
 * 
 * Per Implementation Plan: Section 2.3 - shared/ConfirmDialog.js
 * Created: February 3, 2026
 */

import React, { useEffect, useRef, useCallback } from 'react';

/**
 * Variant configurations
 */
const VARIANT_CONFIG = {
  default: {
    icon: 'ℹ️',
    iconBg: 'bg-blue-100',
    confirmBtn: 'bg-blue-600 hover:bg-blue-700 text-white',
  },
  warning: {
    icon: '⚠️',
    iconBg: 'bg-yellow-100',
    confirmBtn: 'bg-yellow-600 hover:bg-yellow-700 text-white',
  },
  danger: {
    icon: '🚨',
    iconBg: 'bg-red-100',
    confirmBtn: 'bg-red-600 hover:bg-red-700 text-white',
  },
  success: {
    icon: '✅',
    iconBg: 'bg-green-100',
    confirmBtn: 'bg-green-600 hover:bg-green-700 text-white',
  },
};

/**
 * ConfirmDialog Component
 * 
 * @param {boolean} isOpen - Dialog open state
 * @param {function} onClose - Close handler
 * @param {function} onConfirm - Confirm handler
 * @param {string} title - Dialog title
 * @param {string} message - Dialog message
 * @param {string} confirmText - Confirm button text
 * @param {string} cancelText - Cancel button text
 * @param {string} variant - Dialog variant: 'default', 'warning', 'danger', 'success'
 * @param {boolean} loading - Show loading state on confirm button
 * @param {React.Node} children - Custom content
 * @param {string} className - Additional CSS classes
 */
const ConfirmDialog = ({
  isOpen,
  onClose,
  onConfirm,
  title = 'Confirm Action',
  message = 'Are you sure you want to proceed?',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'default',
  loading = false,
  children,
  className = '',
}) => {
  const overlayRef = useRef(null);
  const confirmBtnRef = useRef(null);
  const config = VARIANT_CONFIG[variant] || VARIANT_CONFIG.default;

  // Focus confirm button when dialog opens
  useEffect(() => {
    if (isOpen && confirmBtnRef.current) {
      confirmBtnRef.current.focus();
    }
  }, [isOpen]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  // Handle overlay click
  const handleOverlayClick = useCallback((e) => {
    if (e.target === overlayRef.current) {
      onClose();
    }
  }, [onClose]);

  // Handle confirm
  const handleConfirm = useCallback(async () => {
    if (loading) return;
    
    if (onConfirm) {
      await onConfirm();
    }
  }, [onConfirm, loading]);

  if (!isOpen) return null;

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
    >
      <div
        className={`
          bg-white rounded-lg shadow-xl max-w-md w-full mx-4
          transform transition-all
          ${className}
        `}
      >
        {/* Header with icon */}
        <div className="p-6">
          <div className="flex items-start">
            {/* Icon */}
            <div
              className={`
                flex-shrink-0 w-12 h-12 rounded-full
                flex items-center justify-center
                ${config.iconBg}
              `}
            >
              <span className="text-2xl">{config.icon}</span>
            </div>

            {/* Content */}
            <div className="ml-4 flex-1">
              <h3
                id="dialog-title"
                className="text-lg font-semibold text-gray-900"
              >
                {title}
              </h3>
              <p className="mt-2 text-sm text-gray-600">
                {message}
              </p>
              
              {/* Custom content */}
              {children && (
                <div className="mt-4">
                  {children}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer with buttons */}
        <div className="px-6 py-4 bg-gray-50 rounded-b-lg flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors text-sm font-medium disabled:opacity-50"
          >
            {cancelText}
          </button>
          <button
            ref={confirmBtnRef}
            onClick={handleConfirm}
            disabled={loading}
            className={`
              px-4 py-2 rounded-md transition-colors text-sm font-medium
              disabled:opacity-50 flex items-center
              ${config.confirmBtn}
            `}
          >
            {loading && (
              <svg
                className="animate-spin -ml-1 mr-2 h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            )}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

/**
 * Confirm dialog for session stop
 */
export const StopSessionDialog = ({ isOpen, onClose, onConfirm, sessionId, loading }) => {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Stop Session?"
      message="This will stop the current SSR Algo session. Any open positions will remain open and need to be managed manually."
      confirmText="Stop Session"
      cancelText="Keep Running"
      variant="danger"
      loading={loading}
    >
      {sessionId && (
        <div className="text-sm text-gray-500">
          Session ID: <code className="bg-gray-100 px-1 rounded">{sessionId}</code>
        </div>
      )}
    </ConfirmDialog>
  );
};

/**
 * Confirm dialog for emergency close all
 */
export const EmergencyCloseDialog = ({ isOpen, onClose, onConfirm, loading }) => {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Emergency Close All Positions?"
      message="This will immediately close ALL open positions at market price. This action cannot be undone."
      confirmText="Close All Positions"
      cancelText="Cancel"
      variant="danger"
      loading={loading}
    >
      <div className="p-3 bg-red-50 rounded-lg">
        <p className="text-sm text-red-700 font-medium">
          ⚠️ Warning: Market orders will be executed immediately.
        </p>
      </div>
    </ConfirmDialog>
  );
};

/**
 * Confirm dialog for triggering protective adjustment
 */
export const ManualTriggerDialog = ({ isOpen, onClose, onConfirm, zone, loading }) => {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Manually Trigger Protective Adjustment?"
      message={`This will execute the ${zone || 'protective'} adjustment strategy immediately, regardless of current price position.`}
      confirmText="Trigger Now"
      cancelText="Cancel"
      variant="warning"
      loading={loading}
    >
      <div className="p-3 bg-yellow-50 rounded-lg">
        <p className="text-sm text-yellow-700">
          Protective adjustment will be executed with the configured parameters.
        </p>
      </div>
    </ConfirmDialog>
  );
};

/**
 * Confirm dialog for session configuration reset
 */
export const ResetConfigDialog = ({ isOpen, onClose, onConfirm, loading }) => {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Reset Configuration?"
      message="This will reset all configuration values to their defaults. Any unsaved changes will be lost."
      confirmText="Reset to Defaults"
      cancelText="Keep Current"
      variant="warning"
      loading={loading}
    />
  );
};

export default ConfirmDialog;
