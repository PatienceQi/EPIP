"""Core service modules for EPIP."""

from .data_processor import DataProcessor
from .document_converter import DocumentConverter
from .entity_extractor import (
    EntityDisambiguator,
    EntityEvaluator,
    EntityExtractionConfig,
    EntityReport,
    EntityReportGenerator,
)
from .hallucination import HallucinationGuard
from .kg_builder import KGBuilder, KnowledgeGraphBuilder
from .kg_manager import (
    AuditEntry,
    BatchOperation,
    BatchProcessor,
    KGManager,
    OperationType,
)
from .kg_quality import (
    EntityQualityMetrics,
    GraphQualityMetrics,
    KGQualityEvaluator,
    KGQualityReport,
    QualityReportGenerator,
    QualityThresholds,
    RelationQualityMetrics,
)
from .query_engine import QueryEngine
from .relation_extractor import (
    GraphHealthReport,
    GraphValidator,
    RelationExtractionConfig,
    RelationReport,
    RelationReportGenerator,
    SubgraphAnalyzer,
    SubgraphInfo,
)

__all__ = [
    "DataProcessor",
    "EntityDisambiguator",
    "EntityEvaluator",
    "EntityExtractionConfig",
    "EntityReport",
    "EntityReportGenerator",
    "GraphHealthReport",
    "GraphValidator",
    "DocumentConverter",
    "HallucinationGuard",
    "AuditEntry",
    "BatchOperation",
    "BatchProcessor",
    "KGBuilder",
    "KGManager",
    "KnowledgeGraphBuilder",
    "OperationType",
    "EntityQualityMetrics",
    "GraphQualityMetrics",
    "KGQualityReport",
    "KGQualityEvaluator",
    "QualityReportGenerator",
    "QualityThresholds",
    "RelationQualityMetrics",
    "RelationExtractionConfig",
    "RelationReport",
    "RelationReportGenerator",
    "SubgraphAnalyzer",
    "SubgraphInfo",
    "QueryEngine",
]
