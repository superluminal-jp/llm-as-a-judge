"""
Batch processing domain specifications.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from ..shared_kernel.value_objects import BatchId
from .entities import BatchRequest, BatchResult, BatchProgress
from .value_objects import BatchStatus


class BatchValidationSpecification(ABC):
    """Abstract base class for batch validation specifications."""

    @abstractmethod
    def is_satisfied_by(self, batch_request: BatchRequest) -> bool:
        """Check if batch request satisfies this specification."""
        pass


class BatchProcessingSpecification(ABC):
    """Abstract base class for batch processing specifications."""

    @abstractmethod
    def is_satisfied_by(self, batch_progress: BatchProgress) -> bool:
        """Check if batch progress satisfies this specification."""
        pass


class BatchCompletionSpecification(ABC):
    """Abstract base class for batch completion specifications."""

    @abstractmethod
    def is_satisfied_by(self, batch_result: BatchResult) -> bool:
        """Check if batch result satisfies this specification."""
        pass


# Concrete specification implementations


class ValidBatchSizeSpecification(BatchValidationSpecification):
    """Specification for valid batch size."""

    def __init__(self, min_size: int = 1, max_size: int = 1000):
        self.min_size = min_size
        self.max_size = max_size

    def is_satisfied_by(self, batch_request: BatchRequest) -> bool:
        return self.min_size <= batch_request.total_items <= self.max_size


class ValidConcurrencySpecification(BatchValidationSpecification):
    """Specification for valid concurrency settings."""

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent

    def is_satisfied_by(self, batch_request: BatchRequest) -> bool:
        return 1 <= batch_request.max_concurrent_items <= self.max_concurrent


class ValidRetrySettingsSpecification(BatchValidationSpecification):
    """Specification for valid retry settings."""

    def __init__(self, max_retries: int = 5):
        self.max_retries = max_retries

    def is_satisfied_by(self, batch_request: BatchRequest) -> bool:
        return 0 <= batch_request.max_retries_per_item <= self.max_retries


class BatchProcessingCompleteSpecification(BatchProcessingSpecification):
    """Specification for batch processing completion."""

    def is_satisfied_by(self, batch_progress: BatchProgress) -> bool:
        return batch_progress.pending_items == 0


class BatchProcessingFailedSpecification(BatchProcessingSpecification):
    """Specification for batch processing failure."""

    def __init__(self, failure_threshold: float = 0.5):
        self.failure_threshold = failure_threshold

    def is_satisfied_by(self, batch_progress: BatchProgress) -> bool:
        if batch_progress.completed_items + batch_progress.failed_items == 0:
            return False
        failure_rate = batch_progress.failed_items / (
            batch_progress.completed_items + batch_progress.failed_items
        )
        return failure_rate >= self.failure_threshold


class BatchSuccessSpecification(BatchCompletionSpecification):
    """Specification for batch success."""

    def __init__(self, min_success_rate: float = 0.8):
        self.min_success_rate = min_success_rate

    def is_satisfied_by(self, batch_result: BatchResult) -> bool:
        return batch_result.success_rate >= self.min_success_rate


class BatchFailureSpecification(BatchCompletionSpecification):
    """Specification for batch failure."""

    def __init__(self, max_success_rate: float = 0.2):
        self.max_success_rate = max_success_rate

    def is_satisfied_by(self, batch_result: BatchResult) -> bool:
        return batch_result.success_rate <= self.max_success_rate


class BatchTimeoutSpecification(BatchCompletionSpecification):
    """Specification for batch timeout."""

    def __init__(self, max_duration_seconds: float = 3600):
        self.max_duration_seconds = max_duration_seconds

    def is_satisfied_by(self, batch_result: BatchResult) -> bool:
        if batch_result.processing_duration is None:
            return False
        return batch_result.processing_duration > self.max_duration_seconds
