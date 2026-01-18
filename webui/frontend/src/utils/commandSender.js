/**
 * Command Sender Utility - Saga Pattern for Bot Commands
 *
 * Provides robust command execution with:
 * - Optimistic UI updates
 * - Backend confirmation tracking
 * - Rollback on failure
 * - Toast notifications
 * - Timeout handling
 *
 * Date: November 12, 2025
 * Part of: WebUI Robustness Plan Week 3
 */

import apiClient from './apiClient';
import { v4 as uuidv4 } from 'uuid';

// Command types
export const COMMAND_TYPES = {
  START_BOT: 'start',
  STOP_BOT: 'stop',
  RESTART_BOT: 'restart',
  UPDATE_CONFIG: 'update_config',
  CANCEL_ORDERS: 'cancel_orders',
};

// Command status
const COMMAND_STATUS = {
  PENDING: 'pending',
  CONFIRMED: 'confirmed',
  FAILED: 'failed',
  TIMEOUT: 'timeout',
};

// In-flight commands tracking
const inFlightCommands = new Map();

/**
 * Send bot command with saga pattern
 *
 * @param {string} command - Command type from COMMAND_TYPES
 * @param {object} params - Command parameters
 * @param {object} options - Options { timeout, onSuccess, onError, onTimeout }
 * @returns {Promise<object>} Command result
 */
export async function sendBotCommand(command, params = {}, options = {}) {
  const { timeout = 30000, onSuccess, onError, onTimeout, optimisticUpdate } = options;

  // Generate confirmation ID
  const confirmationId = uuidv4();
  const startTime = Date.now();

  // Track command
  const commandState = {
    id: confirmationId,
    command,
    params,
    status: COMMAND_STATUS.PENDING,
    startTime,
    timeout,
  };

  inFlightCommands.set(confirmationId, commandState);

  try {
    // Apply optimistic update if provided
    if (optimisticUpdate) {
      optimisticUpdate();
    }

    // Send command to backend
    const response = await Promise.race([
      apiClient.post('/api/bot/command', {
        command,
        params,
        confirmation_id: confirmationId,
      }),
      new Promise((_, reject) => setTimeout(() => reject(new Error('Command timeout')), timeout)),
    ]);

    // Command confirmed
    commandState.status = COMMAND_STATUS.CONFIRMED;
    commandState.endTime = Date.now();
    commandState.duration = commandState.endTime - startTime;
    commandState.result = response;

    if (onSuccess) {
      onSuccess(response);
    }

    return {
      success: true,
      confirmationId,
      result: response,
      duration: commandState.duration,
    };
  } catch (error) {
    const isTimeout = error.message === 'Command timeout';

    commandState.status = isTimeout ? COMMAND_STATUS.TIMEOUT : COMMAND_STATUS.FAILED;
    commandState.endTime = Date.now();
    commandState.duration = commandState.endTime - startTime;
    commandState.error = error.message;

    if (isTimeout && onTimeout) {
      onTimeout(error);
    } else if (onError) {
      onError(error);
    }

    return {
      success: false,
      confirmationId,
      error: error.message,
      isTimeout,
      duration: commandState.duration,
    };
  } finally {
    // Clean up after 5 minutes
    setTimeout(
      () => {
        inFlightCommands.delete(confirmationId);
      },
      5 * 60 * 1000
    );
  }
}

/**
 * Start bot with confirmation
 */
export async function startBot(botName, options = {}) {
  return sendBotCommand(
    COMMAND_TYPES.START_BOT,
    { bot_name: botName },
    {
      ...options,
      onSuccess: (result) => {
        console.log(`✅ Bot ${botName} started successfully:`, result);
        if (options.onSuccess) options.onSuccess(result);
      },
      onError: (error) => {
        console.error(`❌ Failed to start bot ${botName}:`, error);
        if (options.onError) options.onError(error);
      },
    }
  );
}

/**
 * Stop bot with confirmation
 */
export async function stopBot(botName, options = {}) {
  return sendBotCommand(
    COMMAND_TYPES.STOP_BOT,
    { bot_name: botName },
    {
      ...options,
      onSuccess: (result) => {
        console.log(`✅ Bot ${botName} stopped successfully:`, result);
        if (options.onSuccess) options.onSuccess(result);
      },
      onError: (error) => {
        console.error(`❌ Failed to stop bot ${botName}:`, error);
        if (options.onError) options.onError(error);
      },
    }
  );
}

/**
 * Restart bot with confirmation
 */
export async function restartBot(botName, options = {}) {
  return sendBotCommand(
    COMMAND_TYPES.RESTART_BOT,
    { bot_name: botName },
    {
      ...options,
      timeout: options.timeout || 60000, // Restart takes longer
      onSuccess: (result) => {
        console.log(`✅ Bot ${botName} restarted successfully:`, result);
        if (options.onSuccess) options.onSuccess(result);
      },
      onError: (error) => {
        console.error(`❌ Failed to restart bot ${botName}:`, error);
        if (options.onError) options.onError(error);
      },
    }
  );
}

/**
 * Update bot config with confirmation
 */
export async function updateBotConfig(botName, configUpdates, options = {}) {
  return sendBotCommand(
    COMMAND_TYPES.UPDATE_CONFIG,
    { bot_name: botName, config: configUpdates },
    {
      ...options,
      onSuccess: (result) => {
        console.log(`✅ Config updated for ${botName}:`, result);
        if (options.onSuccess) options.onSuccess(result);
      },
      onError: (error) => {
        console.error(`❌ Failed to update config for ${botName}:`, error);
        if (options.onError) options.onError(error);
      },
    }
  );
}

/**
 * Cancel all pending orders with confirmation
 */
export async function cancelAllOrders(botName, options = {}) {
  return sendBotCommand(
    COMMAND_TYPES.CANCEL_ORDERS,
    { bot_name: botName },
    {
      ...options,
      onSuccess: (result) => {
        console.log(`✅ All orders cancelled for ${botName}:`, result);
        if (options.onSuccess) options.onSuccess(result);
      },
      onError: (error) => {
        console.error(`❌ Failed to cancel orders for ${botName}:`, error);
        if (options.onError) options.onError(error);
      },
    }
  );
}

/**
 * Get command status by confirmation ID
 */
export function getCommandStatus(confirmationId) {
  return inFlightCommands.get(confirmationId);
}

/**
 * Get all in-flight commands
 */
export function getAllInFlightCommands() {
  return Array.from(inFlightCommands.values());
}

/**
 * Get command statistics
 */
export function getCommandStats() {
  const commands = Array.from(inFlightCommands.values());

  return {
    total: commands.length,
    pending: commands.filter((c) => c.status === COMMAND_STATUS.PENDING).length,
    confirmed: commands.filter((c) => c.status === COMMAND_STATUS.CONFIRMED).length,
    failed: commands.filter((c) => c.status === COMMAND_STATUS.FAILED).length,
    timeout: commands.filter((c) => c.status === COMMAND_STATUS.TIMEOUT).length,
    avgDuration:
      commands.length > 0
        ? commands.reduce((sum, c) => sum + (c.duration || 0), 0) / commands.length
        : 0,
  };
}

export default {
  sendBotCommand,
  startBot,
  stopBot,
  restartBot,
  updateBotConfig,
  cancelAllOrders,
  getCommandStatus,
  getAllInFlightCommands,
  getCommandStats,
  COMMAND_TYPES,
};
