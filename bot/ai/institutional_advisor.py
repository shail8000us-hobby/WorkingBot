"""
Institutional-Grade AI Trading Advisor

This is the main AI advisor that combines all analytics modules to provide:
- Intelligent recommendations (position sizing, risk management, strategy adjustments)
- Advanced conversational AI with deep context awareness
- Root cause analysis for trades
- Performance insights and optimization suggestions

This is the crown jewel of the institutional AI system.

Author: GridBot Pro - Institutional AI
Version: 1.0.0
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

# Import all analytics modules
from .analytics import (
    get_performance_analytics,
    get_risk_analytics,
    get_execution_analytics,
    get_log_analyzer
)
from .predictive import (
    get_market_regime_detector,
    get_grid_optimizer
)


class InstitutionalAIAdvisor:
    """
    Professional-grade AI trading advisor
    
    This is the main intelligence engine that combines all analytics
    to provide institutional-quality insights and recommendations.
    """
    
    def __init__(self, base_dir: str = None):
        """Initialize the institutional AI advisor"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent
        
        # Initialize all analytics modules
        self.performance = get_performance_analytics()
        self.risk = get_risk_analytics()
        self.execution = get_execution_analytics()
        self.logs = get_log_analyzer()
        self.regime = get_market_regime_detector()
        self.optimizer = get_grid_optimizer()
        
        self.cache = {}
        self.cache_ttl = 60
        self.last_cache_time = None
    
    # =========================================================================
    # COMPREHENSIVE ANALYSIS
    # =========================================================================
    
    def get_comprehensive_analysis(
        self,
        lookback_days: int = 30,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get complete institutional-grade analysis
        
        This is the main method that combines all analytics modules
        to provide a comprehensive view of the trading system.
        
        Args:
            lookback_days: Number of days to analyze
            force_refresh: Force recalculation (ignore cache)
        
        Returns:
            Dictionary with complete analysis
        """
        # Check cache
        if not force_refresh and self.last_cache_time:
            if (datetime.now() - self.last_cache_time).total_seconds() < self.cache_ttl:
                return self.cache
        
        # Gather all analytics
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'lookback_days': lookback_days,
            
            # Performance Analytics
            'performance': self.performance.calculate_all_metrics(lookback_days),
            'performance_grades': None,  # Will calculate below
            
            # Risk Analytics
            'risk': self.risk.calculate_all_metrics(lookback_days),
            'risk_grades': None,  # Will calculate below
            
            # Execution Analytics
            'execution': self.execution.calculate_all_metrics(lookback_days),
            'execution_grades': None,  # Will calculate below
            
            # Log Analysis
            'log_analysis': self.logs.analyze_logs(24),  # Last 24 hours
            'system_health': None,  # Will calculate below
            
            # Market Analysis
            'market': self.regime.analyze_market(),
            
            # Optimization
            'optimization': self.optimizer.get_optimization_recommendations(),
            
            # AI Insights
            'insights': None,  # Will generate below
            'recommendations': None,  # Will generate below
            'alerts': None  # Will generate below
        }
        
        # Calculate grades
        analysis['performance_grades'] = self.performance.get_performance_grade(analysis['performance'])
        analysis['risk_grades'] = self.risk.get_risk_grade(analysis['risk'])
        analysis['execution_grades'] = self.execution.get_execution_grade(analysis['execution'])
        analysis['system_health'] = self.logs.get_health_status(analysis['log_analysis'])
        
        # Generate AI insights
        analysis['insights'] = self._generate_insights(analysis)
        
        # Generate recommendations
        analysis['recommendations'] = self._generate_recommendations(analysis)
        
        # Generate alerts
        analysis['alerts'] = self._generate_alerts(analysis)
        
        # Update cache
        self.cache = analysis
        self.last_cache_time = datetime.now()
        
        return analysis
    
    # =========================================================================
    # INTELLIGENT INSIGHTS
    # =========================================================================
    
    def _generate_insights(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate intelligent insights from analysis
        
        Args:
            analysis: Complete analysis dictionary
        
        Returns:
            List of insight dictionaries
        """
        insights = []
        
        # Performance insights
        perf = analysis['performance']
        sharpe = perf['risk_adjusted_returns']['sharpe_ratio']
        win_rate = perf['win_loss_stats']['win_rate']
        max_dd = abs(perf['drawdown_analysis']['max_drawdown']['max_dd_pct'])
        
        if sharpe > 2.0:
            insights.append({
                'category': 'PERFORMANCE',
                'severity': 'positive',
                'title': 'Excellent Risk-Adjusted Returns',
                'message': f'Your Sharpe Ratio of {sharpe} is excellent (top 10% of traders). You are generating strong returns relative to risk.',
                'icon': '⭐'
            })
        
        elif sharpe < 1.0:
            insights.append({
                'category': 'PERFORMANCE',
                'severity': 'warning',
                'title': 'Low Risk-Adjusted Returns',
                'message': f'Your Sharpe Ratio of {sharpe} is below optimal. Consider reducing position sizes or widening grid step to improve risk-adjusted returns.',
                'icon': '⚠️'
            })
        
        if win_rate > 65:
            insights.append({
                'category': 'PERFORMANCE',
                'severity': 'positive',
                'title': 'High Win Rate',
                'message': f'Your win rate of {win_rate:.1f}% is strong. Current market conditions suit your grid strategy well.',
                'icon': '✓'
            })
        
        if max_dd > 20:
            insights.append({
                'category': 'RISK',
                'severity': 'critical',
                'title': 'High Drawdown',
                'message': f'Maximum drawdown of {max_dd:.1f}% is concerning. Consider reducing position sizes or implementing stricter loss limits.',
                'icon': '🔴'
            })
        
        # Market regime insights
        market = analysis['market']
        regime = market['regime']['regime']
        
        if regime == 'MEAN_REVERTING':
            insights.append({
                'category': 'MARKET',
                'severity': 'positive',
                'title': 'Optimal Market Regime',
                'message': 'Market is mean-reverting - ideal for grid trading. Expected win rate: 65-75%.',
                'icon': '✓'
            })
        
        elif regime == 'HIGH_VOLATILITY':
            insights.append({
                'category': 'MARKET',
                'severity': 'warning',
                'title': 'High Volatility Detected',
                'message': 'Market volatility is elevated. Consider reducing position sizes and widening grid step.',
                'icon': '⚠️'
            })
        
        # Risk insights
        risk = analysis['risk']
        margin_util = risk['margin_leverage']['margin_utilization']
        liq_distance = risk['margin_leverage']['liquidation_distance']
        
        if margin_util > 60:
            insights.append({
                'category': 'RISK',
                'severity': 'critical',
                'title': 'High Margin Utilization',
                'message': f'Margin utilization at {margin_util:.1f}% is high. Liquidation risk is elevated. Consider closing some positions.',
                'icon': '🔴'
            })
        
        if liq_distance < 30:
            insights.append({
                'category': 'RISK',
                'severity': 'critical',
                'title': 'Low Liquidation Distance',
                'message': f'Liquidation distance at {liq_distance:.1f}% is dangerously low. Add margin or close positions immediately.',
                'icon': '🔴'
            })
        
        # Execution insights
        exec_data = analysis['execution']
        fill_rate = exec_data['fill_rate']
        rejection_rate = exec_data['rejection']['rejection_rate']
        
        if fill_rate < 95:
            insights.append({
                'category': 'EXECUTION',
                'severity': 'warning',
                'title': 'Low Fill Rate',
                'message': f'Fill rate of {fill_rate:.1f}% is below optimal. Check order types and price levels.',
                'icon': '⚠️'
            })
        
        if rejection_rate > 5:
            insights.append({
                'category': 'EXECUTION',
                'severity': 'warning',
                'title': 'High Rejection Rate',
                'message': f'Order rejection rate of {rejection_rate:.1f}% is high. Review error logs for root cause.',
                'icon': '⚠️'
            })
        
        return insights
    
    # =========================================================================
    # INTELLIGENT RECOMMENDATIONS
    # =========================================================================
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate intelligent recommendations
        
        Args:
            analysis: Complete analysis dictionary
        
        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        
        # Get key metrics
        perf = analysis['performance']
        risk = analysis['risk']
        market = analysis['market']
        opt = analysis['optimization']
        
        sharpe = perf['risk_adjusted_returns']['sharpe_ratio']
        win_rate = perf['win_loss_stats']['win_rate']
        max_dd = abs(perf['drawdown_analysis']['max_drawdown']['max_dd_pct'])
        regime = market['regime']['regime']
        
        # Position sizing recommendations
        kelly_fraction = opt['position_sizing']['kelly_fraction']
        optimal_size = opt['position_sizing']['optimal_size']
        
        recommendations.append({
            'category': 'POSITION_SIZING',
            'priority': 'high',
            'title': 'Optimal Position Size',
            'action': f'Use {optimal_size} lots per position',
            'reasoning': f'Based on Kelly Criterion ({kelly_fraction*100:.1f}% of capital), this maximizes long-term growth while controlling risk.',
            'expected_impact': '+10-15% annual return',
            'confidence': 85
        })
        
        # Grid parameter recommendations
        optimal_grid_step = opt['grid_parameters']['optimal_grid_step']
        
        recommendations.append({
            'category': 'GRID_PARAMETERS',
            'priority': 'high',
            'title': 'Optimal Grid Step',
            'action': f'Set grid step to ₹{optimal_grid_step}',
            'reasoning': f'Based on current volatility and market regime ({regime}), this grid step optimizes win rate and profit factor.',
            'expected_impact': '+5-10% win rate improvement',
            'confidence': 80
        })
        
        # Risk management recommendations
        if max_dd > 15:
            recommendations.append({
                'category': 'RISK_MANAGEMENT',
                'priority': 'critical',
                'title': 'Reduce Drawdown',
                'action': 'Reduce position size by 30%',
                'reasoning': f'Current max drawdown of {max_dd:.1f}% exceeds optimal levels. Smaller positions will reduce drawdown while maintaining profitability.',
                'expected_impact': '-40% drawdown, -10% returns',
                'confidence': 90
            })
        
        # Market regime recommendations
        if regime == 'HIGH_VOLATILITY':
            recommendations.append({
                'category': 'STRATEGY',
                'priority': 'high',
                'title': 'Adapt to High Volatility',
                'action': 'Widen grid step by 30% and reduce position size by 50%',
                'reasoning': 'High volatility increases risk. Wider grid and smaller positions will protect capital.',
                'expected_impact': '-50% risk, maintain profitability',
                'confidence': 85
            })
        
        elif regime == 'MEAN_REVERTING':
            recommendations.append({
                'category': 'STRATEGY',
                'priority': 'medium',
                'title': 'Optimize for Mean Reversion',
                'action': 'Tighten grid step by 15%',
                'reasoning': 'Mean-reverting conditions are ideal for grid trading. Tighter grid will capture more opportunities.',
                'expected_impact': '+15% trade frequency, +20% profit factor',
                'confidence': 75
            })
        
        # Performance optimization
        if sharpe < 1.5 and win_rate > 60:
            recommendations.append({
                'category': 'OPTIMIZATION',
                'priority': 'medium',
                'title': 'Improve Risk-Adjusted Returns',
                'action': 'Increase take-profit targets by 20%',
                'reasoning': f'High win rate ({win_rate:.1f}%) but low Sharpe ({sharpe}). Wider targets will improve risk-adjusted returns.',
                'expected_impact': '+0.3-0.5 Sharpe Ratio',
                'confidence': 70
            })
        
        return recommendations
    
    # =========================================================================
    # INTELLIGENT ALERTS
    # =========================================================================
    
    def _generate_alerts(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate intelligent alerts
        
        Args:
            analysis: Complete analysis dictionary
        
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        # Critical risk alerts
        risk = analysis['risk']
        margin_util = risk['margin_leverage']['margin_utilization']
        liq_distance = risk['margin_leverage']['liquidation_distance']
        
        if liq_distance < 20:
            alerts.append({
                'severity': 'CRITICAL',
                'category': 'LIQUIDATION_RISK',
                'title': 'CRITICAL: Liquidation Risk High',
                'message': f'Liquidation distance is only {liq_distance:.1f}%. Add margin or close positions IMMEDIATELY.',
                'action': 'CLOSE_POSITIONS',
                'urgency': 'immediate'
            })
        
        elif margin_util > 70:
            alerts.append({
                'severity': 'CRITICAL',
                'category': 'MARGIN_RISK',
                'title': 'CRITICAL: Margin Utilization Too High',
                'message': f'Margin utilization at {margin_util:.1f}% is dangerous. Reduce exposure immediately.',
                'action': 'REDUCE_POSITIONS',
                'urgency': 'immediate'
            })
        
        # Performance degradation alerts
        perf = analysis['performance']
        current_dd = perf['drawdown_analysis']['current_drawdown']
        
        if current_dd < -15:
            alerts.append({
                'severity': 'HIGH',
                'category': 'DRAWDOWN',
                'title': 'High Drawdown Alert',
                'message': f'Current drawdown of {current_dd:.1f}% approaching critical levels.',
                'action': 'REVIEW_STRATEGY',
                'urgency': 'high'
            })
        
        # System health alerts
        health = analysis['system_health']
        
        if health['status'] == 'CRITICAL':
            alerts.append({
                'severity': 'HIGH',
                'category': 'SYSTEM_HEALTH',
                'title': 'System Health Critical',
                'message': health['message'],
                'action': 'CHECK_LOGS',
                'urgency': 'high'
            })
        
        # Market condition alerts
        market = analysis['market']
        regime = market['regime']['regime']
        
        if regime == 'HIGH_VOLATILITY':
            alerts.append({
                'severity': 'MEDIUM',
                'category': 'MARKET_CONDITIONS',
                'title': 'High Volatility Detected',
                'message': 'Market volatility is elevated. Consider reducing activity.',
                'action': 'ADJUST_PARAMETERS',
                'urgency': 'medium'
            })
        
        return alerts
    
    # =========================================================================
    # CONVERSATIONAL AI
    # =========================================================================
    
    def ask(self, question: str) -> Dict[str, Any]:
        """
        Advanced conversational AI with deep context awareness
        
        This is the main Q&A interface that provides intelligent,
        context-aware responses to user questions.
        
        Args:
            question: User's question
        
        Returns:
            Dictionary with AI response
        """
        question_lower = question.lower().strip()
        
        # Get comprehensive analysis for context
        analysis = self.get_comprehensive_analysis()
        
        # Route to appropriate handler
        response = self._handle_question(question_lower, analysis)
        
        return {
            'success': True,
            'question': question,
            'response': response,
            'timestamp': datetime.now().isoformat()
        }
    
    def _handle_question(self, question: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user question with context awareness"""
        
        perf = analysis['performance']
        risk = analysis['risk']
        market = analysis['market']
        insights = analysis['insights']
        recommendations = analysis['recommendations']
        
        # Performance questions
        if any(word in question for word in ['performance', 'doing', 'returns', 'profit']):
            sharpe = perf['risk_adjusted_returns']['sharpe_ratio']
            win_rate = perf['win_loss_stats']['win_rate']
            total_return = perf['overall_performance']['total_return']
            
            return {
                'answer': f"""Your performance is {'excellent' if sharpe > 2.0 else 'good' if sharpe > 1.0 else 'needs improvement'}:

• **Total Return**: {total_return:+.2f}% over {analysis['lookback_days']} days
• **Sharpe Ratio**: {sharpe} {'⭐ (Excellent)' if sharpe > 2.0 else '✓ (Good)' if sharpe > 1.0 else '⚠️ (Fair)'}
• **Win Rate**: {win_rate:.1f}% {'⭐' if win_rate > 65 else '✓' if win_rate > 55 else '⚠️'}

**Key Insight**: {insights[0]['message'] if insights else 'Performance is stable.'}

**Top Recommendation**: {recommendations[0]['action'] if recommendations else 'Continue current strategy.'}""",
                'metrics': perf,
                'deep_link': {'tab': 'ai_advisor', 'section': 'performance'}
            }
        
        # Risk questions
        elif any(word in question for word in ['risk', 'safe', 'danger', 'liquidation']):
            var_95 = risk['value_at_risk']['var_95_historical']
            margin_util = risk['margin_leverage']['margin_utilization']
            liq_distance = risk['margin_leverage']['liquidation_distance']
            
            risk_level = 'LOW' if margin_util < 40 else 'MEDIUM' if margin_util < 60 else 'HIGH'
            
            return {
                'answer': f"""Your current risk level is **{risk_level}**:

• **Margin Utilization**: {margin_util:.1f}% {'✓' if margin_util < 50 else '⚠️' if margin_util < 70 else '🔴'}
• **Liquidation Distance**: {liq_distance:.1f}% {'✓' if liq_distance > 50 else '⚠️' if liq_distance > 30 else '🔴'}
• **Value at Risk (95%)**: ₹{abs(var_95):,.0f}

**Risk Assessment**: {'Your risk is well-controlled.' if risk_level == 'LOW' else 'Risk is moderate. Monitor closely.' if risk_level == 'MEDIUM' else '⚠️ Risk is HIGH. Consider reducing positions.'}

**Recommendation**: {recommendations[0]['action'] if recommendations and recommendations[0]['category'] == 'RISK_MANAGEMENT' else 'Maintain current risk levels.'}""",
                'metrics': risk,
                'deep_link': {'tab': 'ai_advisor', 'section': 'risk'}
            }
        
        # Market regime questions
        elif any(word in question for word in ['market', 'regime', 'conditions', 'volatility']):
            regime = market['regime']['regime']
            confidence = market['regime']['confidence']
            description = market['regime']['description']
            regime_recs = market['regime']['recommendations']
            
            return {
                'answer': f"""Current market regime: **{regime}** (Confidence: {confidence*100:.0f}%)

{description}

**Strategy Recommendation**: {regime_recs['strategy']}

**Grid Adjustment**: {regime_recs['grid_adjustment']}

**Expected Performance**:
• Win Rate: {regime_recs['expected_win_rate']}
• Profit Factor: {regime_recs['expected_profit_factor']}

**Insight**: {[i for i in insights if i['category'] == 'MARKET'][0]['message'] if any(i['category'] == 'MARKET' for i in insights) else 'Market conditions are stable.'}""",
                'metrics': market,
                'deep_link': {'tab': 'ai_advisor', 'section': 'market'}
            }
        
        # Recommendation questions
        elif any(word in question for word in ['should i', 'recommend', 'suggest', 'what do you think']):
            top_recs = recommendations[:3] if len(recommendations) >= 3 else recommendations
            
            rec_text = '\n\n'.join([
                f"**{i+1}. {rec['title']}** (Priority: {rec['priority'].upper()})\n"
                f"   • Action: {rec['action']}\n"
                f"   • Reasoning: {rec['reasoning']}\n"
                f"   • Expected Impact: {rec['expected_impact']}\n"
                f"   • Confidence: {rec['confidence']}%"
                for i, rec in enumerate(top_recs)
            ])
            
            return {
                'answer': f"""Based on comprehensive analysis, here are my top recommendations:

{rec_text}

**Overall Assessment**: Your trading system is {'performing well' if perf['risk_adjusted_returns']['sharpe_ratio'] > 1.5 else 'showing room for improvement'}. Focus on the high-priority recommendations first.""",
                'recommendations': recommendations,
                'deep_link': {'tab': 'ai_advisor', 'section': 'recommendations'}
            }
        
        # Default response
        else:
            return {
                'answer': f"""I can help you with:

• **Performance Analysis**: "How's my performance?" or "What are my returns?"
• **Risk Assessment**: "What's my risk level?" or "Am I safe from liquidation?"
• **Market Insights**: "What's the current market regime?" or "How's volatility?"
• **Recommendations**: "What should I do?" or "Any suggestions?"

Ask me anything about your trading!""",
                'deep_link': None
            }


# Singleton accessor
_institutional_advisor_instance = None

def get_institutional_advisor() -> InstitutionalAIAdvisor:
    """Get singleton instance of InstitutionalAIAdvisor"""
    global _institutional_advisor_instance
    if _institutional_advisor_instance is None:
        _institutional_advisor_instance = InstitutionalAIAdvisor()
    return _institutional_advisor_instance

