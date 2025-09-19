"""
Batch processing application service.

Orchestrates batch evaluation processing by coordinating between domain services
and infrastructure components.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, AsyncIterator, Union
import csv
from io import StringIO

from ...domain.batch import (
    BatchRequest, 
    BatchResult, 
    BatchEvaluationItem, 
    BatchProgress,
    EvaluationType,
    BatchEvaluationService
)
from .llm_judge_service import LLMJudge, CandidateResponse, EvaluationResult


logger = logging.getLogger(__name__)


class BatchProcessingService:
    """
    Application service for batch evaluation processing.
    
    This service coordinates between the domain batch processing service and
    the infrastructure components (LLM judge, file I/O, etc.).
    """
    
    def __init__(self, llm_judge: LLMJudge, max_workers: int = 10):
        """Initialize the batch processing service."""
        self.llm_judge = llm_judge
        self.batch_service = BatchEvaluationService(max_workers=max_workers)
        self._progress_callbacks: Dict[str, List[Callable[[BatchProgress], None]]] = {}
    
    async def process_batch_request(
        self, 
        batch_request: BatchRequest,
        progress_callback: Optional[Callable[[BatchProgress], None]] = None
    ) -> BatchResult:
        """
        Process a batch request using the configured LLM judge.
        
        Args:
            batch_request: The batch request to process
            progress_callback: Optional callback for progress updates
            
        Returns:
            BatchResult containing the processing results
        """
        logger.info(f"Processing batch {batch_request.batch_id} with {batch_request.total_items} items")
        
        # Register progress callback
        if progress_callback:
            self.add_progress_callback(batch_request.batch_id, progress_callback)
        
        try:
            # Create evaluator function that uses our LLM judge with multi-criteria evaluation
            async def evaluator_func(candidate_or_a, criteria_or_b=None):
                if isinstance(criteria_or_b, str):
                    # Single evaluation - use multi-criteria by default
                    multi_result = await self.llm_judge.evaluate_multi_criteria(candidate_or_a)
                    # Convert to legacy format for batch compatibility
                    return EvaluationResult(
                        score=multi_result.aggregated.overall_score,
                        reasoning=multi_result.overall_reasoning or f"Multi-criteria evaluation: {multi_result.aggregated.overall_score:.1f}/5 across {len(multi_result.criterion_scores)} criteria",
                        confidence=multi_result.aggregated.confidence,
                        metadata={
                            "multi_criteria": True,
                            "criteria_count": len(multi_result.criterion_scores),
                            "individual_scores": {
                                cs.criterion_name: {"score": cs.score, "reasoning": cs.reasoning}
                                for cs in multi_result.criterion_scores
                            }
                        }
                    )
                else:
                    # Pairwise comparison
                    return await self.llm_judge.compare_responses(candidate_or_a, criteria_or_b)
            
            # Process the batch
            result = await self.batch_service.process_batch(
                batch_request=batch_request,
                evaluator_func=evaluator_func,
                progress_callback=self._create_progress_dispatcher(batch_request.batch_id)
            )
            
            logger.info(f"Batch {batch_request.batch_id} completed with {result.success_rate:.1%} success rate")
            return result
            
        finally:
            # Cleanup progress callbacks
            self._progress_callbacks.pop(batch_request.batch_id, None)
    
    async def process_batch_from_file(
        self,
        file_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        batch_config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[BatchProgress], None]] = None
    ) -> BatchResult:
        """
        Process a batch from a file (JSONL or CSV format).
        
        Args:
            file_path: Path to input file
            output_path: Optional path for output file
            batch_config: Optional batch configuration overrides
            progress_callback: Optional progress callback
            
        Returns:
            BatchResult containing the processing results
        """
        file_path = Path(file_path)
        
        # Load batch request from file
        batch_request = await self._load_batch_from_file(file_path, batch_config or {})
        
        # Process the batch
        result = await self.process_batch_request(batch_request, progress_callback)
        
        # Save results if output path specified
        if output_path:
            await self._save_batch_results(result, Path(output_path))
        
        return result
    
    async def _load_batch_from_file(
        self, 
        file_path: Path, 
        batch_config: Dict[str, Any]
    ) -> BatchRequest:
        """Load a batch request from a file."""
        
        if not file_path.exists():
            raise FileNotFoundError(f"Batch file not found: {file_path}")
        
        # Create batch request with configuration
        batch_request = BatchRequest(
            name=batch_config.get("name", file_path.stem),
            description=batch_config.get("description"),
            max_concurrent_items=batch_config.get("max_concurrent_items", 10),
            retry_failed_items=batch_config.get("retry_failed_items", True),
            max_retries_per_item=batch_config.get("max_retries_per_item", 3),
            continue_on_error=batch_config.get("continue_on_error", True),
            judge_provider=batch_config.get("judge_provider"),
            judge_model=batch_config.get("judge_model"),
            metadata=batch_config.get("metadata", {})
        )
        
        # Load items based on file format
        if file_path.suffix.lower() == '.jsonl':
            await self._load_items_from_jsonl(file_path, batch_request)
        elif file_path.suffix.lower() == '.csv':
            await self._load_items_from_csv(file_path, batch_request)
        elif file_path.suffix.lower() == '.json':
            await self._load_items_from_json(file_path, batch_request)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        return batch_request
    
    async def _load_items_from_jsonl(self, file_path: Path, batch_request: BatchRequest):
        """Load evaluation items from JSONL file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    item_data = json.loads(line)
                    await self._add_item_from_dict(batch_request, item_data, line_num)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping invalid JSON on line {line_num}: {e}")
                except Exception as e:
                    logger.warning(f"Skipping item on line {line_num}: {e}")
    
    async def _load_items_from_csv(self, file_path: Path, batch_request: BatchRequest):
        """Load evaluation items from CSV file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            # Detect delimiter
            sample = f.read(1024)
            f.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.DictReader(f, delimiter=delimiter)
            for row_num, row in enumerate(reader, 2):  # Start at 2 (header is row 1)
                try:
                    await self._add_item_from_dict(batch_request, row, row_num)
                except Exception as e:
                    logger.warning(f"Skipping item on row {row_num}: {e}")
    
    async def _load_items_from_json(self, file_path: Path, batch_request: BatchRequest):
        """Load evaluation items from JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            # List of items
            for i, item_data in enumerate(data):
                try:
                    await self._add_item_from_dict(batch_request, item_data, i + 1)
                except Exception as e:
                    logger.warning(f"Skipping item {i + 1}: {e}")
        elif isinstance(data, dict):
            # Single batch configuration
            if "items" in data:
                for i, item_data in enumerate(data["items"]):
                    try:
                        await self._add_item_from_dict(batch_request, item_data, i + 1)
                    except Exception as e:
                        logger.warning(f"Skipping item {i + 1}: {e}")
            else:
                # Single item
                await self._add_item_from_dict(batch_request, data, 1)
    
    async def _add_item_from_dict(
        self, 
        batch_request: BatchRequest, 
        item_data: Dict[str, Any], 
        line_num: int
    ):
        """Add an evaluation item from dictionary data."""
        
        # Determine evaluation type
        eval_type = item_data.get("type", "single").lower()
        
        if eval_type == "single" or eval_type == "evaluate":
            # Single evaluation
            prompt = item_data.get("prompt")
            response = item_data.get("response")
            model = item_data.get("model", "unknown")
            criteria = item_data.get("criteria", "overall quality")
            priority = item_data.get("priority", 0)
            
            if not prompt or not response:
                raise ValueError(f"Single evaluation requires 'prompt' and 'response' fields")
            
            candidate = CandidateResponse(
                prompt=prompt,
                response=response,
                model=model
            )
            
            batch_request.add_single_evaluation(
                candidate=candidate,
                criteria=criteria,
                priority=priority,
                metadata={"source_line": line_num}
            )
            
        elif eval_type == "compare" or eval_type == "comparison":
            # Pairwise comparison
            prompt = item_data.get("prompt")
            response_a = item_data.get("response_a")
            response_b = item_data.get("response_b")
            model_a = item_data.get("model_a", "unknown")
            model_b = item_data.get("model_b", "unknown")
            priority = item_data.get("priority", 0)
            
            if not prompt or not response_a or not response_b:
                raise ValueError(f"Comparison evaluation requires 'prompt', 'response_a', and 'response_b' fields")
            
            candidate_a = CandidateResponse(
                prompt=prompt,
                response=response_a,
                model=model_a
            )
            
            candidate_b = CandidateResponse(
                prompt=prompt,
                response=response_b,
                model=model_b
            )
            
            batch_request.add_comparison_evaluation(
                candidate_a=candidate_a,
                candidate_b=candidate_b,
                priority=priority,
                metadata={"source_line": line_num}
            )
        else:
            raise ValueError(f"Unknown evaluation type: {eval_type}")
    
    async def _save_batch_results(self, result: BatchResult, output_path: Path):
        """Save batch results to a file."""
        
        output_data = {
            "batch_summary": result.get_summary(),
            "results": []
        }
        
        # Add successful results
        for item in result.successful_items:
            item_result = {
                "item_id": item.item_id,
                "status": "success",
                "evaluation_type": item.evaluation_type.value,
                "processed_at": item.processed_at.isoformat() if item.processed_at else None,
                "processing_duration": item.processing_duration,
                "result": self._serialize_evaluation_result(item.result),
                "metadata": item.metadata
            }
            
            # Add input data
            if item.evaluation_type == EvaluationType.SINGLE:
                item_result.update({
                    "prompt": item.candidate_response.prompt,
                    "response": item.candidate_response.response,
                    "model": item.candidate_response.model,
                    "criteria": item.criteria
                })
            else:
                item_result.update({
                    "prompt": item.candidate_a.prompt,
                    "response_a": item.candidate_a.response,
                    "response_b": item.candidate_b.response,
                    "model_a": item.candidate_a.model,
                    "model_b": item.candidate_b.model
                })
            
            output_data["results"].append(item_result)
        
        # Add failed results
        for item in result.failed_items:
            item_result = {
                "item_id": item.item_id,
                "status": "failed",
                "evaluation_type": item.evaluation_type.value,
                "processed_at": item.processed_at.isoformat() if item.processed_at else None,
                "processing_duration": item.processing_duration,
                "error": item.error,
                "metadata": item.metadata
            }
            
            # Add input data
            if item.evaluation_type == EvaluationType.SINGLE and item.candidate_response:
                item_result.update({
                    "prompt": item.candidate_response.prompt,
                    "response": item.candidate_response.response,
                    "model": item.candidate_response.model,
                    "criteria": item.criteria
                })
            elif item.candidate_a and item.candidate_b:
                item_result.update({
                    "prompt": item.candidate_a.prompt,
                    "response_a": item.candidate_a.response,
                    "response_b": item.candidate_b.response,
                    "model_a": item.candidate_a.model,
                    "model_b": item.candidate_b.model
                })
            
            output_data["results"].append(item_result)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Batch results saved to {output_path}")
    
    def _serialize_evaluation_result(self, result: Any) -> Dict[str, Any]:
        """Serialize evaluation result for JSON output."""
        if isinstance(result, EvaluationResult):
            return {
                "score": result.score,
                "reasoning": result.reasoning,
                "confidence": result.confidence,
                "metadata": getattr(result, 'metadata', {})
            }
        elif isinstance(result, dict):
            return result
        else:
            return {"raw_result": str(result)}
    
    def _create_progress_dispatcher(self, batch_id: str) -> Callable[[BatchProgress], None]:
        """Create a progress callback dispatcher for a batch."""
        def dispatch_progress(progress: BatchProgress):
            callbacks = self._progress_callbacks.get(batch_id, [])
            for callback in callbacks:
                try:
                    callback(progress)
                except Exception as e:
                    logger.error(f"Error in progress callback for batch {batch_id}: {e}")
        
        return dispatch_progress
    
    def add_progress_callback(
        self, 
        batch_id: str, 
        callback: Callable[[BatchProgress], None]
    ):
        """Add a progress callback for a batch."""
        if batch_id not in self._progress_callbacks:
            self._progress_callbacks[batch_id] = []
        self._progress_callbacks[batch_id].append(callback)
    
    def remove_progress_callback(
        self, 
        batch_id: str, 
        callback: Callable[[BatchProgress], None]
    ):
        """Remove a progress callback for a batch."""
        if batch_id in self._progress_callbacks:
            try:
                self._progress_callbacks[batch_id].remove(callback)
            except ValueError:
                pass
    
    def get_batch_progress(self, batch_id: str) -> Optional[BatchProgress]:
        """Get current progress for a batch."""
        return self.batch_service.get_batch_progress(batch_id)
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a running batch."""
        return self.batch_service.cancel_batch(batch_id)
    
    def get_active_batches(self) -> List[str]:
        """Get list of currently active batch IDs."""
        return self.batch_service.get_active_batches()
    
    async def create_sample_batch_file(self, file_path: Union[str, Path], format: str = "jsonl"):
        """Create a sample batch file for testing/demonstration."""
        file_path = Path(file_path)
        
        if format.lower() == "jsonl":
            sample_data = [
                {
                    "type": "single",
                    "prompt": "What is artificial intelligence?",
                    "response": "AI is a field of computer science focused on creating intelligent machines.",
                    "model": "gpt-3.5-turbo",
                    "criteria": "accuracy and clarity"
                },
                {
                    "type": "comparison",
                    "prompt": "Explain machine learning",
                    "response_a": "ML is a subset of AI",
                    "response_b": "Machine learning is a subset of AI that enables computers to learn from data",
                    "model_a": "gpt-3.5-turbo",
                    "model_b": "gpt-4"
                }
            ]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                for item in sample_data:
                    f.write(json.dumps(item) + '\n')
        
        elif format.lower() == "csv":
            csv_content = """type,prompt,response,model,criteria,response_a,response_b,model_a,model_b
single,"What is AI?","AI is artificial intelligence","gpt-3.5","accuracy",,,,
comparison,"Explain ML",,"","","ML is subset","Machine learning enables computers to learn","gpt-3.5","gpt-4"
"""
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(csv_content)
        
        logger.info(f"Sample batch file created: {file_path}")