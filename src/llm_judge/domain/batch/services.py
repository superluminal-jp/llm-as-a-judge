"""
Batch processing domain services.

Contains business logic for batch evaluation processing that doesn't belong 
to specific entities or value objects.
"""

import asyncio
import logging
from datetime import datetime
from typing import AsyncIterator, Callable, List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import time

from .models import BatchRequest, BatchResult, BatchStatus, BatchEvaluationItem, BatchProgress, EvaluationType
# Using TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import CandidateResponse, EvaluationResult


logger = logging.getLogger(__name__)


class BatchEvaluationService:
    """
    Domain service for orchestrating batch evaluation processing.
    
    This service contains the core business logic for processing batches of evaluations,
    including concurrency management, error handling, and progress tracking.
    """
    
    def __init__(self, max_workers: int = 10):
        """Initialize the batch evaluation service."""
        self.max_workers = max_workers
        self._active_batches: Dict[str, BatchProgress] = {}
        self._cancellation_tokens: Dict[str, bool] = {}
    
    async def process_batch(
        self,
        batch_request: BatchRequest,
        evaluator_func: Callable,
        progress_callback: Optional[Callable[[BatchProgress], None]] = None
    ) -> BatchResult:
        """
        Process a batch of evaluations.
        
        Args:
            batch_request: The batch request to process
            evaluator_func: Function to evaluate individual items
            progress_callback: Optional callback for progress updates
            
        Returns:
            BatchResult containing the processing results
        """
        batch_id = batch_request.batch_id
        started_at = datetime.now()
        
        # Validate batch has items
        if batch_request.total_items == 0:
            raise ValueError("Batch request must contain at least one evaluation item")
            
        logger.info(f"Starting batch processing for batch {batch_id} with {batch_request.total_items} items")
        
        # Initialize progress tracking
        progress = BatchProgress(
            batch_id=batch_id,
            total_items=batch_request.total_items,
            started_at=started_at
        )
        self._active_batches[batch_id] = progress
        self._cancellation_tokens[batch_id] = False
        
        try:
            # Process items with concurrency control
            successful_items, failed_items = await self._process_items_concurrent(
                batch_request, evaluator_func, progress, progress_callback
            )
            
            # Create final result
            completed_at = datetime.now()
            processing_duration = (completed_at - started_at).total_seconds()
            
            # Calculate statistics
            average_processing_time = self._calculate_average_processing_time(
                successful_items + failed_items
            )
            
            result = BatchResult(
                batch_request=batch_request,
                status=BatchStatus.COMPLETED if not self._cancellation_tokens[batch_id] else BatchStatus.CANCELLED,
                started_at=started_at,
                completed_at=completed_at,
                processing_duration=processing_duration,
                successful_items=successful_items,
                failed_items=failed_items,
                average_processing_time=average_processing_time
            )
            
            logger.info(f"Batch {batch_id} completed: {len(successful_items)} successful, {len(failed_items)} failed")
            return result
            
        except Exception as e:
            logger.error(f"Batch {batch_id} failed with error: {e}")
            return BatchResult(
                batch_request=batch_request,
                status=BatchStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(),
                processing_duration=(datetime.now() - started_at).total_seconds(),
                failed_items=batch_request.items.copy(),
                error_message=str(e),
                error_details={"exception_type": type(e).__name__}
            )
        finally:
            # Cleanup
            self._active_batches.pop(batch_id, None)
            self._cancellation_tokens.pop(batch_id, None)
    
    async def _process_items_concurrent(
        self,
        batch_request: BatchRequest,
        evaluator_func: Callable,
        progress: BatchProgress,
        progress_callback: Optional[Callable[[BatchProgress], None]]
    ) -> tuple[List[BatchEvaluationItem], List[BatchEvaluationItem]]:
        """Process batch items with concurrency control."""
        
        # Sort items by priority
        items = batch_request.get_items_by_priority()
        successful_items = []
        failed_items = []
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(min(batch_request.max_concurrent_items, self.max_workers))
        
        # Process items concurrently
        tasks = []
        for item in items:
            if self._cancellation_tokens.get(batch_request.batch_id, False):
                break
                
            task = asyncio.create_task(
                self._process_single_item(
                    item, evaluator_func, semaphore, batch_request, progress, progress_callback
                )
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Separate successful and failed items
        for i, result in enumerate(results):
            item = items[i] if i < len(items) else None
            if isinstance(result, Exception):
                if item:
                    item.error = str(result)
                    item.processed_at = datetime.now()
                    failed_items.append(item)
            elif result and isinstance(result, BatchEvaluationItem):
                if result.has_error:
                    failed_items.append(result)
                else:
                    successful_items.append(result)
        
        return successful_items, failed_items
    
    async def _process_single_item(
        self,
        item: BatchEvaluationItem,
        evaluator_func: Callable,
        semaphore: asyncio.Semaphore,
        batch_request: BatchRequest,
        progress: BatchProgress,
        progress_callback: Optional[Callable[[BatchProgress], None]]
    ) -> BatchEvaluationItem:
        """Process a single evaluation item."""
        
        async with semaphore:
            # Check for cancellation
            if self._cancellation_tokens.get(batch_request.batch_id, False):
                item.error = "Batch processing was cancelled"
                return item
            
            # Update progress
            progress.processing_items += 1
            if progress_callback:
                progress_callback(progress)
            
            start_time = time.time()
            retry_count = 0
            max_retries = batch_request.max_retries_per_item if batch_request.retry_failed_items else 0
            
            while retry_count <= max_retries:
                try:
                    # Process the evaluation
                    if item.evaluation_type == EvaluationType.SINGLE:
                        result = await evaluator_func(item.candidate_response, item.criteria)
                        item.result = result
                    elif item.evaluation_type == EvaluationType.COMPARISON:
                        result = await evaluator_func(item.candidate_a, item.candidate_b)
                        item.result = result
                    
                    # Success - update item and progress
                    item.processed_at = datetime.now()
                    item.processing_duration = time.time() - start_time
                    
                    progress.processing_items -= 1
                    progress.completed_items += 1
                    break
                    
                except Exception as e:
                    retry_count += 1
                    error_msg = f"Attempt {retry_count}/{max_retries + 1} failed: {str(e)}"
                    
                    if retry_count <= max_retries:
                        logger.warning(f"Retrying item {item.item_id}: {error_msg}")
                        await asyncio.sleep(min(2 ** retry_count, 30))  # Exponential backoff
                    else:
                        # Final failure
                        item.error = error_msg
                        item.processed_at = datetime.now()
                        item.processing_duration = time.time() - start_time
                        
                        progress.processing_items -= 1
                        progress.failed_items += 1
                        
                        if not batch_request.continue_on_error:
                            # Cancel the entire batch
                            self._cancellation_tokens[batch_request.batch_id] = True
                        break
            
            # Update progress metrics
            self._update_progress_metrics(progress)
            if progress_callback:
                progress_callback(progress)
            
            return item
    
    def _update_progress_metrics(self, progress: BatchProgress):
        """Update progress metrics like items per second."""
        if progress.started_at:
            elapsed = (datetime.now() - progress.started_at).total_seconds()
            if elapsed > 0:
                completed_total = progress.completed_items + progress.failed_items
                progress.items_per_second = completed_total / elapsed
                
                # Estimate completion time
                if progress.items_per_second > 0 and progress.pending_items > 0:
                    remaining_seconds = progress.pending_items / progress.items_per_second
                    progress.estimated_completion = datetime.now().timestamp() + remaining_seconds
    
    def _calculate_average_processing_time(self, items: List[BatchEvaluationItem]) -> Optional[float]:
        """Calculate average processing time for completed items."""
        processing_times = [
            item.processing_duration for item in items 
            if item.processing_duration is not None
        ]
        if not processing_times:
            return None
        return sum(processing_times) / len(processing_times)
    
    def get_batch_progress(self, batch_id: str) -> Optional[BatchProgress]:
        """Get current progress for a batch."""
        return self._active_batches.get(batch_id)
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a running batch."""
        if batch_id in self._cancellation_tokens:
            self._cancellation_tokens[batch_id] = True
            logger.info(f"Cancellation requested for batch {batch_id}")
            return True
        return False
    
    def get_active_batches(self) -> List[str]:
        """Get list of currently active batch IDs."""
        return list(self._active_batches.keys())
    
    async def process_batch_items_stream(
        self,
        items: AsyncIterator[BatchEvaluationItem],
        evaluator_func: Callable,
        max_concurrent: int = 10
    ) -> AsyncIterator[BatchEvaluationItem]:
        """
        Process batch items as a stream (useful for very large batches).
        
        This method allows processing items without loading them all into memory.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_item(item: BatchEvaluationItem) -> BatchEvaluationItem:
            async with semaphore:
                try:
                    start_time = time.time()
                    
                    if item.evaluation_type == EvaluationType.SINGLE:
                        result = await evaluator_func(item.candidate_response, item.criteria)
                        item.result = result
                    elif item.evaluation_type == EvaluationType.COMPARISON:
                        result = await evaluator_func(item.candidate_a, item.candidate_b)
                        item.result = result
                    
                    item.processed_at = datetime.now()
                    item.processing_duration = time.time() - start_time
                    
                except Exception as e:
                    item.error = str(e)
                    item.processed_at = datetime.now()
                
                return item
        
        # Process items as they come in
        tasks = []
        async for item in items:
            task = asyncio.create_task(process_item(item))
            tasks.append(task)
            
            # Yield completed results
            for i, task in enumerate(list(tasks)):
                if task.done():
                    result = await task
                    tasks.remove(task)
                    yield result
        
        # Wait for remaining tasks
        if tasks:
            remaining = await asyncio.gather(*tasks)
            for result in remaining:
                yield result