#!/usr/bin/env python3
"""
Market News Aggregator - Real-time news feed for crypto markets

This module aggregates news from multiple sources, filters for relevance,
and displays them in priority order.
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load API keys only
load_dotenv('secrets/api_keys.env', verbose=False)

from config.loader import get_config

CONFIG_FILE = Path(__file__).parent.parent.parent / 'config.yaml'


class NewsAggregator:
    """
    Aggregates news from multiple sources and filters for relevance.
    """
    
    def __init__(self):
        self.workspace_root = Path(__file__).parent.parent.parent
        self.cache_file = self.workspace_root / 'bot' / 'news' / '.news_cache.json'
        self.cache_file.parent.mkdir(exist_ok=True)
        
        # API keys (optional)
        self.newsapi_key = os.getenv('NEWS_API_KEY', '')
        self.cryptocompare_key = os.getenv('CRYPTOCOMPARE_API_KEY', '')
        
        # Cache settings
        self.cache_duration = 300  # 5 minutes
        
        # Initialize cache
        self.news_cache = self._load_cache()
    
    def _load_cache(self) -> List[Dict]:
        """Load news from cache"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    # Check if cache is still valid
                    if data.get('timestamp'):
                        cache_time = datetime.fromisoformat(data['timestamp'])
                        if datetime.now() - cache_time < timedelta(seconds=self.cache_duration):
                            return data.get('news', [])
            except Exception:
                pass
        return []
    
    def _save_cache(self, news: List[Dict]):
        """Save news to cache"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'news': news
                }, f, indent=2)
        except Exception:
            pass
    
    def get_news(self, limit: int = 10, priority: str = 'all') -> List[Dict]:
        """
        Get news feed.
        
        Args:
            limit: Maximum number of news items
            priority: Filter by priority (all, critical, high, medium, low)
            
        Returns:
            List of news items
        """
        # Try to get from cache first
        if self.news_cache:
            news = self.news_cache
        else:
            # Fetch fresh news
            news = self._fetch_news()
            self.news_cache = news
            self._save_cache(news)
        
        # Filter by priority
        if priority != 'all':
            news = [n for n in news if n.get('priority') == priority]
        
        # Sort by priority and timestamp
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        news.sort(key=lambda x: (priority_order.get(x.get('priority', 'low'), 3), -x.get('timestamp', 0)))
        
        return news[:limit]
    
    def refresh(self):
        """Force refresh news feed"""
        self.news_cache = self._fetch_news()
        self._save_cache(self.news_cache)
    
    def _fetch_news(self) -> List[Dict]:
        """Fetch news from all sources"""
        all_news = []
        
        # Source 1: Delta Exchange announcements (simulated)
        all_news.extend(self._fetch_delta_announcements())
        
        # Source 2: Crypto-specific news (simulated or via API)
        all_news.extend(self._fetch_crypto_news())
        
        # Source 3: Bot-specific events
        all_news.extend(self._fetch_bot_events())
        
        # Source 4: Market alerts (volatility, volume spikes)
        all_news.extend(self._fetch_market_alerts())
        
        return all_news
    
    def _fetch_delta_announcements(self) -> List[Dict]:
        """Fetch Delta Exchange announcements"""
        # In a real implementation, this would scrape Delta's announcements page
        # For now, return simulated news
        return [
            {
                'id': 'delta_1',
                'title': 'Delta Exchange System Update',
                'summary': 'Scheduled maintenance on Sunday 2 AM - 4 AM IST',
                'source': 'Delta Exchange',
                'priority': 'high',
                'category': 'exchange',
                'timestamp': datetime.now().timestamp(),
                'url': 'https://www.delta.exchange',
                'actionable': True,
                'action_text': 'Close positions before maintenance'
            }
        ]
    
    def _fetch_crypto_news(self) -> List[Dict]:
        """Fetch crypto news from APIs or RSS feeds"""
        news = []
        
        # Try CryptoCompare API if key is available
        if self.cryptocompare_key:
            try:
                url = f'https://min-api.cryptocompare.com/data/v2/news/?lang=EN&api_key={self.cryptocompare_key}'
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get('Data', [])[:5]:
                        news.append({
                            'id': f"cc_{item.get('id', '')}",
                            'title': item.get('title', ''),
                            'summary': item.get('body', '')[:200] + '...',
                            'source': item.get('source', 'CryptoCompare'),
                            'priority': self._determine_priority(item.get('title', '')),
                            'category': 'market',
                            'timestamp': item.get('published_on', datetime.now().timestamp()),
                            'url': item.get('url', ''),
                            'actionable': False
                        })
            except Exception:
                pass
        
        # Fallback: Simulated news
        if not news:
            news = [
                {
                    'id': 'crypto_1',
                    'title': 'Bitcoin Volatility Increases',
                    'summary': 'BTC price volatility has increased by 15% in the last 24 hours. Consider adjusting your grid step size.',
                    'source': 'Market Analysis',
                    'priority': 'medium',
                    'category': 'market',
                    'timestamp': datetime.now().timestamp(),
                    'url': '#',
                    'actionable': True,
                    'action_text': 'Adjust volatility settings'
                },
                {
                    'id': 'crypto_2',
                    'title': 'Low Trading Volume Alert',
                    'summary': 'Trading volume is 30% below average. Grid trading may be less effective in low-volume conditions.',
                    'source': 'Market Analysis',
                    'priority': 'low',
                    'category': 'market',
                    'timestamp': datetime.now().timestamp() - 3600,
                    'url': '#',
                    'actionable': False
                }
            ]
        
        return news
    
    def _fetch_bot_events(self) -> List[Dict]:
        """Fetch bot-specific events"""
        news = []
        
        # Check for recent bot events
        try:
            from bot.safety.blocker_tracker import get_blocker_tracker
            
            tracker = get_blocker_tracker()
            result = tracker.check_all_blockers()
            
            # If there are blockers, create news items
            if result['total_blockers'] > 0:
                for blocker in result['blockers']:
                    if blocker['active'] and blocker['severity'] in ['critical', 'warning']:
                        news.append({
                            'id': f"bot_{blocker['id']}",
                            'title': f"Bot Alert: {blocker['name']}",
                            'summary': blocker['message'],
                            'source': 'GridBot Pro',
                            'priority': 'critical' if blocker['severity'] == 'critical' else 'high',
                            'category': 'bot',
                            'timestamp': datetime.now().timestamp(),
                            'url': '#',
                            'actionable': True,
                            'action_text': 'Fix blocker',
                            'action_link': blocker.get('deep_link', {})
                        })
        except Exception:
            pass
        
        return news
    
    def _fetch_market_alerts(self) -> List[Dict]:
        """Fetch market alerts (volatility, volume, etc.)"""
        news = []
        
        # Check volatility
        try:
            volatility_file = self.workspace_root / 'bot' / 'volatility' / '.volatility_status.json'
            if volatility_file.exists():
                with open(volatility_file, 'r') as f:
                    vol_status = json.load(f)
                    
                    if not vol_status.get('trading_allowed', True):
                        reasons = ', '.join(vol_status.get('block_reasons', []))
                        news.append({
                            'id': 'alert_volatility',
                            'title': 'High Volatility Alert',
                            'summary': f'Trading paused due to high volatility: {reasons}',
                            'source': 'Volatility Monitor',
                            'priority': 'high',
                            'category': 'alert',
                            'timestamp': datetime.now().timestamp(),
                            'url': '#',
                            'actionable': True,
                            'action_text': 'View volatility settings',
                            'action_link': {'tab': 'robustness', 'section': 'volatility'}
                        })
        except Exception:
            pass
        
        # Check margin utilization
        try:
            guardian_health_file = self.workspace_root / '.guardian_health.json'
            if guardian_health_file.exists():
                with open(guardian_health_file, 'r') as f:
                    health = json.load(f)
                    liq_data = health.get('liquidation', {})
                    
                    margin_util = liq_data.get('margin_utilization', 0)
                    if margin_util > 50:
                        priority = 'critical' if margin_util > 70 else 'high'
                        news.append({
                            'id': 'alert_margin',
                            'title': f'Margin Utilization: {margin_util:.1f}%',
                            'summary': f'Your margin utilization is at {margin_util:.1f}%. Consider adding funds or closing positions.',
                            'source': 'Liquidation Monitor',
                            'priority': priority,
                            'category': 'alert',
                            'timestamp': datetime.now().timestamp(),
                            'url': '#',
                            'actionable': True,
                            'action_text': 'View liquidation protection',
                            'action_link': {'tab': 'liquidation_protection'}
                        })
        except Exception:
            pass
        
        return news
    
    def _determine_priority(self, title: str) -> str:
        """Determine news priority based on keywords"""
        title_lower = title.lower()
        
        # Critical keywords
        critical_keywords = ['hack', 'security', 'breach', 'crash', 'halt', 'suspend', 'emergency']
        if any(kw in title_lower for kw in critical_keywords):
            return 'critical'
        
        # High priority keywords
        high_keywords = ['regulation', 'ban', 'sec', 'government', 'major', 'breaking']
        if any(kw in title_lower for kw in high_keywords):
            return 'high'
        
        # Medium priority keywords
        medium_keywords = ['bitcoin', 'btc', 'volatility', 'price', 'market']
        if any(kw in title_lower for kw in medium_keywords):
            return 'medium'
        
        return 'low'


# Singleton instance
_aggregator_instance = None

def get_news_aggregator() -> NewsAggregator:
    """Get singleton instance of NewsAggregator"""
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = NewsAggregator()
    return _aggregator_instance


if __name__ == '__main__':
    # Test the news aggregator
    aggregator = get_news_aggregator()
    
    print("=" * 70)
    print("NEWS AGGREGATOR TEST")
    print("=" * 70)
    
    news = aggregator.get_news(limit=10)
    
    print(f"\nTotal news items: {len(news)}\n")
    
    for item in news:
        priority_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🔵'
        }.get(item['priority'], '⚪')
        
        print(f"{priority_emoji} [{item['priority'].upper()}] {item['title']}")
        print(f"   Source: {item['source']}")
        print(f"   {item['summary'][:100]}...")
        if item.get('actionable'):
            print(f"   Action: {item.get('action_text', 'N/A')}")
        print()

