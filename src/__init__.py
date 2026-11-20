"""
Segnetics Pixel Studio - Universal Engineering Suite for Segnetics Pixel PLCs.
"""

from .core.psl_parser import PSLParser
from .core.psl_analyzer import PSLAnalyzer
from .core.psl_optimizer import PSLOptimizer
from .core.dsl_models import FBDProgram, FBDBlock, FBDWire
from .core.logger import setup_logger

__version__ = "2.5.0"
