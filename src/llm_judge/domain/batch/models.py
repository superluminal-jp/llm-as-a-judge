"""
Batch processing domain models.

Contains the core domain entities and value objects for batch evaluation processing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from uuid import uuid4

# Using TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import CandidateResponse, EvaluationResult
else:
    # Define minimal interfaces for runtime
    class CandidateResponse:
        def __init__(self, prompt: str, response: str, model: str = "unknown", metadata: Dict[str, Any] = None):
            self.prompt = prompt
            self.response = response  
            self.model = model
            self.metadata = metadata or {}
    
    class EvaluationResult:
        def __init__(self, score: float, reasoning: str, confidence: float = 0.0, metadata: Dict[str, Any] = None):
            self.score = score
            self.reasoning = reasoning
            self.confidence = confidence
            self.metadata = metadata or {}


class BatchStatus(Enum):
    """Status of a batch evaluation request."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvaluationType(Enum):
    """Type of evaluation to perform."""
    SINGLE = "single"
    COMPARISON = "comparison"


@dataclass
class BatchEvaluationItem:
    """A single evaluation item within a batch request."""
    
    # Unique identifier within the batch
    item_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Type of evaluation
    evaluation_type: EvaluationType = EvaluationType.SINGLE
    
    # For single evaluations
    candidate_response: Optional[CandidateResponse] = None
    criteria: str = "overall quality"
    
    # For comparison evaluations  
    candidate_a: Optional[CandidateResponse] = None
    candidate_b: Optional[CandidateResponse] = None
    
    # Results (populated after processing)
    result: Optional[Union[EvaluationResult, Dict[str, Any]]] = None
    error: Optional[str] = None
    processed_at: Optional[datetime] = None
    processing_duration: Optional[float] = None
    
    # Metadata
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate evaluation item configuration."""
        if self.evaluation_type == EvaluationType.SINGLE:
            if not self.candidate_response:
                raise ValueError("Single evaluation requires candidate_response")
        elif self.evaluation_type == EvaluationType.COMPARISON:
            if not self.candidate_a or not self.candidate_b:
                raise ValueError("Comparison evaluation requires both candidate_a and candidate_b")
            if self.candidate_a.prompt != self.candidate_b.prompt:
                raise ValueError("Comparison candidates must have the same prompt")
    
    @property
    def is_completed(self) -> bool:
        """Check if this item has been processed."""
        return self.result is not None or self.error is not None
    
    @property
    def has_error(self) -> bool:
        """Check if this item encountered an error."""
        return self.error is not None


@dataclass 
class BatchRequest:
    """A batch of evaluation requests to be processed."""
    
    # Unique batch identifier
    batch_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Batch metadata
    name: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    # Evaluation items
    items: List[BatchEvaluationItem] = field(default_factory=list)
    
    # Processing configuration
    max_concurrent_items: int = 10
    retry_failed_items: bool = True
    max_retries_per_item: int = 3
    continue_on_error: bool = True
    
    # Judge configuration
    judge_provider: Optional[str] = None
    judge_model: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate batch request configuration."""
        if self.max_concurrent_items <= 0:
            raise ValueError("max_concurrent_items must be greater than 0")
            
        if self.max_retries_per_item < 0:
            raise ValueError("max_retries_per_item cannot be negative")
    
    @property
    def total_items(self) -> int:
        """Total number of items in the batch."""
        return len(self.items)
    
    @property
    def single_evaluations(self) -> List[BatchEvaluationItem]:
        """Get all single evaluation items."""
        return [item for item in self.items if item.evaluation_type == EvaluationType.SINGLE]
    
    @property
    def comparison_evaluations(self) -> List[BatchEvaluationItem]:
        """Get all comparison evaluation items."""
        return [item for item in self.items if item.evaluation_type == EvaluationType.COMPARISON]
    
    def add_single_evaluation(self, candidate: CandidateResponse, criteria: str = "overall quality", 
                            priority: int = 0, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a single evaluation to the batch."""
        item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE,
            candidate_response=candidate,
            criteria=criteria,
            priority=priority,
            metadata=metadata or {}
        )
        self.items.append(item)
        return item.item_id
    
    def add_comparison_evaluation(self, candidate_a: CandidateResponse, candidate_b: CandidateResponse,
                                priority: int = 0, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a comparison evaluation to the batch."""
        item = BatchEvaluationItem(
            evaluation_type=EvaluationType.COMPARISON,
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            priority=priority,
            metadata=metadata or {}
        )
        self.items.append(item)
        return item.item_id
    
    def get_items_by_priority(self) -> List[BatchEvaluationItem]:
        """Get items sorted by priority (highest first)."""
        return sorted(self.items, key=lambda x: x.priority, reverse=True)


@dataclass
class BatchProgress:
    """Progress tracking for batch processing."""
    
    batch_id: str
    total_items: int
    completed_items: int = 0
    failed_items: int = 0
    processing_items: int = 0
    
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    # Performance metrics
    average_processing_time: Optional[float] = None
    items_per_second: Optional[float] = None
    
    @property
    def pending_items(self) -> int:
        """Number of items not yet started."""
        return self.total_items - self.completed_items - self.failed_items - self.processing_items
    
    @property
    def completion_percentage(self) -> float:
        """Completion percentage (0.0 to 1.0)."""
        if self.total_items == 0:
            return 1.0
        return (self.completed_items + self.failed_items) / self.total_items
    
    @property
    def success_rate(self) -> float:
        """Success rate of completed items (0.0 to 1.0)."""
        processed = self.completed_items + self.failed_items
        if processed == 0:
            return 0.0
        return self.completed_items / processed


@dataclass
class BatchResult:
    """Results of a completed batch evaluation."""
    
    # Request reference
    batch_request: BatchRequest
    
    # Processing metadata
    status: BatchStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    processing_duration: Optional[float] = None
    
    # Results
    successful_items: List[BatchEvaluationItem] = field(default_factory=list)
    failed_items: List[BatchEvaluationItem] = field(default_factory=list)
    
    # Aggregated statistics
    total_cost: Optional[float] = None
    average_processing_time: Optional[float] = None
    
    # Error information
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_items(self) -> int:
        """Total number of items in the batch."""
        return self.batch_request.total_items
    
    @property
    def completed_items_count(self) -> int:
        """Number of successfully completed items."""
        return len(self.successful_items)
    
    @property
    def failed_items_count(self) -> int:
        """Number of failed items."""
        return len(self.failed_items)
    
    @property
    def success_rate(self) -> float:
        """Success rate (0.0 to 1.0)."""
        if self.total_items == 0:
            return 1.0
        return self.completed_items_count / self.total_items
    
    @property
    def is_completed(self) -> bool:
        """Check if batch processing is completed."""
        return self.status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]
    
    def get_results_by_type(self, evaluation_type: EvaluationType) -> List[BatchEvaluationItem]:
        """Get results filtered by evaluation type."""
        return [item for item in self.successful_items 
                if item.evaluation_type == evaluation_type]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the batch results."""
        return {
            "batch_id": self.batch_request.batch_id,
            "status": self.status.value,
            "total_items": self.total_items,
            "successful_items": self.completed_items_count,
            "failed_items": self.failed_items_count,
            "success_rate": self.success_rate,
            "processing_duration": self.processing_duration,
            "average_processing_time": self.average_processing_time,
            "total_cost": self.total_cost
        }