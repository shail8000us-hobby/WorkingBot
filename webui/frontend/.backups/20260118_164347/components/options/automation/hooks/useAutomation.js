/**
 * useAutomation - Main React hook for automation UI
 * 
 * Features:
 * - Manage dialog open/close state
 * - Load/save automation rules
 * - Start/stop automation
 * - Get automation status
 */

import { useState, useCallback, useEffect } from 'react';
import automationStorage from '../storage/AutomationStorage';
import automationMonitor from '../monitoring/AutomationMonitor';
import { DEFAULT_RULES, AUTOMATION_STATUS } from '../types/constants';

export const useAutomation = (position) => {
  const [isDialogOpen, setDialogOpen] = useState(false);
  const [rules, setRules] = useState(null);
  const [status, setStatus] = useState(AUTOMATION_STATUS.INACTIVE);
  const [automationId, setAutomationId] = useState(null);

  // Generate automation ID from position symbol
  const generateAutomationId = useCallback(() => {
    if (!position) return null;
    return `auto_${position.product_symbol}_${Date.now()}`;
  }, [position]);

  // Load existing automation for this position (only on symbol change, not every position update)
  useEffect(() => {
    if (!position || !position.product_symbol) return;

    // Only load if rules haven't been set yet
    if (rules !== null) return;

    const existing = automationStorage.getByPosition(position.product_symbol);
    if (existing.length > 0) {
      // Load most recent automation
      const latest = existing.sort((a, b) => 
        new Date(b.createdAt) - new Date(a.createdAt)
      )[0];
      
      setRules(latest.rules);
      setStatus(latest.status || AUTOMATION_STATUS.INACTIVE);
      setAutomationId(latest.id);
    } else {
      // No existing automation, use defaults
      setRules(JSON.parse(JSON.stringify(DEFAULT_RULES)));
    }
  }, [position?.product_symbol, rules]);

  // Open dialog
  const openDialog = useCallback(() => {
    setDialogOpen(true);
  }, []);

  // Close dialog
  const closeDialog = useCallback(() => {
    setDialogOpen(false);
  }, []);

  // Update rules
  const updateRules = useCallback((newRules) => {
    setRules(newRules);
  }, []);

  // Start automation
  const startAutomation = useCallback((newRules) => {
    if (!position) {
      console.error('Cannot start automation: no position provided');
      return;
    }

    const id = automationId || generateAutomationId();
    
    const automationData = {
      id,
      rules: newRules || rules,
      position: {
        symbol: position.product_symbol,
        strike: position.strike,
        type: position.type,
        underlying: position.underlying,
        expiry: position.expiry,
      },
      status: AUTOMATION_STATUS.WAITING,
      createdAt: new Date().toISOString(),
    };

    // Save to storage
    automationStorage.save(id, automationData);

    // Register with monitor
    automationMonitor.register(id, automationData);

    setAutomationId(id);
    setStatus(AUTOMATION_STATUS.WAITING);
    setRules(newRules || rules);

    console.log(`Started automation: ${id}`);
  }, [position, rules, automationId, generateAutomationId]);

  // Stop automation
  const stopAutomation = useCallback(() => {
    if (!automationId) return;

    automationMonitor.unregister(automationId);
    setStatus(AUTOMATION_STATUS.INACTIVE);

    console.log(`Stopped automation: ${automationId}`);
  }, [automationId]);

  // Pause automation
  const pauseAutomation = useCallback(() => {
    if (!automationId) return;

    automationMonitor.unregister(automationId);
    automationStorage.updateStatus(automationId, AUTOMATION_STATUS.PAUSED);
    setStatus(AUTOMATION_STATUS.PAUSED);

    console.log(`Paused automation: ${automationId}`);
  }, [automationId]);

  // Resume automation
  const resumeAutomation = useCallback(() => {
    if (!automationId) return;

    const automation = automationStorage.load(automationId);
    if (automation) {
      automationMonitor.register(automationId, automation);
      setStatus(AUTOMATION_STATUS.WAITING);
      console.log(`Resumed automation: ${automationId}`);
    }
  }, [automationId]);

  // Delete automation
  const deleteAutomation = useCallback(() => {
    if (!automationId) return;

    stopAutomation();
    automationStorage.delete(automationId);
    setAutomationId(null);
    setRules(JSON.parse(JSON.stringify(DEFAULT_RULES)));

    console.log(`Deleted automation: ${automationId}`);
  }, [automationId, stopAutomation]);

  return {
    // Dialog state
    isDialogOpen,
    openDialog,
    closeDialog,
    
    // Rules
    rules,
    updateRules,
    
    // Status
    status,
    automationId,
    
    // Actions
    startAutomation,
    stopAutomation,
    pauseAutomation,
    resumeAutomation,
    deleteAutomation,
  };
};
