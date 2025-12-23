"""
Intelligent Conversational AI Advisor

This module provides a robust, context-aware AI advisor that can:
- Answer complex questions about bot performance, strategy, and market
- Control bot features through natural language commands
- Provide real-time analysis and recommendations
- Execute actions based on user intent
- Use Ollama LLM for general trading questions
"""

import os
import sys
import json

from bot.state.store import load_positions_file
import re
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger('intelligent_advisor')


class IntelligentAdvisor:
    """
    Advanced conversational AI advisor with bot control capabilities
    """
    
    def __init__(self, base_dir: str = None):
        """Initialize the intelligent advisor"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent.parent
        
        # Initialize analytics modules
        from ..analytics import (
            get_performance_analytics,
            get_risk_analytics,
            get_execution_analytics
        )
        from ..predictive import get_market_regime_detector
        
        self.performance = get_performance_analytics()
        self.risk = get_risk_analytics()
        self.execution = get_execution_analytics()
        self.regime = get_market_regime_detector()
        
        # Conversation history
        self.conversation_history: List[Dict[str, Any]] = []
        
        # Intent patterns
        self.intent_patterns = self._build_intent_patterns()
    
    def _call_ollama(self, question: str, context: str = "") -> str:
        """
        Call Ollama LLM for general trading questions
        
        Args:
            question: User's question
            context: Additional context (bot data, performance, etc.)
        
        Returns:
            AI response string
        """
        try:
            # Prepare the prompt with context
            prompt = f"""You are an expert trading advisor for a grid trading bot. 
Answer the user's question in 2-3 short paragraphs. Be concise and actionable.

{f"Bot Context:{context}" if context else ""}

Question: {question}

Answer (keep it brief and practical):"""

            # Call Ollama API
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': 'llama3.1:8b',
                    'prompt': prompt,
                    'stream': False,
                    'keep_alive': -1,  # Keep model in memory forever
                    'options': {
                        'temperature': 0.7,
                        'num_predict': 200,  # Shorter responses = faster
                        'top_p': 0.9,
                        'top_k': 40
                    }
                },
                timeout=30  # Faster timeout since model stays loaded
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', 'Sorry, I could not generate a response.')
            else:
                log.error(f"Ollama API error: {response.status_code}")
                return "Sorry, I'm having trouble connecting to the AI service."
                
        except requests.exceptions.ConnectionError:
            log.error("Ollama service not running")
            return "⚠️ AI service is not running. Please start Ollama service."
        except Exception as e:
            log.error(f"Ollama error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    def _build_intent_patterns(self) -> Dict[str, List[str]]:
        """Build regex patterns for intent recognition"""
        return {
            # Performance queries
            'performance_query': [
                r'how.*performance',
                r'how.*doing',
                r'performance.*report',
                r'show.*performance',
                r'win.*rate',
                r'profit.*factor',
                r'sharpe.*ratio',
                r'total.*pnl',
                r'how.*much.*made',
                r'how.*much.*lost'
            ],
            
            # Risk queries
            'risk_query': [
                r'risk.*level',
                r'how.*risky',
                r'var.*value',
                r'max.*drawdown',
                r'volatility',
                r'risk.*metrics',
                r'exposure',
                r'liquidation.*risk'
            ],
            
            # Market queries
            'market_query': [
                r'market.*regime',
                r'market.*condition',
                r'what.*market',
                r'trend.*direction',
                r'volatility.*level',
                r'should.*trade',
                r'market.*forecast'
            ],
            
            # Strategy queries
            'strategy_query': [
                r'grid.*settings',
                r'strategy.*working',
                r'should.*adjust',
                r'optimize.*grid',
                r'grid.*spacing',
                r'position.*size'
            ],
            
            # Control commands
            'start_bot': [
                r'start.*bot',
                r'start.*trading',
                r'resume.*trading',
                r'enable.*trading'
            ],
            
            'stop_bot': [
                r'stop.*bot',
                r'stop.*trading',
                r'pause.*trading',
                r'disable.*trading',
                r'halt.*trading'
            ],
            
            'adjust_grid': [
                r'adjust.*grid',
                r'change.*grid',
                r'modify.*grid',
                r'update.*grid',
                r'set.*grid'
            ],
            
            'close_positions': [
                r'close.*position',
                r'exit.*position',
                r'sell.*all',
                r'close.*all'
            ],
            
            # Status queries
            'status_query': [
                r'status',
                r'what.*happening',
                r'current.*state',
                r'bot.*running',
                r'positions.*open'
            ],
            
            # Recommendations
            'recommendation_query': [
                r'what.*should.*do',
                r'recommend',
                r'suggest',
                r'advice',
                r'next.*action'
            ]
        }
    
    def _detect_intent(self, question: str) -> Tuple[str, float]:
        """
        Detect user intent from question
        
        Returns:
            Tuple of (intent, confidence)
        """
        question_lower = question.lower()
        
        best_intent = 'general_query'
        best_confidence = 0.0
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, question_lower):
                    confidence = 0.8  # Base confidence for pattern match
                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence
        
        return best_intent, best_confidence
    
    def _get_bot_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        try:
            # Check if bot is running
            pid_file = self.base_dir / '.bot.pid'
            is_running = False
            
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    import psutil
                    is_running = psutil.pid_exists(pid)
                except:
                    pass
            
            # Load config from YAML
            cfg = get_config()
            trading_mode = cfg.safety.trading_mode
            positions_file = self.base_dir / f'positions_{trading_mode}.json'
            
            open_positions = 0
            total_pnl = 0
            
            if positions_file.exists():
                data = load_positions_file(positions_file)
                positions = data.get('positions', [])
                open_positions = len(positions)
                total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
            
            return {
                'is_running': is_running,
                'trading_mode': trading_mode,
                'open_positions': open_positions,
                'total_pnl': total_pnl,
                'grid_spacing': cfg.grid.step,
                'position_size': cfg.grid.lot_size,
                'max_positions': cfg.grid.max_open_orders
            }
        except Exception as e:
            log.error(f"Failed to get bot status: {e}")
            return {}
    
    def _handle_performance_query(self, question: str) -> Dict[str, Any]:
        """Handle performance-related questions"""
        try:
            metrics = self.performance.calculate_all_metrics()
            
            # Extract key metrics
            win_loss = metrics.get('win_loss_stats', {})
            returns = metrics.get('returns', {})
            ratios = metrics.get('risk_adjusted_returns', {})
            
            answer = f"""📊 **Performance Summary**

**Win/Loss Statistics:**
- Win Rate: {win_loss.get('win_rate', 0):.1f}%
- Profit Factor: {win_loss.get('profit_factor', 0):.2f}
- Total Trades: {win_loss.get('total_trades', 0)}
- Winning Trades: {win_loss.get('winning_trades', 0)}
- Losing Trades: {win_loss.get('losing_trades', 0)}

**Returns:**
- Total Return: {returns.get('total_return', 0):.2f}%
- Average Trade: ₹{win_loss.get('avg_win', 0):.2f}
- Max Drawdown: {returns.get('max_drawdown', 0):.2f}%

**Risk-Adjusted Metrics:**
- Sharpe Ratio: {ratios.get('sharpe_ratio', 0):.2f}
- Sortino Ratio: {ratios.get('sortino_ratio', 0):.2f}
- Calmar Ratio: {ratios.get('calmar_ratio', 0):.2f}

**Overall Assessment:** {'🟢 Excellent' if win_loss.get('win_rate', 0) > 65 else '🟡 Good' if win_loss.get('win_rate', 0) > 55 else '🔴 Needs Improvement'}
"""
            
            return {
                'answer': answer,
                'data': metrics,
                'actionable': False
            }
        except Exception as e:
            return {
                'answer': f"❌ Failed to retrieve performance data: {str(e)}",
                'data': {},
                'actionable': False
            }
    
    def _handle_risk_query(self, question: str) -> Dict[str, Any]:
        """Handle risk-related questions"""
        try:
            metrics = self.risk.calculate_all_metrics()
            
            var_metrics = metrics.get('var_metrics', {})
            exposure = metrics.get('exposure', {})
            
            answer = f"""🛡️ **Risk Analysis**

**Value at Risk (VaR):**
- 95% VaR: ₹{var_metrics.get('var_95', 0):.2f}
- 99% VaR: ₹{var_metrics.get('var_99', 0):.2f}
- CVaR (Expected Shortfall): ₹{var_metrics.get('cvar_95', 0):.2f}

**Exposure:**
- Current Exposure: ₹{exposure.get('total_exposure', 0):.2f}
- Max Exposure: ₹{exposure.get('max_exposure', 0):.2f}
- Utilization: {exposure.get('utilization_percent', 0):.1f}%

**Risk Level:** {'🟢 Low' if exposure.get('utilization_percent', 0) < 40 else '🟡 Medium' if exposure.get('utilization_percent', 0) < 70 else '🔴 High'}

**Recommendation:** {'Continue trading normally' if exposure.get('utilization_percent', 0) < 40 else 'Monitor closely' if exposure.get('utilization_percent', 0) < 70 else '⚠️ Consider reducing positions'}
"""
            
            return {
                'answer': answer,
                'data': metrics,
                'actionable': exposure.get('utilization_percent', 0) > 70
            }
        except Exception as e:
            return {
                'answer': f"❌ Failed to retrieve risk data: {str(e)}",
                'data': {},
                'actionable': False
            }
    
    def _handle_market_query(self, question: str) -> Dict[str, Any]:
        """Handle market-related questions"""
        try:
            analysis = self.regime.analyze_market()
            
            regime = analysis.get('regime', {})
            forecast = analysis.get('forecast', {})
            
            answer = f"""📈 **Market Analysis**

**Current Regime:** {regime.get('regime', 'UNKNOWN')}
- Confidence: {regime.get('confidence', 0) * 100:.0f}%
- Description: {regime.get('description', 'N/A')}

**Market Metrics:**
- Momentum: {regime.get('metrics', {}).get('momentum', 0):.2f}
- Volatility: {regime.get('metrics', {}).get('volatility', 0):.2f}
- Trend Strength: {regime.get('metrics', {}).get('trend_strength', 0):.2f}

**Price Forecast:**
- Direction: {forecast.get('direction', 'UNKNOWN')} {' 🚀' if forecast.get('direction') == 'UP' else '📉' if forecast.get('direction') == 'DOWN' else '➡️'}
- Confidence: {forecast.get('confidence', 0) * 100:.0f}%
- Current Price: ₹{analysis.get('current_price', 0):,.0f}

**Strategy Recommendation:**
{regime.get('recommendations', {}).get('strategy', 'N/A')}
- Grid Adjustment: {regime.get('recommendations', {}).get('grid_adjustment', 'N/A')}
- Expected Win Rate: {regime.get('recommendations', {}).get('expected_win_rate', 'N/A')}
"""
            
            return {
                'answer': answer,
                'data': analysis,
                'actionable': False
            }
        except Exception as e:
            return {
                'answer': f"❌ Failed to retrieve market data: {str(e)}",
                'data': {},
                'actionable': False
            }
    
    def _handle_status_query(self, question: str) -> Dict[str, Any]:
        """Handle status-related questions"""
        try:
            status = self._get_bot_status()
            
            answer = f"""🤖 **Bot Status**

**Trading Status:** {'🟢 RUNNING' if status.get('is_running') else '🔴 STOPPED'}
**Trading Mode:** {status.get('trading_mode', 'N/A').upper()}

**Current Positions:**
- Open Positions: {status.get('open_positions', 0)}
- Total Unrealized P&L: ₹{status.get('total_pnl', 0):,.2f}

**Grid Configuration:**
- Grid Spacing: {status.get('grid_spacing', 'N/A')}
- Position Size: ${status.get('position_size', 'N/A')}
- Max Positions: {status.get('max_positions', 'N/A')}

**Quick Actions:**
- {'Stop bot with: "stop trading"' if status.get('is_running') else 'Start bot with: "start trading"'}
- Adjust grid: "adjust grid spacing to X"
- Close positions: "close all positions"
"""
            
            return {
                'answer': answer,
                'data': status,
                'actionable': True
            }
        except Exception as e:
            return {
                'answer': f"❌ Failed to retrieve status: {str(e)}",
                'data': {},
                'actionable': False
            }
    
    def _handle_recommendation_query(self, question: str) -> Dict[str, Any]:
        """Handle recommendation requests"""
        try:
            # Get comprehensive analysis
            from ..institutional_advisor import get_institutional_advisor
            advisor = get_institutional_advisor()
            analysis = advisor.get_comprehensive_analysis()
            
            recommendations = analysis.get('recommendations', [])
            
            if not recommendations:
                answer = "✅ Everything looks good! No immediate actions required."
            else:
                answer = "💡 **AI Recommendations**\n\n"
                for i, rec in enumerate(recommendations[:3], 1):  # Top 3
                    priority_emoji = '🔴' if rec.get('priority') == 'critical' else '🟡' if rec.get('priority') == 'high' else '🔵'
                    answer += f"{priority_emoji} **{rec.get('title', 'N/A')}**\n"
                    answer += f"   Action: {rec.get('action', 'N/A')}\n"
                    answer += f"   Reasoning: {rec.get('reasoning', 'N/A')}\n"
                    answer += f"   Confidence: {rec.get('confidence', 0)}%\n\n"
            
            return {
                'answer': answer,
                'data': {'recommendations': recommendations},
                'actionable': len(recommendations) > 0
            }
        except Exception as e:
            return {
                'answer': f"❌ Failed to generate recommendations: {str(e)}",
                'data': {},
                'actionable': False
            }
    
    def _handle_control_command(self, intent: str, question: str) -> Dict[str, Any]:
        """Handle bot control commands"""
        
        if intent == 'start_bot':
            return {
                'answer': """🚀 **Start Trading Command Detected**

To start the bot, please use the "Start Bot" button in the main control panel.

Alternatively, you can start it via terminal:
```
cd ~/Documents/WorkingBot
python3 bot/run.py
```

⚠️ **Safety Check:**
- Ensure you've reviewed current market conditions
- Verify your grid settings are appropriate
- Check that you have sufficient capital
""",
                'data': {'command': 'start_bot'},
                'actionable': True,
                'requires_confirmation': True
            }
        
        elif intent == 'stop_bot':
            return {
                'answer': """🛑 **Stop Trading Command Detected**

To stop the bot, please use the "Stop Bot" button in the main control panel.

This will:
- Stop placing new orders
- Keep existing positions open
- Continue monitoring liquidation risk (Guardian Bot)

⚠️ **Note:** Existing open positions will remain until manually closed or TP is hit.
""",
                'data': {'command': 'stop_bot'},
                'actionable': True,
                'requires_confirmation': True
            }
        
        elif intent == 'close_positions':
            return {
                'answer': """⚠️ **Close All Positions Command Detected**

This is a HIGH-RISK action that will:
- Close ALL open positions at market price
- May result in slippage
- Cannot be undone

Please use the "Emergency Close All" button in the control panel if you're certain.

**Alternative:** Consider closing positions gradually to minimize market impact.
""",
                'data': {'command': 'close_positions'},
                'actionable': True,
                'requires_confirmation': True
            }
        
        elif intent == 'adjust_grid':
            # Try to extract grid parameters from question
            spacing_match = re.search(r'spacing.*?(\d+)', question.lower())
            size_match = re.search(r'size.*?(\d+)', question.lower())
            
            suggestions = []
            if spacing_match:
                suggestions.append(f"Grid Spacing: {spacing_match.group(1)}")
            if size_match:
                suggestions.append(f"Position Size: ${size_match.group(1)}")
            
            return {
                'answer': f"""⚙️ **Grid Adjustment Command Detected**

Detected parameters:
{chr(10).join(f'- {s}' for s in suggestions) if suggestions else '- No specific parameters detected'}

To adjust grid settings:
1. Go to the Configuration tab
2. Modify the desired parameters
3. Save changes
4. Restart the bot for changes to take effect

**Tip:** Use the "Grid Optimization" feature in the Recommendations tab for AI-suggested settings.
""",
                'data': {'command': 'adjust_grid', 'suggestions': suggestions},
                'actionable': True,
                'requires_confirmation': False
            }
        
        return {
            'answer': "❓ Command not fully implemented yet. Please use the control panel.",
            'data': {},
            'actionable': False
        }
    
    def ask(self, question: str) -> Dict[str, Any]:
        """
        Process a question and return an intelligent response
        
        Args:
            question: User's question
        
        Returns:
            Dictionary with answer, data, and metadata
        """
        try:
            # Detect intent
            intent, confidence = self._detect_intent(question)
            
            log.info(f"Question: {question}")
            log.info(f"Detected intent: {intent} (confidence: {confidence:.2f})")
            
            # Route to appropriate handler
            if intent == 'performance_query':
                response = self._handle_performance_query(question)
            elif intent == 'risk_query':
                response = self._handle_risk_query(question)
            elif intent == 'market_query':
                response = self._handle_market_query(question)
            elif intent == 'status_query':
                response = self._handle_status_query(question)
            elif intent == 'recommendation_query':
                response = self._handle_recommendation_query(question)
            elif intent in ['start_bot', 'stop_bot', 'close_positions', 'adjust_grid']:
                response = self._handle_control_command(intent, question)
            else:
                # General query - use Ollama for intelligent response
                # Get bot context for better answers
                bot_status = self._get_bot_status()
                context = f"""
Bot Status: {'Running' if bot_status.get('is_running') else 'Stopped'}
Trading Mode: {bot_status.get('trading_mode', 'N/A').upper()}
Open Positions: {bot_status.get('open_positions', 0)}
Grid Spacing: {bot_status.get('grid_spacing', 'N/A')}
"""
                
                # Call Ollama for intelligent response
                ai_answer = self._call_ollama(question, context)
                
                response = {
                    'answer': f"""🤖 **AI Trading Advisor**

{ai_answer}

---
💡 **Quick Tips:**
- Ask about performance: "How's my performance?"
- Check risk: "What's my risk level?"
- Get recommendations: "What should I do?"
- Control bot: "Start trading" or "Stop the bot"
""",
                    'data': {},
                    'actionable': False
                }
            
            # Add metadata
            response['intent'] = intent
            response['confidence'] = confidence
            response['timestamp'] = datetime.now().isoformat()
            
            # Store in conversation history
            self.conversation_history.append({
                'question': question,
                'response': response,
                'timestamp': datetime.now().isoformat()
            })
            
            return response
            
        except Exception as e:
            log.error(f"Error processing question: {e}")
            return {
                'answer': f"❌ Sorry, I encountered an error: {str(e)}\n\nPlease try rephrasing your question.",
                'data': {},
                'actionable': False,
                'error': str(e)
            }


# Singleton accessor
_intelligent_advisor_instance = None

def get_intelligent_advisor() -> IntelligentAdvisor:
    """Get singleton instance of intelligent advisor"""
    global _intelligent_advisor_instance
    if _intelligent_advisor_instance is None:
        _intelligent_advisor_instance = IntelligentAdvisor()
    return _intelligent_advisor_instance

