"""
RAGAS评测系统
完整的RAG系统评测解决方案
"""

__version__ = "1.0.0"
__author__ = "ACRAC Team"

from .core.data_extractor import RAGASDataExtractor
from .core.evaluator import RAGASEvaluator
from .core.analyzer import RAGASAnalyzer
from .reports.generator import RAGASReportGenerator

__all__ = [
    'RAGASDataExtractor',
    'RAGASEvaluator', 
    'RAGASAnalyzer',
    'RAGASReportGenerator'
]