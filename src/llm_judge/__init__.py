"""LLM-as-a-Judge: Evaluation system for language model responses."""

from .application.services.llm_judge_service import LLMJudge, CandidateResponse, EvaluationResult
from .infrastructure.config.config import LLMConfig, load_config

__version__ = "0.1.0"
__all__ = ["LLMJudge", "CandidateResponse", "EvaluationResult", "LLMConfig", "load_config"]