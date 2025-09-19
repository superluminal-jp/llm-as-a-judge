"""
Value Objects for the Batch Processing Bounded Context.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
import re

from ..shared_kernel.value_objects import Weight, Priority


class BatchStatus(Enum):
    """Status of a batch processing request."""

    PENDING = "pending"  # Batch created but not started
    PROCESSING = "processing"  # Batch is being processed
    COMPLETED = "completed"  # Batch completed successfully
    FAILED = "failed"  # Batch failed
    CANCELLED = "cancelled"  # Batch was cancelled
    PAUSED = "paused"  # Batch processing is paused


class EvaluationType(Enum):
    """Type of evaluation to perform in batch."""

    SINGLE = "single"  # Single response evaluation
    COMPARISON = "comparison"  # Pairwise comparison
    MULTI_CRITERIA = "multi_criteria"  # Multi-criteria evaluation


@dataclass(frozen=True)
class BatchConfiguration:
    """Configuration for batch processing."""

    max_concurrent_items: int = 10
    retry_failed_items: bool = True
    max_retries_per_item: int = 3
    continue_on_error: bool = True
    timeout_per_item: Optional[float] = None
    timeout_per_batch: Optional[float] = None
    priority: Priority = field(default_factory=lambda: Priority(5))

    def __post_init__(self):
        """Validate batch configuration."""
        if (
            not isinstance(self.max_concurrent_items, int)
            or self.max_concurrent_items <= 0
        ):
            raise ValueError("max_concurrent_items must be a positive integer")
        if self.max_concurrent_items > 100:
            raise ValueError("max_concurrent_items cannot exceed 100")

        if (
            not isinstance(self.max_retries_per_item, int)
            or self.max_retries_per_item < 0
        ):
            raise ValueError("max_retries_per_item must be a non-negative integer")
        if self.max_retries_per_item > 10:
            raise ValueError("max_retries_per_item cannot exceed 10")

        if self.timeout_per_item is not None:
            if (
                not isinstance(self.timeout_per_item, (int, float))
                or self.timeout_per_item <= 0
            ):
                raise ValueError("timeout_per_item must be a positive number")
            if self.timeout_per_item > 3600:  # 1 hour
                raise ValueError("timeout_per_item cannot exceed 3600 seconds")

        if self.timeout_per_batch is not None:
            if (
                not isinstance(self.timeout_per_batch, (int, float))
                or self.timeout_per_batch <= 0
            ):
                raise ValueError("timeout_per_batch must be a positive number")
            if self.timeout_per_batch > 86400:  # 24 hours
                raise ValueError("timeout_per_batch cannot exceed 86400 seconds")

    @property
    def is_high_priority(self) -> bool:
        """Check if batch has high priority."""
        return self.priority.is_high

    @property
    def is_low_priority(self) -> bool:
        """Check if batch has low priority."""
        return self.priority.is_low


@dataclass(frozen=True)
class ProcessingMetrics:
    """Metrics for batch processing performance."""

    total_items: int
    completed_items: int = 0
    failed_items: int = 0
    processing_items: int = 0
    average_processing_time: Optional[float] = None
    items_per_second: Optional[float] = None
    success_rate: float = 0.0
    error_rate: float = 0.0

    def __post_init__(self):
        """Validate and calculate derived metrics."""
        if not isinstance(self.total_items, int) or self.total_items < 0:
            raise ValueError("total_items must be a non-negative integer")

        if not isinstance(self.completed_items, int) or self.completed_items < 0:
            raise ValueError("completed_items must be a non-negative integer")

        if not isinstance(self.failed_items, int) or self.failed_items < 0:
            raise ValueError("failed_items must be a non-negative integer")

        if not isinstance(self.processing_items, int) or self.processing_items < 0:
            raise ValueError("processing_items must be a non-negative integer")

        # Validate totals
        processed = self.completed_items + self.failed_items + self.processing_items
        if processed > self.total_items:
            raise ValueError("Sum of processed items cannot exceed total items")

        # Calculate derived metrics
        if self.total_items > 0:
            processed_items = self.completed_items + self.failed_items
            if processed_items > 0:
                self.success_rate = self.completed_items / processed_items
                self.error_rate = self.failed_items / processed_items

    @property
    def pending_items(self) -> int:
        """Number of items not yet started."""
        return (
            self.total_items
            - self.completed_items
            - self.failed_items
            - self.processing_items
        )

    @property
    def completion_percentage(self) -> float:
        """Completion percentage (0.0 to 1.0)."""
        if self.total_items == 0:
            return 1.0
        return (self.completed_items + self.failed_items) / self.total_items

    @property
    def is_completed(self) -> bool:
        """Check if all items have been processed."""
        return self.pending_items == 0 and self.processing_items == 0

    @property
    def has_failures(self) -> bool:
        """Check if there are any failed items."""
        return self.failed_items > 0

    def update_processing_time(self, processing_time: float) -> "ProcessingMetrics":
        """Update average processing time."""
        if not isinstance(processing_time, (int, float)) or processing_time < 0:
            raise ValueError("processing_time must be a non-negative number")

        # Simple moving average calculation
        if self.average_processing_time is None:
            new_avg = processing_time
        else:
            # Weighted average with recent processing time
            new_avg = (self.average_processing_time * 0.8) + (processing_time * 0.2)

        return ProcessingMetrics(
            total_items=self.total_items,
            completed_items=self.completed_items,
            failed_items=self.failed_items,
            processing_items=self.processing_items,
            average_processing_time=new_avg,
            items_per_second=self.items_per_second,
            success_rate=self.success_rate,
            error_rate=self.error_rate,
        )


@dataclass(frozen=True)
class BatchMetadata:
    """Metadata for batch processing."""

    name: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    custom_attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate batch metadata."""
        if self.name and len(self.name) > 200:
            raise ValueError("Batch name must be less than 200 characters")

        if self.description and len(self.description) > 1000:
            raise ValueError("Batch description must be less than 1000 characters")

        # Validate tags
        for tag in self.tags:
            if not isinstance(tag, str):
                raise ValueError("All tags must be strings")
            if len(tag) > 50:
                raise ValueError("Tag must be less than 50 characters")
            if not re.match(r"^[a-zA-Z0-9_-]+$", tag):
                raise ValueError("Tag contains invalid characters")

        # Validate custom attributes
        for key, value in self.custom_attributes.items():
            if not isinstance(key, str):
                raise ValueError("Custom attribute keys must be strings")
            if len(key) > 50:
                raise ValueError("Custom attribute key must be less than 50 characters")
            if not re.match(r"^[a-zA-Z0-9_-]+$", key):
                raise ValueError("Custom attribute key contains invalid characters")

    def add_tag(self, tag: str) -> "BatchMetadata":
        """Add a tag to the metadata."""
        if not tag or not isinstance(tag, str):
            raise ValueError("Tag must be a non-empty string")
        if len(tag) > 50:
            raise ValueError("Tag must be less than 50 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", tag):
            raise ValueError("Tag contains invalid characters")

        new_tags = list(self.tags)
        if tag not in new_tags:
            new_tags.append(tag)

        return BatchMetadata(
            name=self.name,
            description=self.description,
            tags=new_tags,
            user_id=self.user_id,
            session_id=self.session_id,
            custom_attributes=self.custom_attributes,
        )

    def remove_tag(self, tag: str) -> "BatchMetadata":
        """Remove a tag from the metadata."""
        new_tags = [t for t in self.tags if t != tag]
        return BatchMetadata(
            name=self.name,
            description=self.description,
            tags=new_tags,
            user_id=self.user_id,
            session_id=self.session_id,
            custom_attributes=self.custom_attributes,
        )

    def add_custom_attribute(self, key: str, value: Any) -> "BatchMetadata":
        """Add a custom attribute."""
        if not key or not isinstance(key, str):
            raise ValueError("Key must be a non-empty string")
        if len(key) > 50:
            raise ValueError("Key must be less than 50 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", key):
            raise ValueError("Key contains invalid characters")

        new_attributes = dict(self.custom_attributes)
        new_attributes[key] = value

        return BatchMetadata(
            name=self.name,
            description=self.description,
            tags=self.tags,
            user_id=self.user_id,
            session_id=self.session_id,
            custom_attributes=new_attributes,
        )


@dataclass(frozen=True)
class BatchConstraints:
    """Constraints for batch processing."""

    max_items_per_batch: int = 10000
    max_batch_size_mb: float = 100.0  # Maximum batch size in MB
    max_processing_time_hours: float = 24.0  # Maximum processing time in hours
    max_concurrent_batches: int = 5

    def __post_init__(self):
        """Validate batch constraints."""
        if (
            not isinstance(self.max_items_per_batch, int)
            or self.max_items_per_batch <= 0
        ):
            raise ValueError("max_items_per_batch must be a positive integer")
        if self.max_items_per_batch > 100000:
            raise ValueError("max_items_per_batch cannot exceed 100000")

        if (
            not isinstance(self.max_batch_size_mb, (int, float))
            or self.max_batch_size_mb <= 0
        ):
            raise ValueError("max_batch_size_mb must be a positive number")
        if self.max_batch_size_mb > 1000:  # 1GB
            raise ValueError("max_batch_size_mb cannot exceed 1000")

        if (
            not isinstance(self.max_processing_time_hours, (int, float))
            or self.max_processing_time_hours <= 0
        ):
            raise ValueError("max_processing_time_hours must be a positive number")
        if self.max_processing_time_hours > 168:  # 1 week
            raise ValueError("max_processing_time_hours cannot exceed 168")

        if (
            not isinstance(self.max_concurrent_batches, int)
            or self.max_concurrent_batches <= 0
        ):
            raise ValueError("max_concurrent_batches must be a positive integer")
        if self.max_concurrent_batches > 20:
            raise ValueError("max_concurrent_batches cannot exceed 20")

    def validate_batch_size(self, item_count: int) -> bool:
        """Validate if batch size is within constraints."""
        return item_count <= self.max_items_per_batch

    def validate_processing_time(self, estimated_hours: float) -> bool:
        """Validate if estimated processing time is within constraints."""
        return estimated_hours <= self.max_processing_time_hours
