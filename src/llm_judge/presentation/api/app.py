"""
FastAPI application factory.

Creates and configures the FastAPI application with proper middleware,
routing, and error handling following Clean Architecture principles.
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import time
from typing import Dict, Any

from .middleware import ErrorHandlingMiddleware, LoggingMiddleware
from .routes import evaluation_router, batch_router, criteria_router, health_router
from .schemas import ErrorResponse
from ...infrastructure.config.config import LLMConfig


logger = logging.getLogger(__name__)


def create_app(config: LLMConfig) -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="LLM-as-a-Judge API",
        description="Production-ready evaluation system for language model responses",
        version="0.3.0",
        docs_url="/docs" if config.log_level == "DEBUG" else None,
        redoc_url="/redoc" if config.log_level == "DEBUG" else None,
        openapi_url="/openapi.json" if config.log_level == "DEBUG" else None,
    )

    # Add middleware
    _add_middleware(app, config)

    # Add routes
    _add_routes(app)

    # Add exception handlers
    _add_exception_handlers(app)

    # Add startup and shutdown events
    _add_lifecycle_events(app, config)

    return app


def _add_middleware(app: FastAPI, config: LLMConfig) -> None:
    """Add middleware to the application."""

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=(
            ["*"] if config.log_level == "DEBUG" else ["https://yourdomain.com"]
        ),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=(
            ["*"]
            if config.log_level == "DEBUG"
            else ["yourdomain.com", "*.yourdomain.com"]
        ),
    )

    # Custom middleware
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(LoggingMiddleware)


def _add_routes(app: FastAPI) -> None:
    """Add routes to the application."""

    # Health check
    app.include_router(health_router, prefix="/health", tags=["health"])

    # API routes
    app.include_router(
        evaluation_router, prefix="/api/v1/evaluations", tags=["evaluations"]
    )
    app.include_router(batch_router, prefix="/api/v1/batches", tags=["batches"])
    app.include_router(criteria_router, prefix="/api/v1/criteria", tags=["criteria"])

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "LLM-as-a-Judge API",
            "version": "0.3.0",
            "status": "operational",
            "docs": "/docs" if app.docs_url else "disabled",
        }


def _add_exception_handlers(app: FastAPI) -> None:
    """Add global exception handlers."""

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"Value error: {exc}")
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="VALIDATION_ERROR",
                message=str(exc),
                details={"type": "ValueError"},
            ).dict(),
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError):
        logger.warning(f"Key error: {exc}")
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="MISSING_FIELD",
                message=f"Required field missing: {exc}",
                details={"type": "KeyError"},
            ).dict(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                details={"type": type(exc).__name__},
            ).dict(),
        )


def _add_lifecycle_events(app: FastAPI, config: LLMConfig) -> None:
    """Add startup and shutdown events."""

    @app.on_event("startup")
    async def startup_event():
        """Application startup event."""
        logger.info("Starting LLM-as-a-Judge API")
        logger.info(
            f"Configuration: provider={config.default_provider}, log_level={config.log_level}"
        )

        # Initialize services here
        # app.state.llm_provider = await create_llm_provider(config)
        # app.state.evaluation_service = EvaluationService(app.state.llm_provider)

        logger.info("API startup completed")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event."""
        logger.info("Shutting down LLM-as-a-Judge API")

        # Cleanup services here
        # if hasattr(app.state, 'llm_provider'):
        #     await app.state.llm_provider.close()

        logger.info("API shutdown completed")


# Request/Response middleware for logging and metrics
@app.middleware("http")
async def request_response_middleware(request: Request, call_next):
    """Middleware for request/response logging and metrics."""
    start_time = time.time()

    # Log request
    logger.info(f"Request: {request.method} {request.url}")

    # Process request
    response = await call_next(request)

    # Calculate processing time
    process_time = time.time() - start_time

    # Log response
    logger.info(
        f"Response: {response.status_code} - "
        f"{request.method} {request.url} - "
        f"{process_time:.3f}s"
    )

    # Add processing time header
    response.headers["X-Process-Time"] = str(process_time)

    return response
