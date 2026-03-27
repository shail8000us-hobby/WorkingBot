"""
OI Aggregator — Blueprint Package

Multi-exchange Open Interest dashboard (read-only analytics).
Completely isolated from MMM / IC / SSDH trading modules.

Created: March 27, 2026
"""

from .oi_api import oi_bp, init_oi_websocket

__all__ = ['oi_bp', 'init_oi_websocket']
