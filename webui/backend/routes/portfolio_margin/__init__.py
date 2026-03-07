"""
Portfolio Margin Module

Portfolio margin monitoring and management for Delta Exchange.
Provides REST endpoints and WebSocket integration for real-time margin data.

Created: March 2026
"""

from .routes import portfolio_margin_bp

__all__ = ['portfolio_margin_bp']
