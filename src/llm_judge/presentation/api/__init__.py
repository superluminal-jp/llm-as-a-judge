"""
API Presentation Layer.

This module contains the REST API implementation using FastAPI,
following Clean Architecture principles.
"""

from .app import create_app
from .routes import (
    evaluation_router,
    batch_router,
    criteria_router,
    health_router,
)
from .middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    CORSMiddleware,
)
from .schemas import (
    # Evaluation schemas
    EvaluationRequest,
    EvaluationResponse,
    ComparisonRequest,
    ComparisonResponse,
    MultiCriteriaEvaluationRequest,
    MultiCriteriaEvaluationResponse,
    # Batch schemas
    BatchRequest,
    BatchResponse,
    BatchStatusResponse,
    BatchProgressResponse,
    # Criteria schemas
    CriteriaRequest,
    CriteriaResponse,
    CriteriaListResponse,
    # Common schemas
    ErrorResponse,
    HealthResponse,
    MetadataResponse,
)

__all__ = [
    # App
    "create_app",
    # Routes
    "evaluation_router",
    "batch_router",
    "criteria_router",
    "health_router",
    # Middleware
    "ErrorHandlingMiddleware",
    "LoggingMiddleware",
    "CORSMiddleware",
    # Schemas
    "EvaluationRequest",
    "EvaluationResponse",
    "ComparisonRequest",
    "ComparisonResponse",
    "MultiCriteriaEvaluationRequest",
    "MultiCriteriaEvaluationResponse",
    "BatchRequest",
    "BatchResponse",
    "BatchStatusResponse",
    "BatchProgressResponse",
    "CriteriaRequest",
    "CriteriaResponse",
    "CriteriaListResponse",
    "ErrorResponse",
    "HealthResponse",
    "MetadataResponse",
]
