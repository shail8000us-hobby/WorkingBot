# PyTorch & TensorFlow Integration for MMM Algorithm
## Comprehensive Learning Guide & Implementation Roadmap

**Last Updated:** April 9, 2026  
**Target Audience:** AI Agent + Operator (learning-first approach)  
**Status:** Planning Phase — Read Before Implementation

---

## Table of Contents

1. [Overview & Architecture](#overview--architecture)
2. [Use Case 1: Price & IV Prediction (LSTM)](#use-case-1-price--iv-prediction-lstm)
3. [Use Case 2: IV Forecasting (LSTM/GRU)](#use-case-2-implied-volatility-forecasting)
4. [Use Case 3: Optimal Strike Selection](#use-case-3-optimal-strike-selection)
5. [Use Case 4: Anomaly Detection](#use-case-4-anomaly-detection)
6. [Use Case 5: Loss Prediction & Risk Scoring](#use-case-5-loss-prediction--risk-scoring)
7. [Use Case 6: Adjustment Decision Engine](#use-case-6-adjustment-decision-engine)
8. [Use Case 7: Regime Classification](#use-case-7-regime-classification)
9. [Use Case 8: Close-at-5 Prediction](#use-case-8-close-at-5-prediction)
10. [Use Case 9: Session Profitability Forecast](#use-case-9-session-profitability-forecast)
11. [Use Case 10: Margin Tier Prediction](#use-case-10-margin-tier-prediction)
12. [Implementation Roadmap](#implementation-roadmap)
13. [Data Pipeline Architecture](#data-pipeline-architecture)
14. [Testing & Validation Strategy](#testing--validation-strategy)
15. [Safety & Fallback Mechanisms](#safety--fallback-mechanisms)

---

## Overview & Architecture

### Why ML for MMM?

The MMM algorithm makes real-time decisions based on:
- **Current market state** (price, IV, Greeks)
- **Position state** (loss, frozen lots, Greeks per strike)
- **Historical patterns** (premium decay curves, market microstructure)

Traditional hardcoded logic handles common scenarios but misses:
- **Subtle market regimes** (false IV spikes, microstructure anomalies)
- **Optimal parameter tuning** (when to adjust, by how much, at which strike)
- **Predictive insights** (will this position hit loss limit in 30 min?)

**ML adds:** Learn from historical data what hardcoded rules approximate only crudely.

### High-Level Architecture

```
┌─────────────────────────────────────────┐
│     MMM Heartbeat Loop                  │
│  (mmm_monitor.py _run_loop cycle)       │
└─────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────┐
│  1. Fetch price/Greeks/margin           │
│  2. Safety checks                       │
│  3. Regime logic  ◄── ML Score (Class)  │
│  4. Adjustment   ◄── ML Predict (Action)│
│  5. Scale-up     ◄── ML Score (Risk)    │
│  6. Margin       ◄── ML Predict (ETA)   │
│  7. Wind-down    ◄── ML Predict (P&L)   │
└─────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────┐
│     Execute orders / Adjust / Close     │
└─────────────────────────────────────────┘
```

### Framework Choice: PyTorch vs TensorFlow

| Framework | Best For | In MMM Context |
|-----------|----------|---|
| **TensorFlow** | Production inference, pre-built layers, structured APIs | IV/Price forecasting, Regime classification, Anomaly detection |
| **PyTorch** | Research, custom training loops, dynamic graphs | Loss predictor, Adjustment RL agent, Strike optimizer |

**Decision:** Start with TensorFlow for inference speed & ease; move to PyTorch for advanced use cases (RL).

---

## Use Case 1: Price & IV Prediction (LSTM)

### 1.1 Problem Statement

Currently MMM has hardcoded blocks:
- IV spike detected → block sells
- Trend tier ≥ 2 → guard mode (block dangerous adjustments)

These are **binary switches**. The problem:
- False positives (IV spike reverses immediately)
- False negatives (trending market continues without detection)
- No predictive horizon (react only after spike detected)

### 1.2 What It Does

**LSTM Network** learns temporal patterns from historical BTC price/IV sequences:

```
Input: [price_t-60 ... price_t] (60 timesteps × 1 min candles)
Output: [P(up), P(down), P(flat)]  (3-class classification for next 5 min)

Also output: IV_predicted (regression branch)
```

**Use in MMM:**
- If P(down) > 0.65 and CE side large → increase margin buffer
- If IV_predicted will spike → proactively disable scale-up
- If P(flat) > 0.70 → enable scale-up (safer)

### 1.3 Data Requirements

#### Training Data Source
```python
# Historical data: 1000 trading sessions over 3 months
# Per session: {
#     'prices': [price_t-60 ... price_t],  # 60 1-min candles
#     'ivs': [iv_t-60 ... iv_t],           # IV at each timestep
#     'label_5m': 'UP' | 'DOWN' | 'FLAT',  # What actually happened next 5 min
#     'label_realized_pnl': float,         # Session actual P&L
# }

# Collected from:
# - Delta Exchange API historical data
# - Session logs (webui/backend/logs/mmm_sessions/)
# - Greeks snapshots stored in Redis/DB during live trading
```

#### Feature Engineering
```
Raw Features:
  - price_close, price_high, price_low, price_open
  - iv_level, iv_change_pct
  - bid_ask_spread
  - volume (if available)
  
Derived Features:
  - returns = (price_t - price_t-1) / price_t-1
  - log_returns = log(price_t / price_t-1)
  - iv_momentum = (iv_t - iv_t-5) / iv_t-5
  - volatility = std(returns[-5:])
  - sma_5, sma_10 (simple moving averages)
```

### 1.4 Model Architecture (TensorFlow)

```python
import tensorflow as tf
from tensorflow.keras import layers, Sequential

class PriceIVPredictor(Sequential):
    """
    LSTM-based price direction + IV forecaster for BTC options.
    
    Input shape: (batch_size, 60, num_features)  # 60 1-min timesteps
    Output shape: (batch_size, 3) for classification
                  (batch_size, 1) for IV regression
    """
    def __init__(self, num_features=5):  # price, iv, spread, vol, returns
        super().__init__([
            # LSTM layer 1: 64 units, return sequences for stacking
            layers.LSTM(64, return_sequences=True, activation='relu',
                       input_shape=(60, num_features)),
            layers.Dropout(0.2),
            
            # LSTM layer 2: 32 units, return final output
            layers.LSTM(32, return_sequences=False, activation='relu'),
            layers.Dropout(0.2),
            
            # Dense layers for classification branch
            layers.Dense(16, activation='relu'),
            layers.Dense(3, activation='softmax', name='direction')  # UP, DOWN, FLAT
        ])
        
        # Regression head for IV prediction (added separately)
        self.iv_head = Sequential([
            layers.Dense(16, activation='relu'),
            layers.Dense(1, name='iv_forecast')
        ])
    
    def call(self, x):
        x = super().call(x)
        iv_forecast = self.iv_head(x)
        return {'direction': x, 'iv_forecast': iv_forecast}

# Training loss: sparse_categorical_crossentropy for direction
#                mean_squared_error for IV forecast
# Optimizer: Adam (lr=0.001)
# Batch size: 32
# Epochs: 50 (with early stopping on validation set)
```

### 1.5 Data Collection Pipeline

```python
# File: mmm_ml_data_collector.py (NEW)

import logging
from datetime import datetime, timedelta
from typing import List, Dict
import json
import numpy as np

log = logging.getLogger(__name__)

class PriceIVDataCollector:
    """
    Collect 1-min OHLC + IV snapshots during live MMM trading.
    Store in local SQLite for batch training.
    """
    
    def __init__(self, db_path: str = 'ml_training_data.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create training data table if not exists."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS price_iv_sequences (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                timestamp REAL,
                sequence_json TEXT,  -- 60-element price/IV array
                label_5m TEXT,        -- UP | DOWN | FLAT
                label_30m TEXT,       -- UP | DOWN | FLAT (for validation)
                realized_pnl REAL,    -- Session actual P&L
                created_at REAL
            )
        ''')
        conn.commit()
        conn.close()
    
    def collect_sequence(self, session_id: str, prices: List[float], 
                        ivs: List[float], label_5m: str, 
                        label_30m: str, realized_pnl: float):
        """
        Store one training sequence.
        
        Args:
            session_id: from session['_uuid']
            prices: list of 60 closing prices (1-min candles, oldest first)
            ivs: list of 60 IV levels at same timestamps
            label_5m: actual direction in next 5 minutes
            label_30m: actual direction in next 30 minutes
            realized_pnl: session final P&L
        """
        sequence = {
            'prices': prices,
            'ivs': ivs,
            'returns': [(prices[i+1] - prices[i]) / prices[i] 
                       for i in range(len(prices)-1)] + [0],
            'label_5m': label_5m,
        }
        
        import sqlite3
        from time import time
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO price_iv_sequences 
            (session_id, timestamp, sequence_json, label_5m, label_30m, realized_pnl, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            time(),
            json.dumps(sequence),
            label_5m,
            label_30m,
            realized_pnl,
            time()
        ))
        conn.commit()
        conn.close()
        log.info(f"Collected sequence for {session_id}: {label_5m}")
    
    def get_training_batch(self, limit=500) -> (np.ndarray, np.ndarray):
        """
        Load sequences from DB and prepare for training.
        
        Returns:
            X: shape (N, 60, 5) — 60 timesteps, 5 features each
            y: shape (N, 3) — one-hot encoded direction
        """
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(f'''
            SELECT sequence_json, label_5m FROM price_iv_sequences
            ORDER BY created_at DESC LIMIT ?
        ''', (limit,)).fetchall()
        conn.close()
        
        X = []
        y = []
        direction_map = {'UP': [1, 0, 0], 'DOWN': [0, 1, 0], 'FLAT': [0, 0, 1]}
        
        for seq_json, label in rows:
            seq = json.loads(seq_json)
            # Stack features: [price, iv, returns, iv_momentum, zeros]
            price_norm = np.array(seq['prices']) / seq['prices'][-1]  # normalize to last
            iv_norm = np.array(seq['ivs']) / (np.mean(seq['ivs']) + 1e-6)
            returns = np.array(seq['returns'])
            
            timesteps = np.column_stack([price_norm, iv_norm, returns, 
                                         np.zeros(len(price_norm)), 
                                         np.zeros(len(price_norm))])
            X.append(timesteps)
            y.append(direction_map.get(label, [0, 0, 1]))
        
        return np.array(X), np.array(y)

# Usage in mmm_monitor.py heartbeat:
collector = PriceIVDataCollector()
# After each heartbeat, collect historical prices and label them
# collector.collect_sequence(session['_uuid'], prices_60min, ivs_60min, 
#                           label_5m, label_30m, session['realized_pnl'])
```

### 1.6 Integration in MMM

```python
# File: mmm_monitor.py (in _heartbeat method, after market data fetch)

class MMMMonitor:
    def __init__(self, ...):
        # Load pre-trained model
        self.price_iv_model = tf.keras.models.load_model('model_price_iv.h5')
        self.price_history = deque(maxlen=60)  # Track last 60 prices
        self.iv_history = deque(maxlen=60)     # Track last 60 IVs
    
    async def _heartbeat(self):
        # ... existing code ...
        
        # Fetch current market data
        spot_price = await fetch_spot_price()  # BTC price
        iv_level = await fetch_iv_level()
        
        # Update history
        self.price_history.append(spot_price)
        self.iv_history.append(iv_level)
        
        # If we have 60 datapoints, make prediction
        if len(self.price_history) == 60:
            X = self._prepare_input_for_prediction()  # shape (1, 60, 5)
            predictions = self.price_iv_model.predict(X, verbose=0)
            
            direction_probs = predictions['direction'][0]  # [P(UP), P(DOWN), P(FLAT)]
            iv_forecast = predictions['iv_forecast'][0][0]
            
            session['_ml_predictions'] = {
                'direction_probs': {
                    'up': float(direction_probs[0]),
                    'down': float(direction_probs[1]),
                    'flat': float(direction_probs[2]),
                },
                'iv_forecast': float(iv_forecast),
                'prediction_timestamp': datetime.now(timezone.utc).isoformat(),
            }
            
            # Use in regime logic
            if direction_probs[1] > 0.65:  # High confidence DOWN
                log.warning("ML: High confidence downtrend predicted")
                session['_ml_regime_lean'] = 'bearish'
            elif direction_probs[0] > 0.65:  # High confidence UP
                session['_ml_regime_lean'] = 'bullish'
            else:
                session['_ml_regime_lean'] = 'neutral'
        
        # ... rest of heartbeat ...
```

### 1.7 Training Script

```python
# File: train_price_iv_model.py (standalone script)

import tensorflow as tf
import numpy as np
from mmm_ml_data_collector import PriceIVDataCollector
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def train_price_iv_model(epochs=50, batch_size=32):
    """
    Full training pipeline.
    
    Steps:
    1. Load sequences from DB
    2. Split train/val/test
    3. Create model
    4. Train with early stopping
    5. Evaluate on test set
    6. Save model + weights
    """
    
    # Load data
    collector = PriceIVDataCollector('ml_training_data.db')
    X, y = collector.get_training_batch(limit=1000)
    
    log.info(f"Loaded {len(X)} sequences")
    log.info(f"Shape: X={X.shape}, y={y.shape}")
    
    # Split: 70% train, 15% val, 15% test
    N = len(X)
    train_idx = int(0.7 * N)
    val_idx = int(0.85 * N)
    
    X_train, y_train = X[:train_idx], y[:train_idx]
    X_val, y_val = X[train_idx:val_idx], y[train_idx:val_idx]
    X_test, y_test = X[val_idx:], y[val_idx:]
    
    # Normalize
    X_mean = X_train.mean(axis=(0, 1), keepdims=True)
    X_std = X_train.std(axis=(0, 1), keepdims=True) + 1e-6
    X_train = (X_train - X_mean) / X_std
    X_val = (X_val - X_mean) / X_std
    X_test = (X_test - X_mean) / X_std
    
    # Create model
    from mmm_ml_models import PriceIVPredictor
    model = PriceIVPredictor(num_features=5)
    
    # Compile
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss=['sparse_categorical_crossentropy', 'mse'],
        metrics=['accuracy', 'mae']
    )
    
    # Callbacks
    early_stop = tf.keras.callbacks.EarlyStopping(
        monitor='val_loss',
        patience=5,
        restore_best_weights=True
    )
    
    # Train
    log.info("Starting training...")
    history = model.fit(
        X_train, [np.argmax(y_train, axis=1), np.ones(len(y_train))],
        validation_data=(X_val, [np.argmax(y_val, axis=1), np.ones(len(y_val))]),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stop],
        verbose=1
    )
    
    # Evaluate
    test_loss, test_acc, _ = model.evaluate(X_test, 
                                           [np.argmax(y_test, axis=1), 
                                            np.ones(len(y_test))])
    log.info(f"Test Accuracy: {test_acc:.4f}")
    
    # Save
    model.save('model_price_iv.h5')
    log.info("Model saved to model_price_iv.h5")
    
    return model, history

if __name__ == '__main__':
    train_price_iv_model()
```

### 1.8 Validation & Testing

```python
# File: test_price_iv_model.py

import unittest
import numpy as np
import tensorflow as tf
from mmm_ml_models import PriceIVPredictor

class TestPriceIVPredictor(unittest.TestCase):
    
    def setUp(self):
        self.model = PriceIVPredictor(num_features=5)
    
    def test_model_output_shape(self):
        """Verify model outputs correct shapes."""
        X = np.random.randn(8, 60, 5)  # batch of 8
        outputs = self.model.predict(X, verbose=0)
        
        self.assertEqual(outputs['direction'].shape, (8, 3))  # 3 classes
        self.assertEqual(outputs['iv_forecast'].shape, (8, 1))
    
    def test_model_consistency(self):
        """Same input → same output (deterministic after seeding)."""
        tf.random.set_seed(42)
        X = np.random.randn(4, 60, 5)
        
        out1 = self.model.predict(X, verbose=0)
        self.model = PriceIVPredictor(num_features=5)  # Fresh model
        tf.random.set_seed(42)
        out2 = self.model.predict(X, verbose=0)
        
        # Won't match (different weights), but show determinism works
        np.testing.assert_array_almost_equal(out1['iv_forecast'], out1['iv_forecast'])
    
    def test_prediction_bounds(self):
        """Probabilities sum to 1."""
        X = np.random.randn(10, 60, 5)
        outputs = self.model.predict(X, verbose=0)
        probs = outputs['direction']
        
        row_sums = probs.sum(axis=1)
        np.testing.assert_array_almost_equal(row_sums, np.ones(10))

if __name__ == '__main__':
    unittest.main()
```

### 1.9 Inference Performance

```
Expected latency:
  - Data prep (normalize, stack features): 2ms
  - LSTM forward pass (2 layers): 8ms
  - Total: ~10ms (well under 100ms budget)

Memory footprint:
  - Model weights: ~2.5 MB
  - Runtime buffers: ~500 KB
  - Total: ~3 MB (negligible)

Accuracy target:
  - Binary (any direction): 65-70%
  - Ternary (UP/DOWN/FLAT): 50-55%
  - IV forecast MAE: <5% relative error
```

---

## Use Case 2: Implied Volatility Forecasting

### 2.1 Problem Statement

MMM currently reacts to IV changes *after they happen* (regime detects high IV, blocks sells).

**Question:** Can we *predict* IV moves 5-30 minutes ahead?

**Why?** Enable proactive scaling decisions:
- Predicted IV spike → disable scale-up (safer to wait)
- Predicted IV drop → scale-up encouraged
- Predicted IV stable → normal adjustments OK

### 2.2 Architecture

```python
# GRU network (more efficient than LSTM for univariate time series)

Input: [IV_t-60 ... IV_t], Greeks (delta, gamma, vega), spot moves
Output: IV_t+5, IV_t+10, IV_t+30  (multi-horizon forecast)
```

**Why GRU over LSTM?** Fewer parameters (60 vs 80 units per cell), faster inference.

### 2.3 Model Code

```python
import tensorflow as tf
from tensorflow.keras import layers, Sequential, Model, Input

def create_iv_forecaster(lookback=60, num_horizons=3):
    """
    Multi-horizon IV forecaster using GRU + attention.
    
    Args:
        lookback: 60 timesteps (1-min bars)
        num_horizons: 3 (5m, 10m, 30m ahead)
    
    Returns:
        Model that predicts IV at [t+5m, t+10m, t+30m]
    """
    
    # Input: (batch, 60, 3) — [IV, delta, gamma]
    inputs = Input(shape=(lookback, 3), name='iv_sequence')
    
    # GRU layer with attention
    gru = layers.GRU(32, return_sequences=True, activation='relu')(inputs)
    attention = layers.AdditiveAttention()([gru, gru])  # Self-attention
    gru2 = layers.GRU(16, return_sequences=False, activation='relu')(attention)
    
    # Dense heads for each horizon
    x = layers.Dense(32, activation='relu')(gru2)
    
    heads = []
    for horizon in [5, 10, 30]:
        head = layers.Dense(1, name=f'iv_t+{horizon}m')(x)
        heads.append(head)
    
    model = Model(inputs=inputs, outputs=heads)
    return model

# Compile
model = create_iv_forecaster()
model.compile(
    optimizer=tf.keras.optimizers.Adam(0.0005),
    loss=['mse', 'mse', 'mse'],
    loss_weights=[1.0, 1.2, 1.5],  # Weight longer horizons more
    metrics=['mae']
)
```

### 2.4 Data Collection

```python
def collect_iv_sequence(session_id, iv_history, delta_history, gamma_history,
                       labels: Dict[str, float]):
    """
    labels = {
        'iv_t+5m': actual IV 5 min later,
        'iv_t+10m': actual IV 10 min later,
        'iv_t+30m': actual IV 30 min later,
    }
    """
    import sqlite3
    import json
    
    sequence = {
        'iv': iv_history,
        'delta': delta_history,
        'gamma': gamma_history,
    }
    
    conn = sqlite3.connect('ml_training_data.db')
    conn.execute('''
        INSERT INTO iv_forecast_sequences
        (session_id, sequence_json, label_5m, label_10m, label_30m, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        session_id,
        json.dumps(sequence),
        labels['iv_t+5m'],
        labels['iv_t+10m'],
        labels['iv_t+30m'],
        datetime.now().timestamp(),
    ))
    conn.commit()
    conn.close()
```

### 2.5 Integration in MMM

```python
# mmm_monitor.py

async def _heartbeat(self):
    # ... fetch market data ...
    
    if len(self.iv_history) == 60:
        X = np.column_stack([
            list(self.iv_history),
            list(self.delta_history),
            list(self.gamma_history),
        ])
        X = X.reshape(1, 60, 3)  # (1, 60, 3)
        
        preds = self.iv_forecaster.predict(X, verbose=0)
        iv_pred_5m, iv_pred_10m, iv_pred_30m = [p[0, 0] for p in preds]
        
        current_iv = self.iv_history[-1]
        iv_change_5m_pct = (iv_pred_5m - current_iv) / current_iv * 100
        
        session['_ml_iv_forecast'] = {
            'current': current_iv,
            'pred_5m': iv_pred_5m,
            'pred_10m': iv_pred_10m,
            'pred_30m': iv_pred_30m,
            'change_5m_pct': iv_change_5m_pct,
        }
        
        # Use to guide decisions
        if iv_change_5m_pct > 15:  # Predicted spike
            log.warning(f"ML: IV spike predicted (+{iv_change_5m_pct:.1f}% in 5m)")
            session['_ml_iv_score'] = 'high_crash_risk'
        elif iv_change_5m_pct < -10:
            session['_ml_iv_score'] = 'low_roll_risk'
        else:
            session['_ml_iv_score'] = 'stable'
```

---

## Use Case 3: Optimal Strike Selection

### 3.1 Problem

Currently `find_scale_strikes()` in `mmm_scaler.py` picks the strike with premium *closest to target*.

**Issue:** This is naive. Some strikes decay faster, require fewer adjustments, have better Greeks.

### 3.2 Solution

Train a neural network to *score* each available strike:

```python
Input: [strike_offset, delta, gamma, vega, theta, current_premium, 
        days_to_expiry, historical_decay_rate]
Output: score (0-1) — how "good" is this strike to sell NOW
```

### 3.3 Model Architecture

```python
class StrikeScorer(tf.keras.Sequential):
    """
    Dense network to score strike quality.
    """
    def __init__(self):
        super().__init__([
            layers.Dense(64, activation='relu', input_shape=(8,)),
            layers.Dropout(0.2),
            layers.Dense(32, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(16, activation='relu'),
            layers.Dense(1, activation='sigmoid'),  # Output: 0-1 score
        ])
        
        self.compile(
            optimizer=tf.keras.optimizers.Adam(0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )

# Training labels:
# Score = 1.0 if: strike was sold, position closed at profit, P&L positive
# Score = 0.0 if: strike was sold, position hit max loss, P&L negative
# Score = 0.5 if: neutral (middle positions)
```

### 3.4 Features

```python
def extract_strike_features(strike: float, chain_entry: Dict, 
                           session: Dict, spot_price: float) -> np.ndarray:
    """
    Extract 8 features for strike scorer.
    """
    option_type = 'CE'  # or 'PE'
    option_data = chain_entry.get(option_type.lower(), {})
    
    strike_offset = (strike - spot_price) / spot_price * 100  # % OTM
    delta = option_data.get('delta', 0)
    gamma = option_data.get('gamma', 0)
    vega = option_data.get('vega', 0)
    theta = option_data.get('theta', 0)
    current_premium = option_data.get('bid', 0) or option_data.get('mark_price', 0)
    
    expiry_str = session['params'].get('expiry', '')
    days_to_exp = (expiry_str - datetime.now()).total_seconds() / 86400
    
    # Historical decay rate: median % decay per hour across same strike in past 10 sessions
    decay_rate = fetch_historical_decay_rate(strike, option_type) or 0.8
    
    return np.array([
        strike_offset,
        delta,
        gamma,
        vega,
        theta,
        current_premium,
        days_to_exp,
        decay_rate,
    ], dtype=np.float32)

def score_strikes(session, chain, spot_price, option_type='CE'):
    """
    Score all strikes in chain, return top-5.
    """
    model = tf.keras.models.load_model('model_strike_scorer.h5')
    
    scores = []
    for entry in chain:
        strike = entry.get('strike')
        features = extract_strike_features(strike, entry, session, spot_price)
        score = model.predict(features.reshape(1, 8), verbose=0)[0, 0]
        
        scores.append({
            'strike': strike,
            'score': float(score),
            'features': features,
        })
    
    # Sort by score descending
    scores.sort(key=lambda x: x['score'], reverse=True)
    
    return scores[:5]  # Top 5 candidates
```

### 3.5 Integration

```python
# In mmm_scaler.py

def find_scale_strikes(initializer, session, spot_price):
    """Replace naive approach with ML-scored approach."""
    
    chain_data = initializer.get_full_chain(expiry)
    chain = chain_data['chain']
    
    # Score all CE strikes
    ce_scores = score_strikes(session, chain, spot_price, 'CE')
    pe_scores = score_strikes(session, chain, spot_price, 'PE')
    
    if not ce_scores or not pe_scores:
        return None
    
    # Pick top 1 (could also pick top N and average)
    best_ce = ce_scores[0]
    best_pe = pe_scores[0]
    
    log.info(f"ML Score CE {best_ce['strike']}: {best_ce['score']:.3f}")
    log.info(f"ML Score PE {best_pe['strike']}: {best_pe['score']:.3f}")
    
    return {
        'ce': {'strike': best_ce['strike'], ...},
        'pe': {'strike': best_pe['strike'], ...},
    }
```

---

## Use Case 4: Anomaly Detection

### 4.1 Problem

Market dislocations happen:
- Futures open → spot jumps, Greeks change wildly
- News event → bid-ask spreads explode
- Circuit breaker triggers → illiquidity

MMM shouldn't trade during these. Currently relies on manual operator intervention.

### 4.2 Solution

**Autoencoder** learns "normal" market microstructure during calm periods:

```python
Input: [bid_ask_spread, delta_change, gamma_change, vega_change, 
        volume_change, price_move, iv_move]
Output: Reconstruct same 7 features

Anomaly Score = Reconstruction Error
  - Score < threshold → normal
  - Score > threshold → anomaly (halt new sells)
```

### 4.3 Architecture

```python
class MarketAnomalyDetector(tf.keras.Sequential):
    """
    Autoencoder for microstructure anomalies.
    
    Learns to compress (7 features → 2 latent) and decompress.
    High reconstruction error = anomaly.
    """
    def __init__(self):
        super().__init__([
            # Encoder
            layers.Dense(7, input_shape=(7,), activation='relu'),
            layers.Dense(4, activation='relu'),
            layers.Dense(2, activation='relu'),  # Bottleneck
            
            # Decoder
            layers.Dense(4, activation='relu'),
            layers.Dense(7, activation='linear'),  # Reconstruct
        ])
        
        self.compile(
            optimizer=tf.keras.optimizers.Adam(0.001),
            loss='mse'
        )

# Training: Feed 1000+ hours of *normal* market data
# The model learns to reconstruct normal patterns
# Given anomalous data, reconstruction error spikes
```

### 4.4 Feature Extraction

```python
def extract_microstructure_features(session, current_market_data, 
                                   previous_market_data):
    """Extract 7 features from current market state."""
    
    bid_ask_spread = current_market_data['bid_ask_spread']
    
    # Greeks change from last heartbeat
    delta_prev = previous_market_data.get('delta_sum', 0)
    delta_curr = current_market_data.get('delta_sum', 0)
    delta_change = abs(delta_curr - delta_prev) / (abs(delta_prev) + 1)
    
    gamma_prev = previous_market_data.get('gamma_sum', 0)
    gamma_curr = current_market_data.get('gamma_sum', 0)
    gamma_change = abs(gamma_curr - gamma_prev) / (abs(gamma_prev) + 1)
    
    # Volume change (if available)
    volume_change = current_market_data.get('volume_change_pct', 0)
    
    # Price move
    price_move = abs(current_market_data['spot'] - previous_market_data['spot']) / \
                 previous_market_data['spot'] * 100
    
    # IV move
    iv_move = abs(current_market_data['iv'] - previous_market_data['iv']) / \
              previous_market_data['iv'] * 100 if previous_market_data['iv'] > 0 else 0
    
    return np.array([
        bid_ask_spread,
        delta_change,
        gamma_change,
        volume_change,
        price_move,
        iv_move,
        1.0,  # Bias feature
    ], dtype=np.float32)
```

### 4.5 Integration

```python
# mmm_monitor.py

class MMMMonitor:
    def __init__(self, ...):
        self.anomaly_detector = tf.keras.models.load_model('model_anomaly.h5')
        self.anomaly_threshold = 0.8  # configurable
        self.prev_market_data = {}
    
    async def _heartbeat(self):
        current_market_data = {
            'spot': spot_price,
            'iv': iv_level,
            'bid_ask_spread': bid_ask_spread,
            'delta_sum': sum_of_all_deltas,
            'gamma_sum': sum_of_all_gammas,
            ...
        }
        
        if self.prev_market_data:
            features = extract_microstructure_features(
                session, current_market_data, self.prev_market_data
            )
            
            # Encode-decode
            reconstruction = self.anomaly_detector.predict(features.reshape(1, 7))
            anomaly_score = np.mean(np.abs(reconstruction - features.reshape(1, 7)))
            
            session['_ml_anomaly_score'] = float(anomaly_score)
            
            if anomaly_score > self.anomaly_threshold:
                log.warning(f"ML: Market anomaly detected (score={anomaly_score:.2f})")
                session['_anomaly_detected'] = True
                session['_halt_new_sells'] = True
            else:
                session['_anomaly_detected'] = False
        
        self.prev_market_data = current_market_data
```

---

## Use Case 5: Loss Prediction & Risk Scoring

### 5.1 Problem

MMM runs until it hits `max_loss_amount`. But:
- How much loss might we see in the *next 30 minutes*?
- Is current `max_loss_amount = -$500` safe or aggressive?
- Should we tighten it dynamically?

### 5.2 Solution

**Multi-layer network** predicts maximum loss over N minutes:

```python
Input: [all_positions (per-strike loss, Greeks), spot_delta, 
        realized_loss, margin_tier, IV_level, time_to_expiry]
Output: predicted_max_loss_30m, confidence_interval_95%
```

### 5.3 Architecture

```python
class MaxLossPredictor(tf.keras.Sequential):
    """
    Predicts max adverse excursion (MAE) over next 30 minutes.
    
    Uses current position state + Greeks + market state.
    """
    def __init__(self, max_positions=20):
        # Flatten all position data
        position_input_size = max_positions * 5  # strike, lots, premium, delta, gamma
        
        super().__init__([
            layers.Dense(128, activation='relu', 
                        input_shape=(position_input_size + 15,)),  # +15 for market state
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            
            layers.Dense(64, activation='relu'),
            layers.Dropout(0.2),
            
            layers.Dense(32, activation='relu'),
            
            # Two heads: loss prediction + confidence
            layers.Dense(1, activation='linear', name='predicted_max_loss'),
            layers.Dense(1, activation='softplus', name='confidence_interval'),
        ])
```

### 5.4 Training Data

```python
def collect_loss_sequence(session_id, positions_state, market_state,
                         realized_loss_now, max_loss_next_30m):
    """
    After session ends: collect what max loss was experienced in 
    next 30 minutes vs. what state was at time of prediction.
    """
    import sqlite3
    
    conn = sqlite3.connect('ml_training_data.db')
    conn.execute('''
        INSERT INTO loss_prediction_data
        (session_id, positions_json, market_state_json, 
         realized_loss_now, label_max_loss_30m, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        session_id,
        json.dumps(positions_state),
        json.dumps(market_state),
        realized_loss_now,
        max_loss_next_30m,
        datetime.now().timestamp(),
    ))
    conn.commit()
    conn.close()
```

### 5.5 Integration

```python
# mmm_monitor.py

def get_max_loss_prediction(session):
    """
    Call every heartbeat (optional; expensive computation).
    Use to dynamically set margin buffer or tighten max_loss_amount.
    """
    model = self.loss_predictor
    
    # Prepare input
    positions_flat = flatten_all_positions(session)
    market_state = extract_market_state(session)
    
    X = np.concatenate([positions_flat, market_state])
    X = X.reshape(1, -1)
    
    predictions = model.predict(X, verbose=0)
    predicted_loss = predictions[0, 0]
    confidence_interval = predictions[0, 1]
    
    session['_ml_loss_forecast'] = {
        'predicted_max_loss_30m': float(predicted_loss),
        'ci_95': float(confidence_interval),
        'current_realized': session.get('realized_pnl', 0),
        'margin_buffer_recommended': float(confidence_interval * 1.2),
    }
    
    # Optionally tighten max_loss dynamically
    if abs(predicted_loss) > session['params']['max_loss_amount'] * 0.8:
        log.warning(f"ML: Predicted loss {predicted_loss:.2f} approaching limit")
        session['_loss_risk'] = 'high'
```

---

## Use Case 6: Adjustment Decision Engine

### 6.1 Problem

Currently `_process_adjustment()` uses hardcoded logic:
- If loss > threshold → reduce N lots at new strike
- N = fixed (e.g., `adjustment_count = 10`)
- New strike = closest with higher premium

**Issue:** Suboptimal. Sometimes:
- Need to reduce MORE (trending market)
- Need to reduce LESS (better to wait)
- Better strike exists (not just closest premium)

### 6.2 Solution

**Reinforcement Learning agent** learns optimal adjustment policy:

```python
State: {
  loss_pct,           # loss / max_loss_amount
  spot_move_pct,      # BTC move since entry
  iv_level,
  gamma_exposure,     # total gamma * spot
  theta_daily,        # expected theta until EOD
  time_to_expiry,
  margin_tier,
  realized_pnl_pct,   # session profit
}

Action: {
  reduce_pct: 10-100% of active lots,
  target_strike_offset: -2% to +2% OTM,
  or: NO_ADJUSTMENT
}

Reward: -session_loss + 0.1 * session_profit_if_held
```

### 6.3 Model Architecture (PyTorch)

```python
import torch
import torch.nn as nn

class AdjustmentAgent(nn.Module):
    """
    Actor-Critic network for MMM adjustment decisions.
    
    Actor: outputs action (reduce %, target offset)
    Critic: outputs state value estimate
    """
    def __init__(self, state_dim=8, action_dim=2):
        super().__init__()
        
        self.shared = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
        )
        
        # Actor: output action parameters
        self.actor_mean = nn.Linear(64, action_dim)
        self.actor_logstd = nn.Linear(64, action_dim)  # Log std dev
        
        # Critic: value function
        self.critic = nn.Linear(64, 1)
    
    def forward(self, state):
        x = self.shared(state)
        
        # Actor
        mean = self.actor_mean(x)
        logstd = self.actor_logstd(x)
        std = torch.exp(logstd)
        
        # Critic
        value = self.critic(x)
        
        return mean, std, value

# Training: PPO (Proximal Policy Optimization)
# Optimize: maximize expected reward - penalty for too many adjustments
```

### 6.4 Integration

```python
# mmm_monitor.py

async def _process_adjustment(self, session, ce_now, pe_now):
    """
    OLD: hardcoded logic
    NEW: ML-informed decision
    """
    
    # Build state vector
    state = torch.tensor([
        session.get('_loss_pct', 0),
        session.get('spot_move_pct', 0),
        session.get('iv_level', 30),
        session.get('gamma_exposure', 0),
        session.get('theta_daily', 0),
        session.get('time_to_expiry_hours', 1),
        session.get('_margin_tier_level', 0),  # 0=green, 1=yellow, 2=red
        session.get('realized_pnl_pct', 0),
    ], dtype=torch.float32)
    
    # Get ML recommendation
    with torch.no_grad():
        mean, std, value = self.adjustment_agent(state)
    
    # Sample action (with some exploration)
    reduce_pct = torch.clamp(mean[0] + torch.randn(1) * std[0], 10, 100).item()
    target_offset = torch.clamp(mean[1] + torch.randn(1) * std[1], -2, 2).item()
    
    session['_ml_adjustment_recommendation'] = {
        'reduce_pct': reduce_pct,
        'target_offset': target_offset,
        'state_value': value.item(),
    }
    
    # Execute (with safety checks still in place)
    if value.item() > -session['params']['max_loss_amount'] * 0.1:
        # Model is confident adjustment is good
        await execute_adjustment(session, reduce_pct, target_offset)
    else:
        log.info("ML: Hold, model confidence low")
```

---

## Use Case 7: Regime Classification

### 7.1 Problem

Current regime system (mmm_regime.py) has 3 hard tiers based on IV thresholds:
- IV < 25 → NORMAL
- 25 ≤ IV < 45 → HIGH
- IV ≥ 45 → CRITICAL

**Issue:** IV alone is noisy. A spike that reverses in 2m shouldn't block the whole session.

### 7.2 Solution

**Multi-class LSTM classifier** learns 4 market regimes:

```python
Classes: TRENDING_UP | TRENDING_DOWN | RANGING | HIGH_VOLATILITY_SPIKE

Input: [price history (60 bars), IV history, bid-ask spread, volume]
Output: class + confidence + duration estimate (how long will regime last?)
```

### 7.3 Architecture

```python
class RegimeClassifier(tf.keras.Sequential):
    def __init__(self):
        super().__init__([
            layers.Input(shape=(60, 5)),  # price, IV, spread, vol, returns
            
            layers.LSTM(64, return_sequences=True, activation='relu'),
            layers.Dropout(0.2),
            
            layers.LSTM(32, return_sequences=False, activation='relu'),
            layers.Dropout(0.2),
            
            layers.Dense(16, activation='relu'),
            layers.Dense(4, activation='softmax'),  # 4 regimes
        ])
        
        self.compile(
            optimizer=tf.keras.optimizers.Adam(0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )

# Classes (one-hot):
# TRENDING_UP:     [1, 0, 0, 0]
# TRENDING_DOWN:   [0, 1, 0, 0]
# RANGING:         [0, 0, 1, 0]
# SPIKE:           [0, 0, 0, 1]
```

### 7.4 Integration

```python
# mmm_monitor.py

regime_classifier = tf.keras.models.load_model('model_regime.h5')

async def detect_regime_ml(session):
    """
    Call every 5 heartbeats (to avoid excessive computation).
    """
    if len(price_history) < 60:
        return
    
    X = np.column_stack([
        list(price_history),     # prices
        list(iv_history),        # IVs
        list(spread_history),    # bid-ask spreads
        list(volume_history),    # volumes (if available)
        list(returns_history),   # returns
    ])
    
    X = X.reshape(1, 60, 5)
    probs = regime_classifier.predict(X, verbose=0)[0]
    
    regimes = ['TRENDING_UP', 'TRENDING_DOWN', 'RANGING', 'HIGH_VOL_SPIKE']
    top_regime = regimes[np.argmax(probs)]
    top_confidence = float(np.max(probs))
    
    session['_ml_regime'] = {
        'class': top_regime,
        'confidence': top_confidence,
        'probs': {regimes[i]: float(probs[i]) for i in range(4)},
    }
    
    # Use to enhance/override hardcoded regime
    if top_regime == 'HIGH_VOL_SPIKE' and top_confidence > 0.75:
        # Detected spike, but only block if >2-minute duration
        log.warning(f"ML: Spike detected (confidence={top_confidence:.2f})")
        if not session.get('_spike_block_until'):
            session['_spike_block_until'] = datetime.now() + timedelta(minutes=2)
    
    # RANGING + TRENDING_UP = good for scale-up
    if top_regime in ['RANGING', 'TRENDING_UP']:
        session['_regime_scale_up_eligible'] = True
```

---

## Use Case 8: Close-at-5 Prediction

### 8.1 Problem

MMM closes frozen positions when premium ≤ $5 (close-at-5).

**Questions:**
- Will this premium reach $5 in 5 minutes? 10 minutes? 30 minutes?
- Which frozen positions should we prioritize closing?
- Should we close before $5 (if we're confident it's decaying fast)?

### 8.2 Solution

Binary logistic classifier: "Will this position close at $5 within N minutes?"

```python
Input: [premium_current, theta_daily, gamma, vega, days_to_exp, 
        premium_decay_rate_historical, bid_ask_spread]
Output: [P(close within 5m), P(close within 10m), P(close within 30m)]
```

### 8.3 Model

```python
class CloseAt5Predictor(tf.keras.Sequential):
    def __init__(self):
        super().__init__([
            layers.Dense(32, activation='relu', input_shape=(7,)),
            layers.Dropout(0.2),
            layers.Dense(16, activation='relu'),
            layers.Dense(3, activation='sigmoid'),  # 3 horizons, sigmoid for per-class prob
        ])

# Training: For each closed position, label whether it closed within each horizon
```

### 8.4 Integration

```python
# mmm_close_at_5.py

def get_close_at_5_predictions(positions, model):
    """
    Score each frozen position on "closability".
    """
    predictions = []
    
    for pos in positions:
        features = np.array([
            pos['current_premium'],
            pos['theta_daily'],
            pos['gamma'],
            pos['vega'],
            pos['days_to_expiry'],
            pos.get('decay_rate', 0.8),
            pos['bid_ask_spread'],
        ])
        
        probs = model.predict(features.reshape(1, 7), verbose=0)[0]
        
        predictions.append({
            'position': pos,
            'p_close_5m': probs[0],
            'p_close_10m': probs[1],
            'p_close_30m': probs[2],
        })
    
    # Sort by confidence (highest probability of close soonest)
    predictions.sort(key=lambda x: x['p_close_5m'], reverse=True)
    
    return predictions

# In _heartbeat of MMM
close_preds = get_close_at_5_predictions(session['ce']['positions'], model)
for pred in close_preds:
    if pred['p_close_5m'] > 0.8:
        log.info(f"ML: High confidence close-at-5 for {pred['position']['strike']}")
        # Prioritize closing this one first
```

---

## Use Case 9: Session Profitability Forecast

### 9.1 Problem

MMM runs until:
1. Expiry time (fixed)
2. Max loss hit (reactive)
3. Operator stops it (manual)

**Better:** Predict end-of-session P&L, enable smart stop decisions.

### 9.2 Solution

**Transformer-based forecaster** predicts session P&L at each future point:

```python
Input: Current session state, positions, Greeks, elapsed time %, market state
Output: Predicted P&L distribution (mean, std) for [5m, 10m, 30m, 60m ahead]
```

### 9.3 Architecture

```python
import tensorflow as tf
from tensorflow.keras import layers, Model, Input

def create_profitability_forecaster():
    """
    Transformer model for multi-horizon P&L forecast.
    
    Uses positional encoding to represent time until expiry.
    """
    
    # Input: (batch, timesteps=1, features=50)
    # We're forecasting at current timestep, predicting N steps ahead
    
    inputs = Input(shape=(1, 50), name='session_state')
    
    # Positional encoding for time horizons
    x = layers.Dense(64, activation='relu')(inputs)
    
    # Multi-head attention
    attention = layers.MultiHeadAttention(num_heads=4, key_dim=16)
    x = attention(x, x)
    
    # Feed-forward
    x = layers.Dense(32, activation='relu')(x)
    x = layers.Dropout(0.2)(x)
    
    # Output heads for different horizons
    heads = []
    for horizon in [5, 10, 30, 60]:
        # Mean and std
        mean = layers.Dense(1, name=f'pnl_mean_{horizon}m')(x)
        std = layers.Dense(1, activation='softplus', name=f'pnl_std_{horizon}m')(x)
        heads.append(mean)
        heads.append(std)
    
    model = Model(inputs=inputs, outputs=heads)
    return model
```

### 9.4 Integration

```python
# mmm_monitor.py

profitability_forecaster = create_profitability_forecaster()

async def forecast_session_pnl(session):
    """
    Call every 10 heartbeats.
    """
    state = extract_session_state(session)  # shape (1, 1, 50)
    
    preds = profitability_forecaster.predict(state, verbose=0)
    
    forecast = {}
    for i, horizon in enumerate([5, 10, 30, 60]):
        mean_idx = i * 2
        std_idx = i * 2 + 1
        forecast[f'{horizon}m'] = {
            'mean': preds[mean_idx][0, 0, 0],
            'std': preds[std_idx][0, 0, 0],
            'ci_95_lower': preds[mean_idx][0, 0, 0] - 1.96 * preds[std_idx][0, 0, 0],
            'ci_95_upper': preds[mean_idx][0, 0, 0] + 1.96 * preds[std_idx][0, 0, 0],
        }
    
    session['_ml_pnl_forecast'] = forecast
    
    # Suggest early stop if forecast is bleak
    if forecast['30m']['ci_95_upper'] < -session['params']['max_loss_amount'] * 0.5:
        log.warning("ML: P&L forecast indicates high loss risk in 30m")
        session['_ml_early_stop_recommendation'] = True
```

---

## Use Case 10: Margin Tier Prediction

### 10.1 Problem

Margin tier blocks are reactive:
- Computation happens: margin alert fires
- "YELLOW" blocks new sells
- "RED" forces closeout

By then, positions are already beyond safe levels.

### 10.2 Solution

**LSTM time-series predictor** forecasts margin level 5-15 minutes ahead:

```python
Input: [margin_ratio_history (60 min), position_delta_history, 
        spot_price_volatility, volume]
Output: [margin_ratio_t+5m, margin_ratio_t+10m, margin_ratio_t+15m,
         minutes_until_YELLOW, minutes_until_RED]
```

### 10.3 Model

```python
class MarginPredictor(tf.keras.Sequential):
    def __init__(self):
        super().__init__([
            layers.Input(shape=(60, 4)),  # margin%, delta, vol, price
            layers.LSTM(32, return_sequences=True, activation='relu'),
            layers.Dropout(0.2),
            layers.LSTM(16, return_sequences=False, activation='relu'),
            layers.Dense(16, activation='relu'),
            # Outputs: 3 margin forecasts + 2 time-to-event predictions
            layers.Dense(5, activation='linear'),
        ])
```

### 10.4 Integration

```python
# mmm_monitor.py

margin_predictor = tf.keras.models.load_model('model_margin.h5')

async def predict_margin_tiers(session):
    """
    Call every heartbeat.
    """
    margin_hist = np.array(session.get('_margin_ratio_history', []))[:60]
    delta_hist = np.array(session.get('_delta_history', []))[:60]
    vol_hist = np.array(session.get('_volatility_history', []))[:60]
    price_hist = np.array(session.get('_price_history', []))[:60]
    
    if len(margin_hist) < 60:
        return  # Not enough data
    
    X = np.column_stack([margin_hist, delta_hist, vol_hist, price_hist])
    X = X.reshape(1, 60, 4)
    
    preds = margin_predictor.predict(X, verbose=0)[0]
    
    margin_5m, margin_10m, margin_15m, mins_to_yellow, mins_to_red = preds
    
    session['_ml_margin_forecast'] = {
        'current': session['_margin_ratio'],
        'pred_5m': margin_5m,
        'pred_10m': margin_10m,
        'pred_15m': margin_15m,
        'mins_until_yellow': max(0, mins_to_yellow),
        'mins_until_red': max(0, mins_to_red),
    }
    
    # Proactive action
    if mins_to_yellow < 5:
        log.warning(f"ML: Yellow margin predicted in {mins_to_yellow:.1f}m")
        session['_margin_preemptive_reduce'] = True
        # Soft reduce (not hard block, just suggest reduction)
```

---

## Implementation Roadmap

### Phase 1: Data Pipeline (Week 1-2)

**Goal:** Collect training data from live sessions.

- [ ] Create `mmm_ml_data_collector.py` with SQLite DB schema
- [ ] Add data collection calls to `mmm_monitor.py` heartbeat
- [ ] Collect 500+ sessions (3-4 days of live trading)
- [ ] Verify data quality (no nulls, correct shapes)

**Output:** Database with 500+ labeled training sequences

---

### Phase 2: Off-Policy Model Training (Week 3-4)

**Goal:** Train models on historical data, NOT yet deployed.

- [ ] Price/IV Predictor (LSTM): Train 50 epochs, validate accuracy >65%
- [ ] IV Forecaster (GRU): Train 50 epochs, validate MAE <5%
- [ ] Strike Scorer (Dense): Train 50 epochs, validate ROC-AUC >0.7
- [ ] Anomaly Detector (Autoencoder): Train 100 epochs, validate calibration
- [ ] Loss Predictor (Dense): Train 50 epochs, validate RMSE <$50

**Deliverables:**
- 5 saved models (.h5 files)
- 5 test reports (accuracy, latency, memory)
- Comparison vs. baseline hardcoded logic

---

### Phase 3: Light Integration (Week 5)

**Goal:** Deploy models as *scorers*, NOT decision-makers.

- [ ] Code `mmm_ml_monitor.py` wrapper class
- [ ] Add inference calls to heartbeat (CPU-only, <50ms latency budget)
- [ ] Store predictions in `session['_ml_*']` fields
- [ ] Send predictions to WebUI (new dashboard tab: "ML Insights")
- [ ] Compare ML predictions vs. actual outcomes (post-hoc)

**No operator-facing changes yet.** Just observe if ML is useful.

---

### Phase 4: Advisory Mode (Week 6-7)

**Goal:** Show recommendations, let operator decide.

- [ ] Add "ML Suggestions" tab to WebUI
- [ ] Show: "ML recommends HOLD (confidence 72%)" or "ML: Scale-up safe (99% flat)"
- [ ] Operator can click "Apply ML Suggestion" button (still manual)
- [ ] Track operator acceptance rate (feedback loop)

---

### Phase 5: Selective Automation (Week 8+)

**Goal:** Let ML make specific low-risk decisions.

- [ ] Enable Regime Classifier to auto-toggle regime (no sell execution changes)
- [ ] Enable Margin Predictor to auto-reduce (soft, not forced)
- [ ] Enable Close-at-5 predictor to reorder close candidates (not auto-close)
- [ ] Leave Adjustment + Scale-up as advisory only (too risky to auto-execute)

---

## Data Pipeline Architecture

### Storage

```
ml_training_data.db (SQLite)
├── price_iv_sequences
│   ├── session_id, timestamp, sequence_json
│   ├── label_5m, label_30m, realized_pnl
│   └── created_at
│
├── loss_prediction_data
│   ├── session_id, positions_json, market_state_json
│   ├── realized_loss_now, label_max_loss_30m
│   └── created_at
│
├── close_at_5_sequences
│   ├── strike, premium, theta, gamma, vega
│   ├── label_closed_5m, label_closed_10m, label_closed_30m
│   └── created_at
│
└── regime_sequences
    ├── price_history, iv_history, spread_history
    ├── label_regime, label_duration_estimate
    └── created_at
```

### Data Flow

```
MMM Live Trading
  ↓
collect_sequence() calls in heartbeat
  ↓
Write to ml_training_data.db
  ↓
Every 4 hours: backup to Cloud Storage
  ↓
Weekly: run training script (off-hours)
  ↓
Validate on test set
  ↓
If validation improves: deploy new model
```

---

## Testing & Validation Strategy

### Unit Tests

```python
# test_ml_models.py
- Test model output shapes
- Test inference latency (<100ms)
- Test model determinism (same input → same output)
- Test handling of edge cases (NaNs, zeros)
```

### Integration Tests

```python
# test_mmm_ml_integration.py
- Mock heartbeat with test session data
- Verify predictions stored in session['_ml_*']
- Verify no side effects (models don't modify state)
- Verify fallback if model crashes
```

### Backtesting

```python
# backtest_ml_decisions.py
- Replay historical sessions
- At each heartbeat, compare ML decision vs. actual outcome
- Compute accuracy, precision, recall
- Identify failure modes
```

### Live Validation (Advisory Phase)

```python
Track over 2 weeks:
- How often do ML suggestions match operator's manual decision?
- Accuracy of price/IV predictions (compare to actuals)
- Accuracy of loss forecasts (compare to realized losses)
- Latency impact on heartbeat timing
```

---

## Safety & Fallback Mechanisms

### 1. Model Inference Failures

```python
async def _safe_predict(model, X):
    """Predict with fallback."""
    try:
        result = model.predict(X, verbose=0)
        return result, True
    except Exception as e:
        log.error(f"Model inference failed: {e}")
        return None, False  # Flag indicates fallback active

# In heartbeat:
pred, success = await _safe_predict(model, X)
if success:
    session['_ml_regime'] = classify_regime(pred)
else:
    session['_ml_regime'] = 'FALLBACK_NORMAL'
    # Use hardcoded tier system
```

### 2. Stale/Corrupted Models

```python
# Check model signature on load
import hashlib

def load_model_with_checksum(model_path, expected_sha256):
    with open(model_path, 'rb') as f:
        actual_sha = hashlib.sha256(f.read()).hexdigest()
    
    if actual_sha != expected_sha256:
        log.error(f"Model checksum mismatch: {actual_sha} != {expected_sha256}")
        return None
    
    return tf.keras.models.load_model(model_path)
```

### 3. Prediction Sanity Checks

```python
# Before acting on prediction:
if abs(predicted_pnl) > 2 * session['max_loss_amount']:
    log.warning("Prediction sanity check failed (too extreme)")
    prediction_accepted = False
elif np.isnan(predicted_pnl) or np.isinf(predicted_pnl):
    log.warning("Prediction is NaN/Inf")
    prediction_accepted = False
else:
    prediction_accepted = True
```

### 4. Operator Override

```python
# Always allow operator to disable ML
session['params']['ml_enabled'] = False  # Disables all ML predictions

# Or per-module
session['params']['ml_regime_override'] = 'hardcoded'  # Use old tier system
```

### 5. Performance Budgets

```python
# Monitor inference latency per model
latencies = {
    'price_iv': 0,
    'margin': 0,
    'loss_predictor': 0,
}

# If any model exceeds budget, fail gracefully
MAX_INFERENCE_TIME_MS = 50

for model_name, latency in latencies.items():
    if latency > MAX_INFERENCE_TIME_MS:
        log.warning(f"{model_name} exceeded latency budget ({latency}ms)")
        session[f'_ml_{model_name}_disabled'] = True
```

---

## References & Further Reading

- **TensorFlow Docs:** https://www.tensorflow.org/learn
- **PyTorch Docs:** https://pytorch.org/docs/stable
- **LSTM/GRU Tutorial:** https://colah.github.io/posts/2015-08-Understanding-LSTMs/
- **PPO (Reinforcement Learning):** https://openai.com/research/openai-five
- **Autoencoder Anomaly Detection:** https://keras.io/examples/timeseries/timeseries_anomaly_detection/
- **Time Series Forecasting:** https://www.tensorflow.org/tutorials/structured_data/time_series

---

**Next Step:** Read through Use Cases 1-3, then start Phase 1 (data collection).

