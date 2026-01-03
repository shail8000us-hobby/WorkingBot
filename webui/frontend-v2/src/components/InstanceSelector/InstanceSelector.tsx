/**
 * InstanceSelector - Dropdown for selecting trading instances
 * 
 * Shows all configured instances with status indicators.
 */

import React from 'react';
import { useInstance, Instance } from '../../contexts/InstanceContext';
import styles from './InstanceSelector.module.css';

interface InstanceSelectorProps {
  compact?: boolean;
}

export const InstanceSelector: React.FC<InstanceSelectorProps> = ({ compact = false }) => {
  const { 
    instances, 
    selectedInstanceId, 
    selectInstance, 
    loading,
    refreshInstances 
  } = useInstance();

  if (loading) {
    return (
      <div className={styles.container}>
        <span className={styles.loading}>Loading...</span>
      </div>
    );
  }

  if (instances.length === 0) {
    return (
      <div className={styles.container}>
        <span className={styles.noInstances}>No instances</span>
      </div>
    );
  }

  const getStatusClass = (instance: Instance): string => {
    if (!instance.enabled) return styles.disabled;
    return styles.enabled;
  };

  const getModeClass = (mode: string): string => {
    return mode === 'LONG' ? styles.long : styles.short;
  };

  if (compact) {
    return (
      <select 
        className={styles.select}
        value={selectedInstanceId || ''}
        onChange={(e) => selectInstance(e.target.value)}
      >
        {instances.map(instance => (
          <option key={instance.name} value={instance.name}>
            {instance.symbol} {instance.mode} {instance.enabled ? '●' : '○'}
          </option>
        ))}
      </select>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.label}>Instance</span>
        <button 
          className={styles.refreshBtn}
          onClick={() => refreshInstances()}
          title="Refresh instances"
        >
          🔄
        </button>
      </div>
      
      <div className={styles.instanceList}>
        {instances.map(instance => (
          <button
            key={instance.name}
            className={`${styles.instanceBtn} ${selectedInstanceId === instance.name ? styles.selected : ''} ${getStatusClass(instance)}`}
            onClick={() => selectInstance(instance.name)}
          >
            <span className={styles.symbol}>{instance.symbol}</span>
            <span className={`${styles.mode} ${getModeClass(instance.mode)}`}>
              {instance.mode}
            </span>
            <span className={`${styles.status} ${getStatusClass(instance)}`}>
              {instance.enabled ? '●' : '○'}
            </span>
          </button>
        ))}
      </div>
      
      {selectedInstanceId && (
        <div className={styles.selectedInfo}>
          <span className={styles.selectedLabel}>Selected:</span>
          <span className={styles.selectedValue}>{selectedInstanceId}</span>
        </div>
      )}
    </div>
  );
};

export default InstanceSelector;
