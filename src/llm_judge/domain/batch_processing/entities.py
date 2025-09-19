"""
Batch processing domain entities.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

from ..shared_kernel.value_objects import BatchId, EntityId, Timestamp
from .value_objects import BatchStatus, EvaluationType


@dataclass
class BatchRequest:
    """Entity representing a batch processing request."""

    name: str
    description: Optional[str] = None
    max_concurrent_items: int = 5
    retry_failed_items: bool = True
    max_retries_per_item: int = 3
    continue_on_error: bool = True
    batch_id: BatchId = field(default_factory=BatchId)
    created_at: Timestamp = field(default_factory=Timestamp)
    items: List["BatchEvaluationItem"] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        """Get total number of items in the batch."""
        return len(self.items)

    def add_item(self, item: "BatchEvaluationItem") -> None:
        """Add an item to the batch."""
        self.items.append(item)


@dataclass
class BatchEvaluationItem:
    """Entity representing a single evaluation item in a batch."""

    evaluation_type: EvaluationType
    prompt: str
    response: str
    model: str
    criteria: str = "overall quality"
    item_id: str = field(default_factory=lambda: str(uuid4()))
    result: Optional[Any] = None
    error: Optional[str] = None
    processed_at: Optional[Timestamp] = None
    processing_duration: Optional[float] = None
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        """Check if the item is completed."""
        return self.result is not None or self.error is not None

    @property
    def has_error(self) -> bool:
        """Check if the item has an error."""
        return self.error is not None


@dataclass
class BatchProgress:
    """Entity representing batch processing progress."""

    batch_id: BatchId
    total_items: int
    started_at: Timestamp
    processing_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    items_per_second: Optional[float] = None
    estimated_completion: Optional[Timestamp] = None

    @property
    def pending_items(self) -> int:
        """Get number of pending items."""
        return (
            self.total_items
            - self.processing_items
            - self.completed_items
            - self.failed_items
        )

    @property
    def success_rate(self) -> float:
        """Get success rate as a percentage."""
        processed = self.completed_items + self.failed_items
        if processed == 0:
            return 0.0
        return (self.completed_items / processed) * 100


@dataclass
class BatchResult:
    """Entity representing the result of batch processing."""

    batch_request: BatchRequest
    status: BatchStatus
    started_at: Timestamp
    completed_at: Optional[Timestamp] = None
    processing_duration: Optional[float] = None
    successful_items: List[BatchEvaluationItem] = field(default_factory=list)
    failed_items: List[BatchEvaluationItem] = field(default_factory=list)
    average_processing_time: Optional[float] = None

    @property
    def total_items(self) -> int:
        """Get total number of items."""
        return len(self.successful_items) + len(self.failed_items)

    @property
    def success_rate(self) -> float:
        """Get success rate as a percentage."""
        if self.total_items == 0:
            return 100.0
        return (len(self.successful_items) / self.total_items) * 100

    @property
    def is_completed(self) -> bool:
        """Check if batch processing is completed."""
        return self.status in [
            BatchStatus.COMPLETED,
            BatchStatus.FAILED,
            BatchStatus.CANCELLED,
        ]

    def get_results_by_type(
        self, evaluation_type: EvaluationType
    ) -> List[BatchEvaluationItem]:
        """Get results filtered by evaluation type."""
        all_items = self.successful_items + self.failed_items
        return [item for item in all_items if item.evaluation_type == evaluation_type]

    def get_summary(self) -> Dict[str, Any]:
        """Get batch result summary."""
        return {
            "batch_id": str(self.batch_request.batch_id),
            "status": self.status.value,
            "total_items": self.total_items,
            "successful_items": len(self.successful_items),
            "failed_items": len(self.failed_items),
            "success_rate": self.success_rate,
            "processing_duration": self.processing_duration,
            "average_processing_time": self.average_processing_time,
        }
