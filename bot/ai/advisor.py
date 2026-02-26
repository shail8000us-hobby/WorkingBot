#!/usr/bin/env python3
"""
AI Advisor - Intelligent bot assistant for answering questions and providing suggestions

This module provides context-aware AI responses about the bot's behavior, configuration,
and trading decisions. It can integrate with OpenAI API or use local AI models.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

from bot.state.store import load_positions_file
from typing import Dict, List, Any, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config


class AIAdvisor:
    """
    AI Advisor for providing intelligent responses about the bot.
    Can integrate with OpenAI API or use rule-based responses.
    """
    
    def __init__(self):
        self.workspace_root = Path(__file__).parent.parent.parent
        # API keys stay in environment for security
        self.api_key = os.getenv('OPENAI_API_KEY', '')
        # allow overriding base URL (FreeAPIKey, self‑hosted, etc.)
        self.api_base = os.getenv('OPENAI_API_BASE', "https://api.openai.com/v1")
        # default model can also be overridden (e.g. claude-opus-4.5)
        self.default_model = os.getenv('OPENAI_API_MODEL', "gpt-4")
        self.use_openai = bool(self.api_key)
        
        # Context about the bot
        self.bot_context = self._load_bot_context()
    
    def _load_bot_context(self) -> Dict[str, Any]:
        """Load current bot context (config, status, positions)"""
        context = {
            'timestamp': datetime.now().isoformat(),
            'config': {},
            'status': {},
            'positions': [],
            'blockers': []
        }
        
        # Load config from YAML
        try:
            cfg = get_config()
            context['config'] = {
                'symbol': cfg.trading.symbol,
                'trading_mode': cfg.safety.trading_mode,
                'execute_orders': cfg.safety.execute_orders,
                'grid_step': cfg.grid.step,
                'grid_bounds': f"{cfg.grid.lower}-{cfg.grid.upper}",
                'lot_size': cfg.grid.lot_size
            }
        except Exception:
            pass
        
        # Load status
        try:
            from bot.safety.blocker_tracker import get_blocker_tracker
            tracker = get_blocker_tracker()
            blocker_data = tracker.check_all_blockers()
            context['status'] = {
                'trading_allowed': blocker_data['trading_allowed'],
                'total_blockers': blocker_data['total_blockers']
            }
            context['blockers'] = blocker_data['blockers']
        except Exception:
            pass
        
        # Load positions
        try:
            positions_file = self.workspace_root / 'positions_demo.json'
            if positions_file.exists():
                positions_data = load_positions_file(positions_file)
                context['positions'] = positions_data.get('positions', [])
        except Exception:
            pass
        
        return context
    
    def ask(self, question: str) -> Dict[str, Any]:
        """
        Ask the AI Advisor a question.
        
        Args:
            question: User's question
            
        Returns:
            dict: {
                'success': bool,
                'answer': str,
                'suggestions': List[str],
                'related_links': List[dict]
            }
        """
        # Refresh context
        self.bot_context = self._load_bot_context()
        
        if self.use_openai:
            return self._ask_openai(question)
        else:
            return self._ask_rule_based(question)
    
    def _ask_openai(self, question: str) -> Dict[str, Any]:
        """Use OpenAI API for intelligent responses"""
        try:
            import openai
            openai.api_key = self.api_key
            # respect custom base URL if provided (FreeAI, proxy, etc.)
            openai.api_base = self.api_base
            
            # Build context prompt
            system_prompt = self._build_system_prompt()
            
            # choose model from environment or default
            model = self.default_model
            
            # Call OpenAI-compatible API
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            
            return {
                'success': True,
                'answer': answer,
                'suggestions': self._extract_suggestions(answer),
                'related_links': self._get_related_links(question),
                'source': 'openai'
            }
        
        except Exception:
            # Fallback to rule-based on any error
            return self._ask_rule_based(question)
    
    def _ask_rule_based(self, question: str) -> Dict[str, Any]:
        """Use rule-based responses (no API needed)"""
        question_lower = question.lower()
        
        # Define response patterns
        responses = {
            'why.*stop': self._explain_why_stopped,
            'why.*not.*trading': self._explain_why_stopped,
            'blocker': self._explain_blockers,
            'volatility': self._explain_volatility,
            'loss.*limit': self._explain_loss_limits,
            'margin': self._explain_margin,
            'liquidation': self._explain_liquidation,
            'grid.*step': self._explain_grid_step,
            'position': self._explain_positions,
            'pnl': self._explain_pnl,
            'risk': self._explain_risk,
            'how.*work': self._explain_how_it_works,
            'what.*is': self._explain_concept,
        }
        
        # Match question to response
        import re
        for pattern, handler in responses.items():
            if re.search(pattern, question_lower):
                return handler()
        
        # Default response
        return {
            'success': True,
            'answer': self._get_default_response(question),
            'suggestions': [
                'Check the USERMANUAL.md for detailed documentation',
                'Review your current configuration in config.yaml',
                'Use the Trading Status Panel to see active blockers'
            ],
            'related_links': [
                {'title': 'User Manual', 'url': '/docs/USERMANUAL.md'},
                {'title': 'Configuration', 'tab': 'configuration'},
                {'title': 'Trading Status', 'action': 'view_status'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_why_stopped(self) -> Dict[str, Any]:
        """Explain why trading is stopped"""
        blockers = [b for b in self.bot_context['blockers'] if b['active']]
        
        if not blockers:
            answer = "✅ Trading is NOT stopped! All systems are healthy and trading is allowed."
        else:
            answer = f"🚫 Trading is stopped due to {len(blockers)} active blocker(s):\n\n"
            for blocker in blockers:
                answer += f"• **{blocker['name']}**: {blocker['message']}\n"
            answer += "\n💡 Click on any blocker in the Trading Status Panel to navigate to the fix location."
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'Click on blockers in the Trading Status Panel to fix them',
                'Review safety settings in the Robustness tab',
                'Check if EXECUTE_ORDERS is enabled in Configuration'
            ],
            'related_links': [
                {'title': 'Fix Blockers', 'action': 'view_blockers'},
                {'title': 'Robustness Settings', 'tab': 'robustness'},
                {'title': 'Configuration', 'tab': 'configuration'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_blockers(self) -> Dict[str, Any]:
        """Explain blockers"""
        blockers = [b for b in self.bot_context['blockers'] if b['active']]
        
        answer = f"🚨 **Blockers** are safety systems that prevent trading when certain conditions are met.\n\n"
        answer += f"**Current Status**: {len(blockers)} active blocker(s)\n\n"
        
        if blockers:
            answer += "**Active Blockers**:\n"
            for blocker in blockers:
                answer += f"• {blocker['name']} ({blocker['severity']})\n"
        else:
            answer += "✅ No active blockers - all systems healthy!"
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'View all blockers in the Trading Status Panel',
                'Click on a blocker to navigate to its fix location',
                'Review safety settings in Robustness tab'
            ],
            'related_links': [
                {'title': 'View Blockers', 'action': 'view_blockers'},
                {'title': 'Robustness Features', 'tab': 'robustness'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_volatility(self) -> Dict[str, Any]:
        """Explain volatility safety"""
        answer = "🌊 **Volatility Safety** monitors market volatility (IV and RV) and stops trading when volatility is too high.\n\n"
        answer += "**How it works**:\n"
        answer += "• Tracks Implied Volatility (IV) from Deribit\n"
        answer += "• Calculates Realized Volatility (RV) from Delta Exchange\n"
        answer += "• Stops trading if IV > 35%, RV > 40%, or |IV-RV| > 10%\n"
        answer += "• Automatically resumes when conditions normalize\n\n"
        answer += "**Why it matters**: High volatility = higher risk of losses and liquidation."
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'Check current IV/RV in the Robustness tab',
                'Adjust volatility limits if needed',
                'Monitor volatility during high-impact news events'
            ],
            'related_links': [
                {'title': 'Volatility Monitor', 'tab': 'robustness', 'section': 'volatility'},
                {'title': 'Adjust Settings', 'tab': 'robustness'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_loss_limits(self) -> Dict[str, Any]:
        """Explain loss limits"""
        guardian_limit = self.bot_context['config'].get('GUARDIAN_LOSS_LIMIT_INR', '-15000')
        
        answer = f"💰 **Loss Limits** protect your capital by automatically closing positions when losses reach a threshold.\n\n"
        answer += f"**Current Settings**:\n"
        answer += f"• Guardian Loss Limit: ₹{guardian_limit}\n\n"
        answer += "**How it works**:\n"
        answer += "• Guardian Bot monitors total PnL 24/7\n"
        answer += "• When loss limit is breached, all positions are closed\n"
        answer += "• You receive a Telegram notification\n"
        answer += "• Bot stops trading until you acknowledge\n\n"
        answer += "**Best Practice**: Set loss limit to 2-3% of your capital."
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'Review loss limits in Guardian Bot tab',
                'Set loss limit to 2-3% of your capital',
                'Enable Telegram notifications for alerts'
            ],
            'related_links': [
                {'title': 'Guardian Bot', 'tab': 'guardian'},
                {'title': 'Capital Protection', 'tab': 'capital_protection'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_margin(self) -> Dict[str, Any]:
        """Explain margin and margin utilization"""
        answer = "📊 **Margin** is the capital you need to maintain open positions.\n\n"
        answer += "**Key Concepts**:\n"
        answer += "• **Initial Margin**: Capital needed to open a position\n"
        answer += "• **Maintenance Margin**: Minimum capital to keep position open\n"
        answer += "• **Margin Utilization**: % of your capital currently used\n"
        answer += "• **Available Balance**: Capital available for new positions\n\n"
        answer += "**Safety Thresholds**:\n"
        answer += "• 40% utilization: Bot stops opening new positions\n"
        answer += "• 50% utilization: Warning alerts sent\n"
        answer += "• 70% utilization: Critical alerts - add funds or close positions\n"
        answer += "• 100% utilization: Liquidation risk!"
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'Monitor margin utilization in Liquidation Protection tab',
                'Keep margin utilization below 40% for safety',
                'Add funds if utilization exceeds 50%'
            ],
            'related_links': [
                {'title': 'Liquidation Protection', 'tab': 'liquidation_protection'},
                {'title': 'Add Funds', 'action': 'add_funds'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_liquidation(self) -> Dict[str, Any]:
        """Explain liquidation"""
        answer = "⚠️ **Liquidation** is when the exchange forcibly closes your positions due to insufficient margin.\n\n"
        answer += "**How it happens**:\n"
        answer += "1. Market moves against your positions\n"
        answer += "2. Unrealized losses reduce your available balance\n"
        answer += "3. Margin utilization increases\n"
        answer += "4. When maintenance margin is breached, liquidation occurs\n\n"
        answer += "**How we protect you**:\n"
        answer += "• Monitor margin utilization 24/7\n"
        answer += "• Stop opening new positions at 40% utilization\n"
        answer += "• Send critical alerts at 70% utilization\n"
        answer += "• Auto-close positions if needed\n\n"
        answer += "**Best Practice**: Always keep 60% of your capital as buffer."
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'Monitor liquidation distance in Liquidation Protection tab',
                'Keep margin utilization below 40%',
                'Set up Telegram alerts for critical warnings'
            ],
            'related_links': [
                {'title': 'Liquidation Protection', 'tab': 'liquidation_protection'},
                {'title': 'Guardian Bot', 'tab': 'guardian'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_grid_step(self) -> Dict[str, Any]:
        """Explain grid step"""
        grid_step = self.bot_context['config'].get('GRID_STEP_INR', '1000')
        
        answer = f"📏 **Grid Step** is the price difference between consecutive buy orders.\n\n"
        answer += f"**Current Setting**: ₹{grid_step}\n\n"
        answer += "**How it works**:\n"
        answer += "• Bot places buy orders at regular intervals (grid steps)\n"
        answer += "• Each position has a target price = entry + grid step\n"
        answer += "• Larger step = fewer positions, lower risk, lower profit\n"
        answer += "• Smaller step = more positions, higher risk, higher profit\n\n"
        answer += "**Choosing the right step**:\n"
        answer += "• Volatile market: Use larger step (₹1500-2000)\n"
        answer += "• Stable market: Use smaller step (₹500-1000)\n"
        answer += "• Consider your capital and risk tolerance"
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'Adjust grid step in Configuration tab',
                'Increase step size in volatile markets',
                'Test different step sizes in backtest'
            ],
            'related_links': [
                {'title': 'Configuration', 'tab': 'configuration'},
                {'title': 'Backtest', 'url': 'http://localhost:5556'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_positions(self) -> Dict[str, Any]:
        """Explain current positions"""
        positions = self.bot_context['positions']
        
        answer = f"📊 **Open Positions**: {len(positions)}\n\n"
        
        if positions:
            total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
            answer += f"**Total PnL**: ₹{total_pnl:,.2f}\n\n"
            answer += "**Position Details**:\n"
            for i, pos in enumerate(positions[:5], 1):  # Show first 5
                entry = pos.get('entry_price', 0)
                current = pos.get('current_price', 0)
                pnl = pos.get('unrealized_pnl', 0)
                answer += f"{i}. Entry: ₹{entry:,.2f} | Current: ₹{current:,.2f} | PnL: ₹{pnl:,.2f}\n"
            
            if len(positions) > 5:
                answer += f"\n...and {len(positions) - 5} more positions"
        else:
            answer += "No open positions currently."
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'View detailed positions in Monitoring tab',
                'Check PnL trends in the dashboard',
                'Consider closing losing positions if needed'
            ],
            'related_links': [
                {'title': 'Monitoring', 'tab': 'monitoring'},
                {'title': 'View Positions', 'action': 'view_positions'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_pnl(self) -> Dict[str, Any]:
        """Explain PnL"""
        positions = self.bot_context['positions']
        total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
        
        answer = f"💰 **Profit & Loss (PnL)**: ₹{total_pnl:,.2f}\n\n"
        answer += "**Understanding PnL**:\n"
        answer += "• **Unrealized PnL**: Profit/loss on open positions (not yet closed)\n"
        answer += "• **Realized PnL**: Profit/loss on closed positions (actual profit)\n"
        answer += "• **Total PnL**: Unrealized + Realized\n\n"
        answer += "**PnL Calculation**:\n"
        answer += "• For each position: (Current Price - Entry Price) × Size\n"
        answer += "• Positive PnL = Profit 🟢\n"
        answer += "• Negative PnL = Loss 🔴\n\n"
        answer += "**Tip**: Don't panic on temporary losses - grid trading works over time!"
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'View PnL history in Reports',
                'Track daily PnL trends',
                'Set realistic profit targets'
            ],
            'related_links': [
                {'title': 'Monitoring', 'tab': 'monitoring'},
                {'title': 'View Reports', 'action': 'view_reports'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_risk(self) -> Dict[str, Any]:
        """Explain risk management"""
        answer = "🛡️ **Risk Management** is crucial for long-term success in trading.\n\n"
        answer += "**Your Bot's Risk Features**:\n"
        answer += "1. **Loss Limits**: Auto-close at predefined loss\n"
        answer += "2. **Margin Monitoring**: Prevent liquidation\n"
        answer += "3. **Volatility Safety**: Stop trading in high volatility\n"
        answer += "4. **Capital Protection**: Equity floor, drawdown cap\n"
        answer += "5. **Order Confirmation Guard**: Prevent cascading orders\n"
        answer += "6. **Circuit Breaker**: Stop on API failures\n\n"
        answer += "**Best Practices**:\n"
        answer += "• Never risk more than 2-3% per trade\n"
        answer += "• Keep 60% capital as buffer\n"
        answer += "• Use stop losses (loss limits)\n"
        answer += "• Don't overtrade (respect position limits)\n"
        answer += "• Monitor your bot daily"
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'Review all safety features in Robustness tab',
                'Set appropriate loss limits',
                'Enable all protection features'
            ],
            'related_links': [
                {'title': 'Robustness Features', 'tab': 'robustness'},
                {'title': 'Capital Protection', 'tab': 'capital_protection'},
                {'title': 'Liquidation Protection', 'tab': 'liquidation_protection'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_how_it_works(self) -> Dict[str, Any]:
        """Explain how the bot works"""
        answer = "🤖 **How GridBot Pro Works**:\n\n"
        answer += "**1. Grid Strategy**:\n"
        answer += "• Places buy orders at regular intervals (grid steps)\n"
        answer += "• Each buy has a corresponding sell (target price)\n"
        answer += "• Profits from price oscillations\n\n"
        answer += "**2. Order Flow**:\n"
        answer += "• Bot monitors market price\n"
        answer += "• Places buy order when price hits grid level\n"
        answer += "• Immediately places sell order (target price)\n"
        answer += "• When sell executes, profit is realized\n"
        answer += "• Process repeats continuously\n\n"
        answer += "**3. Safety Systems**:\n"
        answer += "• Multiple layers of protection\n"
        answer += "• Real-time monitoring\n"
        answer += "• Automatic risk management\n\n"
        answer += "**Best For**: Range-bound markets with regular oscillations"
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'Read the complete User Manual',
                'Watch your bot in action in Monitoring tab',
                'Test strategies in Backtest module'
            ],
            'related_links': [
                {'title': 'User Manual', 'url': '/docs/USERMANUAL.md'},
                {'title': 'Monitoring', 'tab': 'monitoring'},
                {'title': 'Backtest', 'url': 'http://localhost:5556'}
            ],
            'source': 'rule_based'
        }
    
    def _explain_concept(self) -> Dict[str, Any]:
        """Explain a concept"""
        answer = "📚 **GridBot Pro** is a sophisticated automated trading system with:\n\n"
        answer += "• **Grid Trading Strategy**: Profit from price oscillations\n"
        answer += "• **Multi-Layer Safety**: 7 protection systems\n"
        answer += "• **Real-Time Monitoring**: 24/7 position tracking\n"
        answer += "• **Mobile Control**: Telegram bot + Tailscale\n"
        answer += "• **Professional UI**: Web dashboard with all features\n\n"
        answer += "**Key Features**:\n"
        answer += "• Blocker tracking and resolution\n"
        answer += "• Liquidation protection\n"
        answer += "• Capital protection\n"
        answer += "• Volatility safety\n"
        answer += "• Guardian bot (24/7 monitoring)\n"
        answer += "• Backtesting module\n"
        answer += "• Comprehensive documentation"
        
        return {
            'success': True,
            'answer': answer,
            'suggestions': [
                'Explore all tabs in the Web UI',
                'Read the User Manual for details',
                'Start with small capital to learn'
            ],
            'related_links': [
                {'title': 'User Manual', 'url': '/docs/USERMANUAL.md'},
                {'title': 'Dashboard', 'tab': 'monitoring'}
            ],
            'source': 'rule_based'
        }
    
    def _get_default_response(self, question: str) -> str:
        """Default response for unmatched questions"""
        return f"I understand you're asking about: \"{question}\"\n\n" \
               f"I'm here to help! Here are some things I can explain:\n\n" \
               f"• Why trading is stopped\n" \
               f"• How blockers work\n" \
               f"• Volatility safety\n" \
               f"• Loss limits and risk management\n" \
               f"• Margin and liquidation\n" \
               f"• Grid step configuration\n" \
               f"• Current positions and PnL\n" \
               f"• How the bot works\n\n" \
               f"Try asking a more specific question, or check the User Manual for detailed documentation."
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for OpenAI"""
        return f"""You are an AI advisor for GridBot Pro, an automated cryptocurrency trading bot.

Current Bot Context:
- Trading Allowed: {self.bot_context['status'].get('trading_allowed', 'Unknown')}
- Active Blockers: {self.bot_context['status'].get('total_blockers', 0)}
- Open Positions: {len(self.bot_context['positions'])}

Your role is to:
1. Answer questions about the bot's behavior and configuration
2. Explain trading concepts in simple terms
3. Provide actionable suggestions for improving trading performance
4. Warn about risks and best practices

Keep responses concise (under 300 words), friendly, and actionable.
Use emojis to make responses engaging.
Always prioritize user safety and risk management."""
    
    def _extract_suggestions(self, answer: str) -> List[str]:
        """Extract action suggestions from AI response"""
        # Simple extraction - look for bullet points or numbered lists
        suggestions = []
        lines = answer.split('\n')
        for line in lines:
            if line.strip().startswith(('•', '-', '*', '1.', '2.', '3.')):
                suggestions.append(line.strip().lstrip('•-*123. '))
        
        return suggestions[:3]  # Return top 3
    
    def _get_related_links(self, question: str) -> List[Dict[str, str]]:
        """Get related links based on question"""
        question_lower = question.lower()
        
        links = []
        
        if 'blocker' in question_lower or 'stop' in question_lower:
            links.append({'title': 'View Blockers', 'action': 'view_blockers'})
            links.append({'title': 'Robustness', 'tab': 'robustness'})
        
        if 'volatility' in question_lower:
            links.append({'title': 'Volatility Monitor', 'tab': 'robustness', 'section': 'volatility'})
        
        if 'margin' in question_lower or 'liquidation' in question_lower:
            links.append({'title': 'Liquidation Protection', 'tab': 'liquidation_protection'})
        
        if 'position' in question_lower or 'pnl' in question_lower:
            links.append({'title': 'Monitoring', 'tab': 'monitoring'})
        
        if 'config' in question_lower or 'setting' in question_lower:
            links.append({'title': 'Configuration', 'tab': 'configuration'})
        
        # Always add user manual
        links.append({'title': 'User Manual', 'url': '/docs/USERMANUAL.md'})
        
        return links[:3]  # Return top 3


# Singleton instance
_advisor_instance = None

def get_ai_advisor() -> AIAdvisor:
    """Get singleton instance of AIAdvisor"""
    global _advisor_instance
    if _advisor_instance is None:
        _advisor_instance = AIAdvisor()
    return _advisor_instance


if __name__ == '__main__':
    # Test the AI Advisor
    advisor = get_ai_advisor()
    
    test_questions = [
        "Why is trading stopped?",
        "What is volatility safety?",
        "How do I manage risk?",
        "Explain my current positions"
    ]
    
    print("=" * 70)
    print("AI ADVISOR TEST")
    print("=" * 70)
    
    for question in test_questions:
        print(f"\n❓ Question: {question}")
        response = advisor.ask(question)
        print(f"\n💡 Answer:\n{response['answer']}")
        print(f"\n📌 Suggestions:")
        for suggestion in response['suggestions']:
            print(f"  • {suggestion}")
        print("\n" + "-" * 70)

