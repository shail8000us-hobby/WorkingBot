/**
 * Trading Simulator - What-if scenario testing
 */

import React, { useState, useCallback } from 'react';
import styles from './TradingSimulator.module.css';

interface SimulationResult {
  success: boolean;
  action: string;
  reason: string;
  details: Record<string, any>;
}

interface Props {
  instance: string;
}

export const TradingSimulator: React.FC<Props> = ({ instance }) => {
  const [price, setPrice] = useState<string>('');
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);

  const simulateAction = useCallback(async () => {
    if (!price) return;

    setLoading(true);
    try {
      const response = await fetch('/api/brain/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instance,
          scenario: 'price_move',
          params: { new_price: parseFloat(price) }
        })
      });

      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Simulation error:', error);
      setResult({
        success: false,
        action: 'ERROR',
        reason: error instanceof Error ? error.message : 'Simulation failed',
        details: {}
      });
    } finally {
      setLoading(false);
    }
  }, [instance, price]);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>🎮 Trading Simulator</h2>
        <p>Test what the bot would do in different scenarios</p>
      </div>

      <div className={styles.inputSection}>
        <label className={styles.label}>
          What if price moves to:
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="Enter price (e.g., 92500)"
            className={styles.input}
            step="0.01"
          />
        </label>

        <button
          onClick={simulateAction}
          disabled={!price || loading}
          className={styles.simulateButton}
        >
          {loading ? 'Simulating...' : 'Simulate'}
        </button>
      </div>

      {result && (
        <div className={`${styles.result} ${result.success ? styles.success : styles.error}`}>
          <h3>📊 Simulation Result</h3>
          
          <div className={styles.resultCard}>
            <div className={styles.resultHeader}>
              <span className={styles.resultAction}>{result.action}</span>
              <span className={styles.resultStatus}>
                {result.success ? '✅ Success' : '❌ Blocked'}
              </span>
            </div>
            
            <p className={styles.resultReason}>{result.reason}</p>

            {result.details && Object.keys(result.details).length > 0 && (
              <div className={styles.details}>
                <h4>Details:</h4>
                {Object.entries(result.details).map(([key, value]) => (
                  <div key={key} className={styles.detailRow}>
                    <span className={styles.detailKey}>{key}:</span>
                    <span className={styles.detailValue}>{String(value)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <div className={styles.presetScenarios}>
        <h3>Quick Scenarios</h3>
        <div className={styles.scenarioButtons}>
          <button onClick={() => setPrice('90000')} className={styles.scenarioButton}>
            📉 Price drops to 90k
          </button>
          <button onClick={() => setPrice('95000')} className={styles.scenarioButton}>
            📈 Price rises to 95k
          </button>
          <button onClick={() => setPrice('92000')} className={styles.scenarioButton}>
            🎯 At grid level 92k
          </button>
        </div>
      </div>
    </div>
  );
};
