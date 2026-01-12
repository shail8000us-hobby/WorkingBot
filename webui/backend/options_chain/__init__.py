"""
Options Chain Module
====================
Completely isolated module for fetching and displaying options chain data.
Does NOT interfere with existing options trading functionality.

Author: Options Chain Module
Date: January 5, 2026
"""

from flask import Blueprint

# Create blueprint for options chain routes
options_chain_bp = Blueprint('options_chain', __name__, url_prefix='/api/options-chain')

# Import routes to register them with the blueprint
from . import chain_routes
