"""
Options Trading ML Model

Machine learning model to learn from historical options trades and
provide predictions and automation suggestions.

Features:
- Pattern recognition from trade history
- Win probability prediction
- Optimal entry/exit timing suggestions
- Strategy effectiveness analysis
- Automation rule generation

Created: January 14, 2026
"""

import os
import json
import pickle
import threading
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Data directory
DATA_DIR = Path(__file__).parent.parent / 'data'
MODEL_DIR = DATA_DIR / 'ml_models'
TRADES_FILE = DATA_DIR / 'options_trades.csv'

# Minimum trades needed for ML training
MIN_TRADES_FOR_TRAINING = 30
MIN_CLOSED_TRADES = 20


class OptionsMLModel:
    """
    Machine learning model for options trading pattern recognition.
    
    Uses historical trades to:
    1. Predict trade outcomes (win/loss probability)
    2. Identify optimal market conditions
    3. Suggest automation rules
    """
    
    def __init__(self):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        
        self.model = None
        self.scaler = None
        self.feature_columns = []
        self.model_metadata = {}
        self.is_trained = False
        
        # Try to load existing model
        self._load_model()
        
        print(f"✅ OptionsMLModel initialized. Trained: {self.is_trained}")
    
    def _get_feature_columns(self) -> List[str]:
        """Define features for ML model."""
        return [
            # Time features
            'hour_of_day',
            'day_of_week',
            # Option features
            'is_call',
            'is_buy',
            'days_to_expiry',
            'moneyness',
            'quantity',
            'price',
            # Greeks
            'iv',
            'delta',
            'gamma',
            'theta',
            'vega',
            # Market features
            'spot_change_1h',
            'spot_change_24h',
            'market_trend_encoded',
            'volatility_regime_encoded',
            # Position context
            'position_size_before',
        ]
    
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for ML model."""
        df = df.copy()
        
        # Time features
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour_of_day'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # Boolean features
        df['is_call'] = (df['option_type'] == 'Call').astype(int)
        df['is_buy'] = (df['action'] == 'BUY').astype(int)
        
        # Moneyness: (spot - strike) / strike for calls, (strike - spot) / strike for puts
        df['moneyness'] = df.apply(
            lambda r: (r['spot_price'] - r['strike']) / r['strike'] 
            if r['strike'] > 0 and r['option_type'] == 'Call'
            else (r['strike'] - r['spot_price']) / r['strike'] if r['strike'] > 0 
            else 0,
            axis=1
        )
        
        # Encode categorical features
        trend_map = {'bullish': 1, 'neutral': 0, 'bearish': -1}
        vol_map = {'low': 0, 'medium': 1, 'high': 2}
        
        df['market_trend_encoded'] = df['market_trend'].map(trend_map).fillna(0)
        df['volatility_regime_encoded'] = df['volatility_regime'].map(vol_map).fillna(1)
        
        # Fill NaN values
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)
        
        return df
    
    def _create_target(self, df: pd.DataFrame) -> pd.Series:
        """Create target variable (1 = profitable trade, 0 = losing trade)."""
        df['outcome_pnl'] = pd.to_numeric(df['outcome_pnl'], errors='coerce')
        return (df['outcome_pnl'] > 0).astype(int)
    
    def can_train(self) -> Tuple[bool, str]:
        """Check if we have enough data to train."""
        try:
            df = pd.read_csv(TRADES_FILE)
            total_trades = len(df)
            closed_trades = len(df[df['outcome_status'] == 'closed'])
            
            if total_trades < MIN_TRADES_FOR_TRAINING:
                return False, f"Need {MIN_TRADES_FOR_TRAINING} trades, have {total_trades}"
            
            if closed_trades < MIN_CLOSED_TRADES:
                return False, f"Need {MIN_CLOSED_TRADES} closed trades, have {closed_trades}"
            
            return True, f"Ready to train with {closed_trades} closed trades"
            
        except Exception as e:
            return False, f"Error checking data: {str(e)}"
    
    def train(self, force: bool = False) -> Dict:
        """
        Train the ML model on historical trades.
        
        Returns: Training metrics and status
        """
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        # Check if we can train
        can_train, message = self.can_train()
        if not can_train and not force:
            return {
                'success': False,
                'error': message,
                'trades_needed': MIN_TRADES_FOR_TRAINING,
            }
        
        try:
            # Load and prepare data
            df = pd.read_csv(TRADES_FILE)
            
            # Filter to closed trades only
            df = df[df['outcome_status'] == 'closed'].copy()
            
            if len(df) < 10:
                return {
                    'success': False,
                    'error': f"Not enough closed trades. Have {len(df)}, need at least 10.",
                }
            
            # Prepare features
            df = self._prepare_features(df)
            
            # Get feature columns
            self.feature_columns = self._get_feature_columns()
            
            # Ensure all feature columns exist
            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0
            
            X = df[self.feature_columns].values
            y = self._create_target(df).values
            
            # Handle class imbalance
            if len(np.unique(y)) < 2:
                return {
                    'success': False,
                    'error': 'Need both winning and losing trades to train.',
                }
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Train model (Gradient Boosting typically works well for this)
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                random_state=42
            )
            self.model.fit(X_train, y_train)
            
            # Evaluate
            y_pred = self.model.predict(X_test)
            y_prob = self.model.predict_proba(X_test)[:, 1]
            
            # Cross-validation score
            cv_scores = cross_val_score(self.model, X_scaled, y, cv=min(5, len(df) // 5))
            
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0),
                'f1_score': f1_score(y_test, y_pred, zero_division=0),
                'cv_mean': cv_scores.mean(),
                'cv_std': cv_scores.std(),
            }
            
            # Feature importance
            feature_importance = dict(zip(
                self.feature_columns,
                self.model.feature_importances_
            ))
            
            # Sort by importance
            feature_importance = dict(sorted(
                feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            ))
            
            # Save model metadata
            self.model_metadata = {
                'trained_at': datetime.now().isoformat(),
                'num_trades': len(df),
                'metrics': metrics,
                'feature_importance': feature_importance,
                'win_rate_actual': y.mean(),
            }
            
            # Save model
            self._save_model()
            self.is_trained = True
            
            return {
                'success': True,
                'metrics': metrics,
                'feature_importance': feature_importance,
                'num_trades_used': len(df),
                'message': f'Model trained successfully on {len(df)} trades',
            }
            
        except Exception as e:
            import traceback
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc(),
            }
    
    def predict(self, trade_params: Dict) -> Dict:
        """
        Predict outcome probability for a potential trade.
        
        Args:
            trade_params: Dict with trade parameters
            
        Returns:
            Dict with prediction and confidence
        """
        if not self.is_trained:
            return {
                'success': False,
                'error': 'Model not trained yet',
                'suggestion': 'Need more trades to train the model',
            }
        
        try:
            # Create single-row DataFrame
            df = pd.DataFrame([trade_params])
            df = self._prepare_features(df)
            
            # Ensure all feature columns exist
            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0
            
            X = df[self.feature_columns].values
            X_scaled = self.scaler.transform(X)
            
            # Predict
            prob = self.model.predict_proba(X_scaled)[0]
            win_prob = prob[1]
            
            # Determine suggestion
            if win_prob >= 0.7:
                suggestion = 'STRONG_BUY'
                confidence = 'high'
            elif win_prob >= 0.55:
                suggestion = 'BUY'
                confidence = 'medium'
            elif win_prob <= 0.3:
                suggestion = 'AVOID'
                confidence = 'high'
            elif win_prob <= 0.45:
                suggestion = 'CAUTION'
                confidence = 'medium'
            else:
                suggestion = 'NEUTRAL'
                confidence = 'low'
            
            return {
                'success': True,
                'win_probability': round(win_prob, 3),
                'loss_probability': round(1 - win_prob, 3),
                'suggestion': suggestion,
                'confidence': confidence,
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def analyze_patterns(self) -> Dict:
        """
        Analyze trading patterns from historical data.
        
        Returns insights about:
        - Best performing conditions
        - Worst performing conditions
        - Optimal trade timing
        - Strategy effectiveness
        """
        try:
            df = pd.read_csv(TRADES_FILE)
            df = df[df['outcome_status'] == 'closed'].copy()
            
            if len(df) < 10:
                return {
                    'success': False,
                    'error': 'Not enough closed trades for pattern analysis',
                }
            
            df = self._prepare_features(df)
            df['outcome_pnl'] = pd.to_numeric(df['outcome_pnl'], errors='coerce')
            df['is_winner'] = df['outcome_pnl'] > 0
            
            patterns = {}
            
            # Time-based patterns
            patterns['best_hours'] = df.groupby('hour_of_day')['is_winner'].mean().sort_values(ascending=False).head(3).to_dict()
            patterns['worst_hours'] = df.groupby('hour_of_day')['is_winner'].mean().sort_values().head(3).to_dict()
            
            patterns['best_days'] = df.groupby('day_of_week')['is_winner'].mean().sort_values(ascending=False).to_dict()
            
            # Option type patterns
            patterns['call_win_rate'] = df[df['is_call'] == 1]['is_winner'].mean()
            patterns['put_win_rate'] = df[df['is_call'] == 0]['is_winner'].mean()
            
            # Action patterns
            patterns['buy_win_rate'] = df[df['is_buy'] == 1]['is_winner'].mean()
            patterns['sell_win_rate'] = df[df['is_buy'] == 0]['is_winner'].mean()
            
            # Market condition patterns
            patterns['trend_performance'] = df.groupby('market_trend')['is_winner'].mean().to_dict()
            patterns['volatility_performance'] = df.groupby('volatility_regime')['is_winner'].mean().to_dict()
            
            # Moneyness patterns
            df['moneyness_bucket'] = pd.cut(df['moneyness'], bins=[-np.inf, -0.1, -0.02, 0.02, 0.1, np.inf], 
                                           labels=['deep_otm', 'otm', 'atm', 'itm', 'deep_itm'])
            patterns['moneyness_performance'] = df.groupby('moneyness_bucket')['is_winner'].mean().to_dict()
            
            # Days to expiry patterns
            df['dte_bucket'] = pd.cut(df['days_to_expiry'], bins=[0, 1, 3, 7, 14, np.inf],
                                     labels=['0dte', '1-3dte', '3-7dte', '7-14dte', '14+dte'])
            patterns['dte_performance'] = df.groupby('dte_bucket')['is_winner'].mean().to_dict()
            
            # Average PnL patterns
            patterns['avg_pnl_by_type'] = {
                'calls': df[df['is_call'] == 1]['outcome_pnl'].mean(),
                'puts': df[df['is_call'] == 0]['outcome_pnl'].mean(),
            }
            
            return {
                'success': True,
                'patterns': patterns,
                'total_trades_analyzed': len(df),
                'overall_win_rate': df['is_winner'].mean(),
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def generate_automation_rules(self) -> Dict:
        """
        Generate automation rule suggestions based on learned patterns.
        
        Returns actionable rules that can be automated.
        """
        patterns_result = self.analyze_patterns()
        
        if not patterns_result.get('success'):
            return patterns_result
        
        patterns = patterns_result['patterns']
        rules = []
        
        overall_win_rate = patterns_result['overall_win_rate']
        
        # Rule 1: Best trading hours
        best_hours = list(patterns.get('best_hours', {}).keys())[:2]
        if best_hours:
            best_hour_wr = list(patterns.get('best_hours', {}).values())[0]
            if best_hour_wr > overall_win_rate + 0.1:
                rules.append({
                    'rule_id': 'OPTIMAL_HOURS',
                    'name': 'Trade During Optimal Hours',
                    'description': f'Your win rate is {best_hour_wr:.1%} during hours {best_hours}',
                    'condition': f'hour_of_day in {best_hours}',
                    'action': 'PREFER_ENTRY',
                    'confidence': 'high' if best_hour_wr > 0.6 else 'medium',
                    'improvement': f'+{(best_hour_wr - overall_win_rate)*100:.1f}% win rate',
                })
        
        # Rule 2: Option type preference
        call_wr = patterns.get('call_win_rate', 0.5)
        put_wr = patterns.get('put_win_rate', 0.5)
        
        if abs(call_wr - put_wr) > 0.1:
            better_type = 'Call' if call_wr > put_wr else 'Put'
            better_wr = max(call_wr, put_wr)
            rules.append({
                'rule_id': 'OPTION_TYPE_PREF',
                'name': f'Prefer {better_type} Options',
                'description': f'{better_type}s have {better_wr:.1%} win rate vs {min(call_wr, put_wr):.1%}',
                'condition': f'option_type == "{better_type}"',
                'action': 'PREFER_ENTRY',
                'confidence': 'medium',
                'improvement': f'+{abs(call_wr - put_wr)*100:.1f}% win rate',
            })
        
        # Rule 3: Market trend alignment
        trend_perf = patterns.get('trend_performance', {})
        if trend_perf:
            best_trend = max(trend_perf, key=trend_perf.get)
            best_trend_wr = trend_perf[best_trend]
            if best_trend_wr > overall_win_rate + 0.1:
                rules.append({
                    'rule_id': 'TREND_ALIGNMENT',
                    'name': f'Trade in {best_trend.title()} Markets',
                    'description': f'Win rate is {best_trend_wr:.1%} in {best_trend} markets',
                    'condition': f'market_trend == "{best_trend}"',
                    'action': 'PREFER_ENTRY',
                    'confidence': 'high' if best_trend_wr > 0.65 else 'medium',
                    'improvement': f'+{(best_trend_wr - overall_win_rate)*100:.1f}% win rate',
                })
        
        # Rule 4: Volatility regime
        vol_perf = patterns.get('volatility_performance', {})
        if vol_perf:
            best_vol = max(vol_perf, key=vol_perf.get)
            best_vol_wr = vol_perf[best_vol]
            if best_vol_wr > overall_win_rate + 0.1:
                rules.append({
                    'rule_id': 'VOLATILITY_REGIME',
                    'name': f'Trade in {best_vol.title()} Volatility',
                    'description': f'Win rate is {best_vol_wr:.1%} in {best_vol} IV environments',
                    'condition': f'volatility_regime == "{best_vol}"',
                    'action': 'PREFER_ENTRY',
                    'confidence': 'medium',
                    'improvement': f'+{(best_vol_wr - overall_win_rate)*100:.1f}% win rate',
                })
        
        # Rule 5: Moneyness preference
        money_perf = patterns.get('moneyness_performance', {})
        if money_perf:
            # Filter out NaN values
            money_perf = {k: v for k, v in money_perf.items() if pd.notna(v)}
            if money_perf:
                best_money = max(money_perf, key=money_perf.get)
                best_money_wr = money_perf[best_money]
                if best_money_wr > overall_win_rate + 0.1:
                    rules.append({
                        'rule_id': 'MONEYNESS_PREF',
                        'name': f'Prefer {best_money.upper()} Options',
                        'description': f'{best_money.upper()} options have {best_money_wr:.1%} win rate',
                        'condition': f'moneyness_bucket == "{best_money}"',
                        'action': 'PREFER_ENTRY',
                        'confidence': 'medium',
                        'improvement': f'+{(best_money_wr - overall_win_rate)*100:.1f}% win rate',
                    })
        
        # Rule 6: DTE preference
        dte_perf = patterns.get('dte_performance', {})
        if dte_perf:
            dte_perf = {k: v for k, v in dte_perf.items() if pd.notna(v)}
            if dte_perf:
                best_dte = max(dte_perf, key=dte_perf.get)
                best_dte_wr = dte_perf[best_dte]
                if best_dte_wr > overall_win_rate + 0.1:
                    rules.append({
                        'rule_id': 'DTE_PREF',
                        'name': f'Prefer {best_dte.upper()} Expiries',
                        'description': f'{best_dte.upper()} trades have {best_dte_wr:.1%} win rate',
                        'condition': f'dte_bucket == "{best_dte}"',
                        'action': 'PREFER_ENTRY',
                        'confidence': 'medium',
                        'improvement': f'+{(best_dte_wr - overall_win_rate)*100:.1f}% win rate',
                    })
        
        # Rule 7: Avoid worst conditions
        worst_hours = list(patterns.get('worst_hours', {}).keys())[:2]
        if worst_hours:
            worst_hour_wr = list(patterns.get('worst_hours', {}).values())[0]
            if worst_hour_wr < overall_win_rate - 0.15:
                rules.append({
                    'rule_id': 'AVOID_BAD_HOURS',
                    'name': 'Avoid Poor Trading Hours',
                    'description': f'Win rate drops to {worst_hour_wr:.1%} during hours {worst_hours}',
                    'condition': f'hour_of_day in {worst_hours}',
                    'action': 'AVOID_ENTRY',
                    'confidence': 'high',
                    'improvement': f'Avoid {(overall_win_rate - worst_hour_wr)*100:.1f}% loss',
                })
        
        return {
            'success': True,
            'rules': rules,
            'total_rules': len(rules),
            'based_on_trades': patterns_result['total_trades_analyzed'],
            'overall_win_rate': overall_win_rate,
            'message': f'Generated {len(rules)} automation rules based on {patterns_result["total_trades_analyzed"]} trades',
        }
    
    def get_trade_suggestion(self, market_conditions: Dict) -> Dict:
        """
        Get trade suggestion based on current market conditions.
        
        Args:
            market_conditions: Current market state
            
        Returns:
            Trade suggestion with reasoning
        """
        if not self.is_trained:
            return {
                'success': False,
                'error': 'Model not trained',
                'suggestion': None,
            }
        
        # Get pattern analysis
        patterns_result = self.analyze_patterns()
        if not patterns_result.get('success'):
            return patterns_result
        
        patterns = patterns_result['patterns']
        
        # Score current conditions
        score = 0
        reasons = []
        
        current_hour = datetime.now().hour
        best_hours = list(patterns.get('best_hours', {}).keys())
        worst_hours = list(patterns.get('worst_hours', {}).keys())
        
        if current_hour in best_hours:
            score += 2
            reasons.append(f'Trading during optimal hour ({current_hour}:00)')
        elif current_hour in worst_hours:
            score -= 2
            reasons.append(f'⚠️ Trading during suboptimal hour ({current_hour}:00)')
        
        market_trend = market_conditions.get('market_trend', 'neutral')
        trend_perf = patterns.get('trend_performance', {})
        if trend_perf.get(market_trend, 0.5) > 0.55:
            score += 1
            reasons.append(f'Favorable {market_trend} market trend')
        elif trend_perf.get(market_trend, 0.5) < 0.45:
            score -= 1
            reasons.append(f'⚠️ Unfavorable {market_trend} market trend')
        
        vol_regime = market_conditions.get('volatility_regime', 'medium')
        vol_perf = patterns.get('volatility_performance', {})
        if vol_perf.get(vol_regime, 0.5) > 0.55:
            score += 1
            reasons.append(f'Good performance in {vol_regime} volatility')
        
        # Generate suggestion
        if score >= 3:
            suggestion = 'OPTIMAL_CONDITIONS'
            action = 'Consider entering trades - conditions align with historical winners'
        elif score >= 1:
            suggestion = 'FAVORABLE_CONDITIONS'
            action = 'Conditions are acceptable for trading'
        elif score <= -2:
            suggestion = 'AVOID_TRADING'
            action = 'Consider waiting - conditions align with historical losers'
        else:
            suggestion = 'NEUTRAL_CONDITIONS'
            action = 'Conditions are mixed - trade with caution'
        
        return {
            'success': True,
            'suggestion': suggestion,
            'action': action,
            'score': score,
            'reasons': reasons,
            'current_conditions': {
                'hour': current_hour,
                'market_trend': market_trend,
                'volatility_regime': vol_regime,
            },
        }
    
    def _save_model(self):
        """Save model to disk."""
        try:
            model_path = MODEL_DIR / 'options_ml_model.pkl'
            scaler_path = MODEL_DIR / 'options_ml_scaler.pkl'
            meta_path = MODEL_DIR / 'options_ml_metadata.json'
            
            with open(model_path, 'wb') as f:
                pickle.dump(self.model, f)
            
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            
            # Save feature columns with metadata
            self.model_metadata['feature_columns'] = self.feature_columns
            with open(meta_path, 'w') as f:
                json.dump(self.model_metadata, f, indent=2)
            
            print(f"✅ Model saved to {MODEL_DIR}")
            
        except Exception as e:
            print(f"❌ Error saving model: {e}")
    
    def _load_model(self):
        """Load model from disk."""
        try:
            model_path = MODEL_DIR / 'options_ml_model.pkl'
            scaler_path = MODEL_DIR / 'options_ml_scaler.pkl'
            meta_path = MODEL_DIR / 'options_ml_metadata.json'
            
            if not model_path.exists():
                return
            
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            
            with open(meta_path, 'r') as f:
                self.model_metadata = json.load(f)
            
            self.feature_columns = self.model_metadata.get('feature_columns', [])
            self.is_trained = True
            
            print(f"✅ Loaded existing ML model trained on {self.model_metadata.get('num_trades', 'unknown')} trades")
            
        except Exception as e:
            print(f"⚠️ Could not load model: {e}")
            self.is_trained = False
    
    def get_model_status(self) -> Dict:
        """Get current model status and metrics."""
        can_train, train_message = self.can_train()
        
        return {
            'is_trained': self.is_trained,
            'can_train': can_train,
            'train_message': train_message,
            'metadata': self.model_metadata if self.is_trained else None,
            'feature_columns': self.feature_columns if self.is_trained else [],
        }


# Singleton instance
options_ml_model = OptionsMLModel()
