"""
Bot Brain Analyzer Package

Real-time bot brain analysis system that reads source code and generates
visual decision flows, scenarios, and predictions.

Auto-refreshes every 5 seconds - NO manual intervention needed.

Modules:
- code_reader: Reads bot source code files
- ast_parser: Parses Python AST for decision points
- flow_generator: Builds decision flow graph
- sequence_builder: Generates action sequences
- conflict_detector: Detects logic conflicts

Created: October 31, 2025
"""

from .code_reader import BotCodeReader
from .ast_parser import DecisionParser
from .flow_generator import FlowGraphGenerator
from .sequence_builder import SequenceBuilder
from .change_detector import ChangeDetector
from .state_reader import BotStateReader
from .routes import brain_analyzer_bp

__all__ = [
    'BotCodeReader',
    'DecisionParser',
    'FlowGraphGenerator',
    'SequenceBuilder',
    'ChangeDetector',
    'BotStateReader',
    'brain_analyzer_bp'
]

__version__ = '1.0.0'

