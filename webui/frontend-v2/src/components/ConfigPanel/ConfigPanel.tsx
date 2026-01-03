/**
 * ConfigPanel - Configuration Editor
 * 
 * Edit bot configuration with categories and validation.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import styles from './ConfigPanel.module.css';

interface ConfigField {
  key: string;
  value: string | number | boolean;
  type: 'string' | 'number' | 'boolean';
  description?: string;
  category: string;
}

interface ConfigCategory {
  name: string;
  icon: string;
  fields: ConfigField[];
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

export const ConfigPanel: React.FC = () => {
  const { selectedInstanceId, withInstance, selectedInstance } = useInstance();
  const [config, setConfig] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [hasChanges, setHasChanges] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, any>>({});

  // Config categories with their fields
  const categories: ConfigCategory[] = [
    {
      name: 'grid',
      icon: '📊',
      fields: [
        { key: 'grid.num_levels', value: 0, type: 'number', description: 'Number of grid levels', category: 'grid' },
        { key: 'grid.spacing_percent', value: 0, type: 'number', description: 'Grid spacing percentage', category: 'grid' },
        { key: 'grid.order_size', value: 0, type: 'number', description: 'Order size per level', category: 'grid' },
        { key: 'grid.take_profit_percent', value: 0, type: 'number', description: 'Take profit percentage', category: 'grid' },
        { key: 'grid.stop_loss_percent', value: 0, type: 'number', description: 'Stop loss percentage', category: 'grid' },
      ]
    },
    {
      name: 'safety',
      icon: '🛡️',
      fields: [
        { key: 'safety.max_position_size', value: 0, type: 'number', description: 'Maximum position size', category: 'safety' },
        { key: 'safety.max_daily_loss', value: 0, type: 'number', description: 'Maximum daily loss', category: 'safety' },
        { key: 'safety.volatility_pause', value: true, type: 'boolean', description: 'Pause on high volatility', category: 'safety' },
        { key: 'safety.rsi.enabled', value: true, type: 'boolean', description: 'Enable RSI safety', category: 'safety' },
        { key: 'safety.rsi.period', value: 14, type: 'number', description: 'RSI period', category: 'safety' },
        { key: 'safety.rsi.long_threshold', value: 30, type: 'number', description: 'RSI long threshold', category: 'safety' },
        { key: 'safety.rsi.short_threshold', value: 70, type: 'number', description: 'RSI short threshold', category: 'safety' },
      ]
    },
    {
      name: 'trading',
      icon: '💹',
      fields: [
        { key: 'trading.enabled', value: true, type: 'boolean', description: 'Enable trading', category: 'trading' },
        { key: 'trading.mode', value: 'LONG', type: 'string', description: 'Trading mode (LONG/SHORT)', category: 'trading' },
        { key: 'trading.leverage', value: 1, type: 'number', description: 'Leverage multiplier', category: 'trading' },
        { key: 'trading.symbol', value: '', type: 'string', description: 'Trading symbol', category: 'trading' },
      ]
    },
    {
      name: 'guardian',
      icon: '👁️',
      fields: [
        { key: 'guardian.enabled', value: true, type: 'boolean', description: 'Enable guardian mode', category: 'guardian' },
        { key: 'guardian.check_interval', value: 30, type: 'number', description: 'Check interval (seconds)', category: 'guardian' },
        { key: 'guardian.auto_restart', value: true, type: 'boolean', description: 'Auto restart on errors', category: 'guardian' },
      ]
    },
    {
      name: 'notifications',
      icon: '🔔',
      fields: [
        { key: 'notifications.telegram.enabled', value: false, type: 'boolean', description: 'Enable Telegram notifications', category: 'notifications' },
        { key: 'notifications.telegram.chat_id', value: '', type: 'string', description: 'Telegram chat ID', category: 'notifications' },
        { key: 'notifications.email.enabled', value: false, type: 'boolean', description: 'Enable email notifications', category: 'notifications' },
      ]
    },
  ];

  // Fetch config
  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(withInstance(`${API_BASE}/api/yaml-config`));
      const data = await response.json();
      if (data.success) {
        setConfig(data.data || {});
        setEditedValues(data.data || {});
      } else {
        setError(data.error || 'Failed to load config');
      }
    } catch (err) {
      setError(`Failed to fetch config: ${err}`);
    } finally {
      setLoading(false);
    }
  }, [withInstance]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig, selectedInstanceId]);

  // Get value from nested config
  const getConfigValue = (key: string): any => {
    const parts = key.split('.');
    let value: any = editedValues;
    for (const part of parts) {
      if (value && typeof value === 'object') {
        value = value[part];
      } else {
        return undefined;
      }
    }
    return value;
  };

  // Set value in nested config
  const setConfigValue = (key: string, newValue: any) => {
    const parts = key.split('.');
    const newConfig = JSON.parse(JSON.stringify(editedValues));
    let current: any = newConfig;
    
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]]) {
        current[parts[i]] = {};
      }
      current = current[parts[i]];
    }
    
    current[parts[parts.length - 1]] = newValue;
    setEditedValues(newConfig);
    setHasChanges(true);
  };

  // Save config
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/yaml-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: editedValues })
      });
      
      const data = await response.json();
      if (data.success) {
        setSuccess('Configuration saved successfully!');
        setHasChanges(false);
        setConfig(editedValues);
        setTimeout(() => setSuccess(null), 3000);
      } else {
        setError(data.error || 'Failed to save config');
      }
    } catch (err) {
      setError(`Failed to save config: ${err}`);
    } finally {
      setSaving(false);
    }
  };

  // Reset changes
  const handleReset = () => {
    setEditedValues(config);
    setHasChanges(false);
  };

  // Filter fields by search
  const getFilteredFields = (category: ConfigCategory) => {
    if (!searchQuery) return category.fields;
    return category.fields.filter(field => 
      field.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      field.description?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  };

  // Render field input
  const renderField = (field: ConfigField) => {
    const value = getConfigValue(field.key);
    
    if (field.type === 'boolean') {
      return (
        <label className={styles.toggleLabel}>
          <input
            type="checkbox"
            checked={value === true}
            onChange={(e) => setConfigValue(field.key, e.target.checked)}
          />
          <span className={styles.toggleSwitch}></span>
        </label>
      );
    }
    
    if (field.type === 'number') {
      return (
        <input
          type="number"
          className={styles.input}
          value={value ?? ''}
          onChange={(e) => setConfigValue(field.key, parseFloat(e.target.value) || 0)}
        />
      );
    }
    
    return (
      <input
        type="text"
        className={styles.input}
        value={value ?? ''}
        onChange={(e) => setConfigValue(field.key, e.target.value)}
      />
    );
  };

  if (loading) {
    return (
      <div className={styles.panel}>
        <div className={styles.loading}>Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>⚙️ Configuration</h2>
        <div className={styles.headerActions}>
          <input
            type="text"
            placeholder="Search settings..."
            className={styles.searchInput}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button 
            className={styles.refreshBtn}
            onClick={fetchConfig}
            title="Refresh"
          >
            🔄
          </button>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}
      {success && <div className={styles.success}>{success}</div>}

      <div className={styles.content}>
        {/* Category tabs */}
        <div className={styles.categoryTabs}>
          {categories.map(cat => (
            <button
              key={cat.name}
              className={`${styles.categoryTab} ${activeCategory === cat.name ? styles.active : ''}`}
              onClick={() => setActiveCategory(cat.name)}
            >
              <span className={styles.catIcon}>{cat.icon}</span>
              <span className={styles.catName}>{cat.name}</span>
            </button>
          ))}
        </div>

        {/* Fields for active category */}
        <div className={styles.fieldsSection}>
          {categories
            .filter(cat => cat.name === activeCategory)
            .map(cat => (
              <div key={cat.name} className={styles.categoryFields}>
                <h3>{cat.icon} {cat.name.charAt(0).toUpperCase() + cat.name.slice(1)} Settings</h3>
                
                {getFilteredFields(cat).length === 0 ? (
                  <p className={styles.noResults}>No matching settings found</p>
                ) : (
                  <div className={styles.fieldsList}>
                    {getFilteredFields(cat).map(field => (
                      <div key={field.key} className={styles.fieldRow}>
                        <div className={styles.fieldInfo}>
                          <span className={styles.fieldKey}>{field.key}</span>
                          {field.description && (
                            <span className={styles.fieldDesc}>{field.description}</span>
                          )}
                        </div>
                        <div className={styles.fieldValue}>
                          {renderField(field)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
        </div>
      </div>

      {/* Action buttons */}
      <div className={styles.actions}>
        <button
          className={styles.resetBtn}
          onClick={handleReset}
          disabled={!hasChanges}
        >
          ↩️ Reset
        </button>
        <button
          className={`${styles.saveBtn} ${hasChanges ? styles.hasChanges : ''}`}
          onClick={handleSave}
          disabled={!hasChanges || saving}
        >
          {saving ? '💾 Saving...' : '💾 Save Changes'}
        </button>
      </div>
    </div>
  );
};

export default ConfigPanel;
