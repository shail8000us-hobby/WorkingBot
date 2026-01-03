/**
 * Decision Flow Graph - Visual flowchart of bot's decision logic
 */

import React from 'react';
import styles from './DecisionFlowGraph.module.css';

interface DecisionNode {
  id: string;
  type: 'decision' | 'action' | 'check';
  label: string;
  realtime_data?: Record<string, any>;
}

interface DecisionEdge {
  source: string;
  target: string;
  label?: string;
}

interface Props {
  nodes: DecisionNode[];
  edges: DecisionEdge[];
}

export const DecisionFlowGraph: React.FC<Props> = ({ nodes, edges }) => {
  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'decision': return '❓';
      case 'action': return '⚡';
      case 'check': return '🔍';
      default: return '●';
    }
  };

  const getNodeColor = (node: DecisionNode) => {
    if (!node.realtime_data) return 'var(--node-default)';
    
    // Color based on status
    if (node.realtime_data.emergency_stop) return 'var(--error-color)';
    if (node.realtime_data.trading_enabled === false) return 'var(--warning-color)';
    if (node.realtime_data.volatility_safe === false) return 'var(--warning-color)';
    
    return 'var(--success-color)';
  };

  return (
    <div className={styles.container}>
      <div className={styles.graph}>
        {nodes.map((node, index) => (
          <div key={node.id} className={styles.nodeContainer}>
            <div 
              className={styles.node}
              style={{ borderColor: getNodeColor(node) }}
            >
              <div className={styles.nodeIcon}>{getNodeIcon(node.type)}</div>
              <div className={styles.nodeLabel}>{node.label}</div>
              
              {node.realtime_data && (
                <div className={styles.realtimeData}>
                  {Object.entries(node.realtime_data).map(([key, value]) => (
                    <div key={key} className={styles.dataRow}>
                      <span className={styles.dataKey}>{key}:</span>
                      <span className={styles.dataValue}>
                        {typeof value === 'boolean' ? (value ? '✅' : '❌') : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* Edge to next node */}
            {index < nodes.length - 1 && (
              <div className={styles.edge}>
                <div className={styles.edgeLine} />
                {edges[index]?.label && (
                  <div className={styles.edgeLabel}>{edges[index].label}</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {nodes.length === 0 && (
        <div className={styles.empty}>
          <p>No decision nodes found</p>
          <span className={styles.hint}>Bot may not be running or code not analyzed</span>
        </div>
      )}
    </div>
  );
};
