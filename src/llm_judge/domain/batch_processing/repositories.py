"""
Batch processing domain repositories.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..shared_kernel.value_objects import BatchId
from .entities import BatchRequest, BatchResult, BatchProgress
from .value_objects import BatchStatus


class BatchRepository(ABC):
    """Abstract repository for batch persistence."""

    @abstractmethod
    async def save_batch_request(self, batch_request: BatchRequest) -> None:
        """Save a batch request."""
        pass

    @abstractmethod
    async def save_batch_result(self, batch_result: BatchResult) -> None:
        """Save a batch result."""
        pass

    @abstractmethod
    async def find_batch_request_by_id(
        self, batch_id: BatchId
    ) -> Optional[BatchRequest]:
        """Find batch request by ID."""
        pass

    @abstractmethod
    async def find_batch_result_by_id(self, batch_id: BatchId) -> Optional[BatchResult]:
        """Find batch result by ID."""
        pass

    @abstractmethod
    async def find_batches_by_status(
        self,
        status: BatchStatus,
        limit: int = 100,
    ) -> List[BatchRequest]:
        """Find batches by status."""
        pass

    @abstractmethod
    async def delete_batch(self, batch_id: BatchId) -> None:
        """Delete a batch."""
        pass

    @abstractmethod
    async def count_batches(self) -> int:
        """Count total batches."""
        pass


class BatchProgressRepository(ABC):
    """Abstract repository for batch progress persistence."""

    @abstractmethod
    async def save_batch_progress(self, batch_progress: BatchProgress) -> None:
        """Save batch progress."""
        pass

    @abstractmethod
    async def find_batch_progress_by_id(
        self, batch_id: BatchId
    ) -> Optional[BatchProgress]:
        """Find batch progress by ID."""
        pass

    @abstractmethod
    async def update_batch_progress(
        self,
        batch_id: BatchId,
        progress_data: Dict[str, Any],
    ) -> None:
        """Update batch progress."""
        pass

    @abstractmethod
    async def delete_batch_progress(self, batch_id: BatchId) -> None:
        """Delete batch progress."""
        pass

    @abstractmethod
    async def get_active_batch_progress(self) -> List[BatchProgress]:
        """Get all active batch progress."""
        pass
