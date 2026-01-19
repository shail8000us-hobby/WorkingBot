/**
 * NotificationService - Send alerts when automation triggers
 *
 * Features:
 * - Toast notifications (using browser Notification API or Material-UI Snackbar)
 * - Sound alerts
 * - Email/SMS (placeholder for future)
 */

import { NOTIFICATION_TYPES } from '../types/constants';
import soundManager from '../../../../utils/soundManager';

class NotificationService {
  constructor() {
    this.soundEnabled = true;
    this.toastCallback = null; // Will be set by UI component
    this.soundManager = soundManager;

    // Pre-load sound effects (you'll need to add actual sound files)
    this.sounds = {
      success: null, // new Audio('/sounds/success.mp3')
      warning: null, // new Audio('/sounds/warning.mp3')
      error: null, // new Audio('/sounds/error.mp3')
    };
  }

  /**
   * Set callback for toast notifications
   * @param {Function} callback - Function to show toast (from UI component)
   */
  setToastCallback(callback) {
    this.toastCallback = callback;
  }

  /**
   * Main notification method
   * @param {string|Object} typeOrObj - Notification type OR object with {type, title, message}
   * @param {string} message - Message to display (if typeOrObj is string)
   * @param {Object} options - Additional options
   */
  notify(typeOrObj, message, options = {}) {
    // Support both object and positional argument styles
    let type, displayMessage, notifyOptions;

    if (typeof typeOrObj === 'object' && typeOrObj !== null) {
      // Object style: notify({ type, title, message, ... })
      type = typeOrObj.type;
      displayMessage = typeOrObj.title
        ? `${typeOrObj.title}: ${typeOrObj.message || ''}`
        : typeOrObj.message;
      notifyOptions = { browserNotification: typeOrObj.browserNotification, ...typeOrObj };
    } else {
      // Positional style: notify(type, message, options)
      type = typeOrObj;
      displayMessage = message;
      notifyOptions = options;
    }

    const config = this._getConfigForType(type);

    // Show toast notification
    this._showToast(displayMessage, config.severity);

    // Play sound if enabled
    if (this.soundEnabled && config.sound) {
      this._playSound(config.sound);
    }

    // Browser notification (if permission granted)
    if (notifyOptions.browserNotification) {
      this._showBrowserNotification(displayMessage, config);
    }

    // Log to console for debugging
    console.log(`[${type}] ${displayMessage}`, notifyOptions);
  }

  /**
   * Show toast notification using callback
   * @param {string} message - Message to display
   * @param {string} severity - 'success' | 'warning' | 'error' | 'info'
   */
  _showToast(message, severity = 'info') {
    if (this.toastCallback) {
      this.toastCallback(message, severity);
    } else {
      // Fallback: log to console if no callback set
      console.log(`Toast: [${severity}] ${message}`);
    }
  }

  /**
   * Play sound effect
   * @param {string} soundType - 'success' | 'warning' | 'error'
   */
  _playSound(soundType) {
    try {
      // Use sound manager for trade filled notifications (calming chime)
      if (soundType === 'success') {
        this.soundManager.playTradeFilled();
      }
      
      const sound = this.sounds[soundType];
      if (sound) {
        sound.currentTime = 0;
        sound.play().catch((err) => {
          console.warn('Failed to play sound:', err);
        });
      } else {
        // Fallback: use Web Audio API to generate beep
        this._beep(soundType);
      }
    } catch (error) {
      console.warn('Sound playback error:', error);
    }
  }

  /**
   * Generate simple beep using Web Audio API
   * @param {string} type - 'success' | 'warning' | 'error'
   */
  _beep(type) {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      // Different frequencies for different types
      const frequencies = {
        success: 880, // A5
        warning: 660, // E5
        error: 440, // A4
      };

      oscillator.frequency.value = frequencies[type] || 440;
      oscillator.type = 'sine';

      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.2);
    } catch (error) {
      console.warn('Beep generation error:', error);
    }
  }

  /**
   * Show browser notification (requires permission)
   * @param {string} message - Message text
   * @param {Object} config - Notification config
   */
  _showBrowserNotification(message, config) {
    if (!('Notification' in window)) {
      console.warn('Browser does not support notifications');
      return;
    }

    if (Notification.permission === 'granted') {
      new Notification('Options Automation', {
        body: message,
        icon: config.icon || '/favicon.ico',
        tag: 'automation-notification',
      });
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then((permission) => {
        if (permission === 'granted') {
          this._showBrowserNotification(message, config);
        }
      });
    }
  }

  /**
   * Get configuration for notification type
   * @param {string} type - Notification type
   * @returns {Object} Config object
   */
  _getConfigForType(type) {
    const configs = {
      [NOTIFICATION_TYPES.ENTRY_TRIGGERED]: {
        severity: 'info',
        sound: 'warning',
        icon: '⚡',
      },
      [NOTIFICATION_TYPES.EXIT_TRIGGERED]: {
        severity: 'info',
        sound: 'warning',
        icon: '🚪',
      },
      [NOTIFICATION_TYPES.ORDER_PLACED]: {
        severity: 'info',
        sound: 'success',
        icon: '📝',
      },
      [NOTIFICATION_TYPES.ORDER_FILLED]: {
        severity: 'success',
        sound: 'success',
        icon: '✅',
      },
      [NOTIFICATION_TYPES.ORDER_FAILED]: {
        severity: 'error',
        sound: 'error',
        icon: '❌',
      },
      [NOTIFICATION_TYPES.RISK_LIMIT_HIT]: {
        severity: 'warning',
        sound: 'warning',
        icon: '⚠️',
      },
      [NOTIFICATION_TYPES.ERROR]: {
        severity: 'error',
        sound: 'error',
        icon: '🔴',
      },
      [NOTIFICATION_TYPES.WARNING]: {
        severity: 'warning',
        sound: 'warning',
        icon: '⚠️',
      },
    };

    return (
      configs[type] || {
        severity: 'info',
        sound: null,
        icon: 'ℹ️',
      }
    );
  }

  /**
   * Enable/disable sound
   * @param {boolean} enabled - Enable or disable sound
   */
  setSoundEnabled(enabled) {
    this.soundEnabled = enabled;
  }

  /**
   * Request browser notification permission
   */
  requestPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
      return Notification.requestPermission();
    }
    return Promise.resolve(Notification.permission);
  }

  /**
   * Send email notification (placeholder for backend integration)
   * @param {string} to - Email address
   * @param {string} subject - Email subject
   * @param {string} body - Email body
   */
  async sendEmail(to, subject, body) {
    // TODO: Implement backend email service
    console.log('Email notification:', { to, subject, body });
    // return fetch('/api/notifications/email', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({ to, subject, body }),
    // });
  }

  /**
   * Send SMS notification (placeholder for backend integration)
   * @param {string} phone - Phone number
   * @param {string} message - SMS message
   */
  async sendSMS(phone, message) {
    // TODO: Implement backend SMS service
    console.log('SMS notification:', { phone, message });
    // return fetch('/api/notifications/sms', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({ phone, message }),
    // });
  }
}

// Singleton instance
const notificationService = new NotificationService();
export default notificationService;
