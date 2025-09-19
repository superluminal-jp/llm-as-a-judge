"""
Batch processing domain services.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Callable
from ..shared_kernel.value_objects import BatchId, EntityId
from .entities import BatchRequest, BatchResult, BatchProgress, BatchEvaluationItem
from .value_objects import BatchStatus


class BatchProcessingService(ABC):
    """Abstract service for batch processing operations."""

    @abstractmethod
    async def process_batch_request(
        self,
        batch_request: BatchRequest,
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
    ) -> BatchResult:
        """Process a batch request."""
        pass

    @abstractmethod
    async def cancel_batch(self, batch_id: BatchId) -> bool:
        """Cancel a batch processing."""
        pass

    @abstractmethod
    async def get_batch_status(self, batch_id: BatchId) -> Optional[BatchStatus]:
        """Get batch processing status."""
        pass


class BatchOrchestrationService(ABC):
    """Abstract service for batch orchestration."""

    @abstractmethod
    async def orchestrate_batch_processing(
        self,
        batch_request: BatchRequest,
    ) -> BatchResult:
        """Orchestrate batch processing workflow."""
        pass

    @abstractmethod
    async def schedule_batch_items(
        self,
        batch_request: BatchRequest,
    ) -> List[BatchEvaluationItem]:
        """Schedule batch items for processing."""
        pass

    @abstractmethod
    async def coordinate_concurrent_processing(
        self,
        items: List[BatchEvaluationItem],
        max_concurrent: int,
    ) -> List[BatchEvaluationItem]:
        """Coordinate concurrent processing of batch items."""
        pass


class BatchMonitoringService(ABC):
    """Abstract service for batch monitoring."""

    @abstractmethod
    async def monitor_batch_progress(
        self,
        batch_id: BatchId,
    ) -> Optional[BatchProgress]:
        """Monitor batch processing progress."""
        pass

    @abstractmethod
    async def track_batch_metrics(
        self,
        batch_id: BatchId,
    ) -> Dict[str, Any]:
        """Track batch processing metrics."""
        pass

    @abstractmethod
    async def get_batch_health_status(
        self,
        batch_id: BatchId,
    ) -> str:
        """Get batch health status."""
        pass
