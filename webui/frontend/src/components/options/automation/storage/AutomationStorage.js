/**
 * AutomationStorage - Persist automation rules to localStorage
 *
 * Features:
 * - Save/load automation rules
 * - Export/import as JSON
 * - Clear old/completed automations
 */

import { STORAGE_KEYS } from '../types/constants';

class AutomationStorage {
  /**
   * Save automation rule
   * @param {string} automationId - Unique ID for this automation
   * @param {Object} rules - Automation rules object
   */
  save(automationId, rules) {
    try {
      const allAutomations = this.loadAll();
      allAutomations[automationId] = {
        ...rules,
        id: automationId,
        createdAt: rules.createdAt || new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      localStorage.setItem(STORAGE_KEYS.AUTOMATIONS, JSON.stringify(allAutomations));
      return true;
    } catch (error) {
      console.error('Failed to save automation:', error);
      return false;
    }
  }

  /**
   * Load specific automation rule
   * @param {string} automationId - Unique ID
   * @returns {Object|null} Automation rules or null if not found
   */
  load(automationId) {
    try {
      const allAutomations = this.loadAll();
      return allAutomations[automationId] || null;
    } catch (error) {
      console.error('Failed to load automation:', error);
      return null;
    }
  }

  /**
   * Load all automation rules
   * @returns {Object} Map of automationId -> rules
   */
  loadAll() {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.AUTOMATIONS);
      return data ? JSON.parse(data) : {};
    } catch (error) {
      console.error('Failed to load all automations:', error);
      return {};
    }
  }

  /**
   * Delete automation rule
   * @param {string} automationId - Unique ID
   */
  delete(automationId) {
    try {
      const allAutomations = this.loadAll();
      delete allAutomations[automationId];
      localStorage.setItem(STORAGE_KEYS.AUTOMATIONS, JSON.stringify(allAutomations));
      return true;
    } catch (error) {
      console.error('Failed to delete automation:', error);
      return false;
    }
  }

  /**
   * Update automation status
   * @param {string} automationId - Unique ID
   * @param {string} status - New status
   */
  updateStatus(automationId, status) {
    try {
      const automation = this.load(automationId);
      if (automation) {
        automation.status = status;
        automation.updatedAt = new Date().toISOString();
        this.save(automationId, automation);
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to update automation status:', error);
      return false;
    }
  }

  /**
   * Get automations by position symbol
   * @param {string} symbol - Product symbol (e.g., "C-BTC-92000-100126")
   * @returns {Array} Array of automations for this position
   */
  getByPosition(symbol) {
    try {
      const allAutomations = this.loadAll();
      return Object.values(allAutomations).filter((a) => a.position?.symbol === symbol);
    } catch (error) {
      console.error('Failed to get automations by position:', error);
      return [];
    }
  }

  /**
   * Get active automations (not inactive or completed)
   * @returns {Array} Array of active automations
   */
  getActive() {
    try {
      const allAutomations = this.loadAll();
      return Object.values(allAutomations).filter(
        (a) => a.status !== 'inactive' && a.status !== 'completed'
      );
    } catch (error) {
      console.error('Failed to get active automations:', error);
      return [];
    }
  }

  /**
   * Export all automations as JSON
   * @returns {string} JSON string
   */
  export() {
    try {
      const allAutomations = this.loadAll();
      return JSON.stringify(allAutomations, null, 2);
    } catch (error) {
      console.error('Failed to export automations:', error);
      return '{}';
    }
  }

  /**
   * Import automations from JSON
   * @param {string} jsonData - JSON string
   * @returns {boolean} Success status
   */
  import(jsonData) {
    try {
      const automations = JSON.parse(jsonData);
      localStorage.setItem(STORAGE_KEYS.AUTOMATIONS, JSON.stringify(automations));
      return true;
    } catch (error) {
      console.error('Failed to import automations:', error);
      return false;
    }
  }

  /**
   * Clear all automations
   */
  clearAll() {
    try {
      localStorage.removeItem(STORAGE_KEYS.AUTOMATIONS);
      return true;
    } catch (error) {
      console.error('Failed to clear automations:', error);
      return false;
    }
  }

  /**
   * Clear completed automations older than X days
   * @param {number} daysOld - Number of days (default: 30)
   */
  clearOldCompleted(daysOld = 30) {
    try {
      const allAutomations = this.loadAll();
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - daysOld);

      const filtered = Object.fromEntries(
        Object.entries(allAutomations).filter(([id, automation]) => {
          if (automation.status !== 'completed') return true;
          const updatedAt = new Date(automation.updatedAt);
          return updatedAt > cutoffDate;
        })
      );

      localStorage.setItem(STORAGE_KEYS.AUTOMATIONS, JSON.stringify(filtered));
      return true;
    } catch (error) {
      console.error('Failed to clear old completed automations:', error);
      return false;
    }
  }
}

// Singleton instance
const automationStorage = new AutomationStorage();
export default automationStorage;
