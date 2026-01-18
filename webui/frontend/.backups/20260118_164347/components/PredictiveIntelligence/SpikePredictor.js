import React, { useState, useEffect } from 'react';

const SpikePredictor = () => {
  const [prediction, setPrediction] = useState(null);
  const [warning, setWarning] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPrediction = async () => {
    try {
      const response = await fetch('/api/prediction/spike-forecast');
      const data = await response.json();
      
      if (data.available && data.prediction) {
        setPrediction(data.prediction);
      } else {
        setPrediction(null);
      }
      
      // Also check for early warning
      const warningResponse = await fetch('/api/prediction/early-warning');
      const warningData = await warningResponse.json();
      
      if (warningData.available && warningData.warning) {
        setWarning(warningData.warning);
      } else {
        setWarning(null);
      }
      
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrediction();
    const interval = setInterval(fetchPrediction, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const getAlertColor = (alertLevel) => {
    switch (alertLevel) {
      case 'HIGH': return '#ff4444';
      case 'MEDIUM': return '#ffaa00';
      case 'LOW': return '#44ff44';
      default: return '#888';
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '20px', backgroundColor: '#1e1e1e', color: '#fff', borderRadius: '8px' }}>
        <h3>🧠 Predictive Intelligence</h3>
        <p>Loading spike prediction...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px', backgroundColor: '#1e1e1e', color: '#fff', borderRadius: '8px' }}>
        <h3>🧠 Predictive Intelligence</h3>
        <p style={{ color: '#ff4444' }}>Error: {error}</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', backgroundColor: '#1e1e1e', color: '#fff', borderRadius: '8px' }}>
      <h3>🧠 Predictive Intelligence</h3>
      
      {/* Early Warning Alert */}
      {warning && (
        <div style={{
          backgroundColor: '#ff4444',
          color: '#fff',
          padding: '15px',
          borderRadius: '8px',
          marginBottom: '20px',
          border: '2px solid #ff6666'
        }}>
          <h4>⚠️ EARLY WARNING</h4>
          <p><strong>{warning.message}</strong></p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '10px' }}>
            <div>Confidence: <strong>{warning.confidence}</strong></div>
            <div>Pattern: <strong>{warning.pattern}</strong></div>
            <div>Current IV: <strong>{warning.current_iv}</strong></div>
            <div>Predicted IV: <strong>{warning.predicted_iv}</strong></div>
          </div>
        </div>
      )}

      {/* Prediction Details */}
      {prediction ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div>
            <h4>Spike Forecast</h4>
            <div style={{ marginBottom: '10px' }}>
              <span style={{
                color: prediction.will_spike ? '#ff4444' : '#44ff44',
                fontWeight: 'bold'
              }}>
                {prediction.will_spike ? '📈 SPIKE PREDICTED' : '📊 NO SPIKE'}
              </span>
            </div>
            <div>Confidence: <strong style={{ color: getAlertColor(prediction.alert_level) }}>
              {(prediction.confidence * 100).toFixed(1)}%
            </strong></div>
            <div>Time Horizon: <strong>{prediction.minutes_ahead} minutes</strong></div>
            <div>Pattern: <strong>{prediction.pattern_match}</strong></div>
          </div>
          
          <div>
            <h4>IV Analysis</h4>
            <div>Current IV: <strong>{prediction.current_iv}%</strong></div>
            <div>Predicted IV: <strong>{prediction.predicted_iv}%</strong></div>
            <div>Spike Threshold: <strong>{prediction.spike_threshold}%</strong></div>
            <div>Alert Level: <strong style={{ color: getAlertColor(prediction.alert_level) }}>
              {prediction.alert_level}
            </strong></div>
          </div>
        </div>
      ) : (
        <div style={{ textAlign: 'center', color: '#888', padding: '20px' }}>
          <p>Insufficient data for prediction</p>
          <p>Collecting volatility patterns...</p>
        </div>
      )}
      
      <div style={{ marginTop: '20px', fontSize: '12px', color: '#888' }}>
        Last updated: {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
};

export default SpikePredictor;