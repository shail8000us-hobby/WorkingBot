"""
Futures Routes Package

This package handles all API routes for futures position management.
Completely separate from options and grid bot routes.

Created: January 17, 2026
Purpose: Display futures positions in WebUI
"""

from .futures_api import futures_bp

__all__ = ['futures_bp']
