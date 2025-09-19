# LLM-as-a-Judge: Detailed Code Implementation Plan

## Current State: Minimal Working Implementation ✅

### File: `llm_judge_simple.py`
- **Status**: Complete and working
- **Features**: Direct scoring, pairwise comparison, mock LLM integration
- **Lines of Code**: ~100
- **Dependencies**: Only Python standard library

## Phase 1 Enhancements: Production-Ready Core

### 1.1 Real LLM Integration (Priority: HIGH)

#### Add LLM Client Implementation
```python
# File: llm_judge_enhanced.py (expand current file)

import os
import httpx
import json
from typing import Optional

class RealLLMClient:
    """Real LLM API integration."""
    
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        self.client = httpx.AsyncClient()
        
        if provider == "openai":
            self.base_url = "https://api.openai.com/v1/chat/completions"
            self.model = "gpt-4"
        elif provider == "anthropic":
            self.base_url = "https://api.anthropic.com/v1/messages"
            self.model = "claude-3-sonnet-20240229"
    
    async def generate(self, prompt: str) -> dict:
        """Generate evaluation using real LLM API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if self.provider == "openai":
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500
            }
        elif self.provider == "anthropic":
            payload = {
                "model": self.model,
                "max_tokens": 500,
                "temperature": 0.1,
                "messages": [{"role": "user", "content": prompt}]
            }
        
        response = await self.client.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        if self.provider == "openai":
            content = result["choices"][0]["message"]["content"]
        elif self.provider == "anthropic":
            content = result["content"][0]["text"]
        
        try:
            # Try to parse JSON response
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback to basic parsing
            return {"score": 3.0, "reasoning": content, "confidence": 0.5}
```

#### Enhanced Main Class
```python
class EnhancedLLMJudge(LLMJudge):
    """Enhanced judge with real LLM integration."""
    
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None):
        self.client = RealLLMClient(provider, api_key)
    
    async def evaluate_response_async(self, candidate: CandidateResponse, criteria: str = "overall quality") -> EvaluationResult:
        """Async version of evaluation."""
        prompt = self._create_evaluation_prompt(candidate, criteria)
        result = await self.client.generate(prompt)
        
        return EvaluationResult(
            score=result.get("score", 3.0),
            reasoning=result.get("reasoning", "No reasoning provided"),
            confidence=result.get("confidence", 0.5)
        )
```

### 1.2 Configuration Management (Priority: MEDIUM)

#### Add Configuration Class
```python
# Add to llm_judge_enhanced.py

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class JudgeConfig:
    """Configuration for LLM judge."""
    
    # LLM Settings
    provider: str = "openai"
    model: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: int = 500
    
    # Evaluation Settings
    default_criteria: str = "overall quality"
    score_range: tuple = (1, 5)
    confidence_threshold: float = 0.7
    
    # API Settings
    timeout_seconds: int = 30
    max_retries: int = 3
    
    @classmethod
    def from_env(cls) -> "JudgeConfig":
        """Load configuration from environment variables."""
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-4"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),
            timeout_seconds=int(os.getenv("API_TIMEOUT", "30"))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "default_criteria": self.default_criteria,
            "timeout_seconds": self.timeout_seconds
        }
```

### 1.3 Error Handling & Retry Logic (Priority: HIGH)

```python
# Add to llm_judge_enhanced.py

import asyncio
from functools import wraps

def with_retry(max_attempts: int = 3, delay: float = 1.0):
    """Decorator for retry logic."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(delay * (attempt + 1))
                        continue
                    break
            
            raise last_exception
        return wrapper
    return decorator

class RobustLLMClient(RealLLMClient):
    """LLM client with error handling and retries."""
    
    @with_retry(max_attempts=3, delay=1.0)
    async def generate(self, prompt: str) -> dict:
        """Generate with retry logic."""
        try:
            return await super().generate(prompt)
        except httpx.TimeoutException:
            raise Exception("LLM API timeout")
        except httpx.HTTPError as e:
            if e.response.status_code == 429:
                raise Exception("Rate limit exceeded")
            elif e.response.status_code >= 500:
                raise Exception("LLM API server error")
            else:
                raise Exception(f"LLM API error: {e}")
```

### 1.4 Enhanced CLI Interface (Priority: MEDIUM)

```python
# Add to llm_judge_enhanced.py

import argparse
import asyncio

async def cli_evaluate():
    """CLI command for single evaluation."""
    parser = argparse.ArgumentParser(description="Evaluate LLM response")
    parser.add_argument("--prompt", required=True, help="Original prompt")
    parser.add_argument("--response", required=True, help="Response to evaluate")
    parser.add_argument("--model", default="unknown", help="Model that generated response")
    parser.add_argument("--criteria", default="overall quality", help="Evaluation criteria")
    parser.add_argument("--provider", default="openai", help="Judge LLM provider")
    parser.add_argument("--api-key", help="API key (or use env var)")
    
    args = parser.parse_args()
    
    candidate = CandidateResponse(
        prompt=args.prompt,
        response=args.response,
        model=args.model
    )
    
    judge = EnhancedLLMJudge(provider=args.provider, api_key=args.api_key)
    result = await judge.evaluate_response_async(candidate, args.criteria)
    
    print(f"Score: {result.score}/5")
    print(f"Reasoning: {result.reasoning}")
    print(f"Confidence: {result.confidence}")

async def cli_compare():
    """CLI command for pairwise comparison."""
    parser = argparse.ArgumentParser(description="Compare two LLM responses")
    parser.add_argument("--prompt", required=True, help="Original prompt")
    parser.add_argument("--response-a", required=True, help="First response")
    parser.add_argument("--response-b", required=True, help="Second response")
    parser.add_argument("--model-a", default="unknown", help="Model A")
    parser.add_argument("--model-b", default="unknown", help="Model B")
    parser.add_argument("--provider", default="openai", help="Judge LLM provider")
    
    args = parser.parse_args()
    
    candidate_a = CandidateResponse(prompt=args.prompt, response=args.response_a, model=args.model_a)
    candidate_b = CandidateResponse(prompt=args.prompt, response=args.response_b, model=args.model_b)
    
    judge = EnhancedLLMJudge(provider=args.provider)
    result = await judge.compare_responses_async(candidate_a, candidate_b)
    
    print(f"Winner: {result['winner']}")
    print(f"Reasoning: {result['reasoning']}")
    print(f"Confidence: {result['confidence']}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "evaluate":
        asyncio.run(cli_evaluate())
    elif len(sys.argv) > 1 and sys.argv[1] == "compare":
        asyncio.run(cli_compare())
    else:
        # Run demo
        asyncio.run(main())
```

## Phase 2: Modular Architecture

### 2.1 File Structure
```
llm_judge/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── models.py       # Data models
│   ├── judge.py        # Core evaluation logic
│   └── templates.py    # Prompt templates
├── clients/
│   ├── __init__.py
│   ├── base.py         # Abstract base client
│   ├── openai_client.py
│   ├── anthropic_client.py
│   └── mock_client.py  # For testing
├── storage/
│   ├── __init__.py
│   ├── base.py         # Abstract storage
│   ├── sqlite.py       # SQLite implementation
│   └── memory.py       # In-memory storage
├── api/
│   ├── __init__.py
│   ├── server.py       # FastAPI server
│   └── schemas.py      # API schemas
├── cli/
│   ├── __init__.py
│   └── commands.py     # CLI commands
└── utils/
    ├── __init__.py
    ├── config.py       # Configuration
    └── logging.py      # Logging setup
```

### 2.2 Core Models (`llm_judge/core/models.py`)
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid

class EvaluationType(Enum):
    DIRECT_SCORING = "direct_scoring"
    PAIRWISE_COMPARISON = "pairwise_comparison"
    REFERENCE_BASED = "reference_based"

class EvaluationStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class CandidateResponse:
    prompt: str
    response: str
    model: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EvaluationCriteria:
    name: str
    description: str
    scale_min: int = 1
    scale_max: int = 5
    weight: float = 1.0

@dataclass
class EvaluationResult:
    score: float
    reasoning: str
    confidence: float = 0.0
    detailed_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Evaluation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    candidate_response: CandidateResponse = None
    evaluation_type: EvaluationType = EvaluationType.DIRECT_SCORING
    criteria: List[EvaluationCriteria] = field(default_factory=list)
    judge_model: str = "gpt-4"
    status: EvaluationStatus = EvaluationStatus.PENDING
    result: Optional[EvaluationResult] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def mark_completed(self, result: EvaluationResult):
        self.result = result
        self.status = EvaluationStatus.COMPLETED
        self.completed_at = datetime.utcnow()
    
    def mark_failed(self, error: str):
        self.error_message = error
        self.status = EvaluationStatus.FAILED
        self.completed_at = datetime.utcnow()
```

### 2.3 Abstract Base Client (`llm_judge/clients/base.py`)
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the client is available."""
        pass
    
    @abstractmethod
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        pass
    
    async def generate_json(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate and parse JSON response."""
        response = await self.generate(prompt, **kwargs)
        try:
            import json
            return json.loads(response)
        except json.JSONDecodeError:
            # Return structured fallback
            return {
                "score": 3.0,
                "reasoning": response,
                "confidence": 0.5
            }
```

### 2.4 Storage Abstraction (`llm_judge/storage/base.py`)
```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..core.models import Evaluation

class EvaluationStorage(ABC):
    """Abstract base class for evaluation storage."""
    
    @abstractmethod
    async def save(self, evaluation: Evaluation) -> str:
        """Save evaluation and return ID."""
        pass
    
    @abstractmethod
    async def get(self, evaluation_id: str) -> Optional[Evaluation]:
        """Get evaluation by ID."""
        pass
    
    @abstractmethod
    async def list(self, filters: Optional[Dict[str, Any]] = None, 
                  limit: int = 100) -> List[Evaluation]:
        """List evaluations with optional filters."""
        pass
    
    @abstractmethod
    async def update(self, evaluation: Evaluation) -> bool:
        """Update existing evaluation."""
        pass
    
    @abstractmethod
    async def delete(self, evaluation_id: str) -> bool:
        """Delete evaluation."""
        pass
```

## Phase 3: Advanced Features Implementation

### 3.1 Batch Processing (`llm_judge/core/batch.py`)
```python
import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
from .models import Evaluation, EvaluationResult
from .judge import LLMJudge

@dataclass
class BatchRequest:
    evaluations: List[Evaluation]
    batch_id: str
    concurrency_limit: int = 5

@dataclass
class BatchResult:
    batch_id: str
    total_count: int
    completed_count: int
    failed_count: int
    results: List[EvaluationResult]
    errors: List[str]

class BatchProcessor:
    """Process evaluations in batches."""
    
    def __init__(self, judge: LLMJudge, max_concurrent: int = 5):
        self.judge = judge
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(self, batch: BatchRequest) -> BatchResult:
        """Process a batch of evaluations."""
        tasks = [self._process_single(eval) for eval in batch.evaluations]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        completed = []
        errors = []
        
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                completed.append(result)
        
        return BatchResult(
            batch_id=batch.batch_id,
            total_count=len(batch.evaluations),
            completed_count=len(completed),
            failed_count=len(errors),
            results=completed,
            errors=errors
        )
    
    async def _process_single(self, evaluation: Evaluation) -> EvaluationResult:
        """Process single evaluation with concurrency control."""
        async with self.semaphore:
            return await self.judge.evaluate_async(evaluation)
```

### 3.2 REST API (`llm_judge/api/server.py`)
```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import uuid

app = FastAPI(title="LLM Judge API", version="1.0.0")

class EvaluationRequest(BaseModel):
    prompt: str
    response: str
    model: str = "unknown"
    criteria: str = "overall quality"
    judge_model: str = "gpt-4"

class EvaluationResponse(BaseModel):
    evaluation_id: str
    score: float
    reasoning: str
    confidence: float
    status: str

class BatchEvaluationRequest(BaseModel):
    evaluations: List[EvaluationRequest]
    batch_id: Optional[str] = None

@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_single(request: EvaluationRequest):
    """Evaluate a single response."""
    evaluation_id = str(uuid.uuid4())
    
    # Implementation would use actual judge
    result = {
        "evaluation_id": evaluation_id,
        "score": 4.0,
        "reasoning": "Good response with clear explanation",
        "confidence": 0.8,
        "status": "completed"
    }
    
    return EvaluationResponse(**result)

@app.post("/evaluate/batch")
async def evaluate_batch(request: BatchEvaluationRequest, background_tasks: BackgroundTasks):
    """Submit batch evaluation request."""
    batch_id = request.batch_id or str(uuid.uuid4())
    
    # Add background task for processing
    background_tasks.add_task(process_batch_background, batch_id, request.evaluations)
    
    return {"batch_id": batch_id, "status": "submitted", "count": len(request.evaluations)}

@app.get("/evaluate/{evaluation_id}")
async def get_evaluation(evaluation_id: str):
    """Get evaluation result by ID."""
    # Implementation would query storage
    pass

async def process_batch_background(batch_id: str, evaluations: List[EvaluationRequest]):
    """Background task for batch processing."""
    # Implementation would use BatchProcessor
    pass
```

## Testing Strategy

### Unit Tests (`tests/test_core.py`)
```python
import pytest
from llm_judge.core.models import CandidateResponse, EvaluationResult
from llm_judge.core.judge import LLMJudge
from llm_judge.clients.mock_client import MockLLMClient

@pytest.fixture
def mock_client():
    return MockLLMClient(model="mock-gpt", api_key="test")

@pytest.fixture
def judge(mock_client):
    return LLMJudge(client=mock_client)

@pytest.fixture
def sample_candidate():
    return CandidateResponse(
        prompt="What is AI?",
        response="AI is artificial intelligence",
        model="gpt-3.5"
    )

@pytest.mark.asyncio
async def test_evaluate_response(judge, sample_candidate):
    """Test basic response evaluation."""
    result = await judge.evaluate_response_async(sample_candidate)
    
    assert isinstance(result, EvaluationResult)
    assert 1 <= result.score <= 5
    assert len(result.reasoning) > 0
    assert 0 <= result.confidence <= 1

@pytest.mark.asyncio
async def test_pairwise_comparison(judge, sample_candidate):
    """Test pairwise comparison."""
    candidate_b = CandidateResponse(
        prompt="What is AI?",
        response="Artificial Intelligence is machine intelligence",
        model="gpt-4"
    )
    
    result = await judge.compare_responses_async(sample_candidate, candidate_b)
    
    assert result["winner"] in ["A", "B", "tie"]
    assert len(result["reasoning"]) > 0
    assert 0 <= result["confidence"] <= 1
```

### Integration Tests (`tests/test_integration.py`)
```python
import pytest
import os
from llm_judge.core.judge import LLMJudge
from llm_judge.clients.openai_client import OpenAIClient

@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No OpenAI API key")
@pytest.mark.asyncio
async def test_real_openai_evaluation():
    """Test with real OpenAI API."""
    client = OpenAIClient(model="gpt-3.5-turbo", api_key=os.getenv("OPENAI_API_KEY"))
    judge = LLMJudge(client=client)
    
    candidate = CandidateResponse(
        prompt="Explain the water cycle",
        response="Water evaporates, forms clouds, and falls as rain",
        model="test"
    )
    
    result = await judge.evaluate_response_async(candidate, "scientific accuracy")
    
    assert 1 <= result.score <= 5
    assert len(result.reasoning) > 10
    assert result.confidence > 0
```

This detailed code plan provides specific implementation steps, file structures, and code examples for evolving from the current minimal implementation to a full-featured system.