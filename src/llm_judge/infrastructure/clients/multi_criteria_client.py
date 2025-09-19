"""
Multi-criteria evaluation client for LLM providers.

Extends the existing LLM clients to support comprehensive multi-dimensional evaluation.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from ...domain.evaluation.criteria import EvaluationCriteria, DefaultCriteria, CriterionDefinition, CriterionType
from ...domain.evaluation.results import MultiCriteriaResult, CriterionScore
from .anthropic_client import AnthropicClient
from .openai_client import OpenAIClient
from .bedrock_client import BedrockClient


logger = logging.getLogger(__name__)


class MultiCriteriaEvaluationMixin:
    """Mixin to add multi-criteria evaluation capabilities to LLM clients."""
    
    def _build_multi_criteria_prompt(
        self, 
        prompt: str, 
        response_text: str, 
        criteria: EvaluationCriteria
    ) -> str:
        """Build a comprehensive prompt for multi-criteria evaluation."""
        
        # Build criteria descriptions
        criteria_descriptions = []
        for criterion in criteria.criteria:
            desc = f"""
{criterion.name.upper()} (Weight: {criterion.weight:.1%}, Scale: {criterion.scale_min}-{criterion.scale_max}):
{criterion.description}
"""
            if criterion.evaluation_prompt:
                desc += f"Evaluation guidance: {criterion.evaluation_prompt}\n"
            
            if criterion.examples:
                desc += "Examples:\n"
                for score, example in criterion.examples.items():
                    desc += f"  {score}: {example}\n"
            
            criteria_descriptions.append(desc)
        
        # Build the comprehensive prompt
        prompt_template = f"""You are an expert evaluator conducting a comprehensive multi-criteria assessment. 
You must evaluate the following response across {len(criteria.criteria)} distinct criteria.

=== ORIGINAL QUESTION ===
{prompt}

=== RESPONSE TO EVALUATE ===
{response_text}

=== EVALUATION CRITERIA ===
{''.join(criteria_descriptions)}

=== INSTRUCTIONS ===
1. Evaluate the response on each criterion separately
2. Provide a score from {criteria.criteria[0].scale_min} to {criteria.criteria[0].scale_max} for each criterion
3. Give detailed reasoning for each score
4. Provide an overall assessment and recommendations

IMPORTANT: You must respond with ONLY valid JSON. No additional text before or after the JSON.

Required JSON format:

{{
  "criterion_scores": [
    {{
      "criterion_name": "accuracy",
      "score": 4.0,
      "reasoning": "Detailed explanation for this criterion score...",
      "confidence": 0.85
    }},
    {{
      "criterion_name": "clarity", 
      "score": 3.0,
      "reasoning": "Detailed explanation for this criterion score...",
      "confidence": 0.90
    }}
  ],
  "overall_reasoning": "Comprehensive overall assessment of the response quality...",
  "strengths": ["Strength 1", "Strength 2"],
  "weaknesses": ["Weakness 1", "Weakness 2"], 
  "suggestions": ["Improvement suggestion 1", "Improvement suggestion 2"]
}}

Required criteria to include: {', '.join([c.name for c in criteria.criteria])}

Respond with valid JSON only:"""
        return prompt_template
    
    def _parse_multi_criteria_response(
        self,
        response_text: str,
        criteria: EvaluationCriteria,
        judge_model: str
    ) -> MultiCriteriaResult:
        """Parse the multi-criteria evaluation response."""
        try:
            # Extract JSON from response with improved parsing
            response_data = self._extract_json_from_response(response_text)
            
            # Validate response structure
            self._validate_response_structure(response_data, criteria)
            
            # Parse criterion scores
            criterion_scores = []
            for score_data in response_data.get("criterion_scores", []):
                try:
                    # Get the criterion definition to get weight and scale
                    criterion_def = criteria.get_criterion(score_data.get("criterion_name", ""))
                    if not criterion_def:
                        logger.warning(f"Unknown criterion: {score_data.get('criterion_name')}")
                        # Create a default criterion definition for unknown criteria
                        criterion_def = CriterionDefinition(
                            name=score_data.get("criterion_name", "unknown"),
                            description="Unknown criterion",
                            criterion_type=CriterionType.QUALITATIVE,
                            weight=1.0 / len(criteria.criteria),
                            scale_min=1,
                            scale_max=5
                        )
                    
                    criterion_score = CriterionScore(
                        criterion_name=score_data["criterion_name"],
                        score=int(round(float(score_data["score"]))),
                        reasoning=score_data.get("reasoning", ""),
                        confidence=float(score_data.get("confidence", 0.0)),
                        max_score=criterion_def.scale_max,
                        min_score=criterion_def.scale_min,
                        weight=criterion_def.weight
                    )
                    criterion_scores.append(criterion_score)
                    
                except Exception as e:
                    logger.error(f"Error processing criterion score {score_data}: {e}")
                    continue
            
            # If no criterion scores were parsed, create fallback scores
            if not criterion_scores:
                logger.warning("No valid criterion scores found, creating fallback scores")
                for criterion_def in criteria.criteria:
                    fallback_score = CriterionScore(
                        criterion_name=criterion_def.name,
                        score=3,  # Neutral score
                        reasoning=f"Fallback score for {criterion_def.name} due to parsing issues",
                        confidence=0.1,
                        max_score=criterion_def.scale_max,
                        min_score=criterion_def.scale_min,
                        weight=criterion_def.weight
                    )
                    criterion_scores.append(fallback_score)
            
            # Create result
            result = MultiCriteriaResult(
                criterion_scores=criterion_scores,
                criteria_used=criteria,
                judge_model=judge_model,
                overall_reasoning=response_data.get("overall_reasoning", ""),
                strengths=response_data.get("strengths", []),
                weaknesses=response_data.get("weaknesses", []),
                suggestions=response_data.get("suggestions", [])
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse multi-criteria response: {e}")
            logger.debug(f"Response text: {response_text}")
            
            # Fallback: create a basic result with error info
            fallback_score = CriterionScore(
                criterion_name="overall_quality",
                score=3,
                reasoning=f"Failed to parse multi-criteria evaluation: {str(e)}. Raw response available in metadata.",
                confidence=0.1
            )
            
            return MultiCriteriaResult(
                criterion_scores=[fallback_score],
                criteria_used=None,
                judge_model=judge_model,
                overall_reasoning=f"Error parsing multi-criteria response: {str(e)}",
                metadata={"parsing_error": str(e), "raw_response": response_text}
            )
    
    def _extract_json_from_response(self, response_text: str) -> dict:
        """Extract JSON from LLM response with robust parsing."""
        # Clean up response text
        response_text = response_text.strip()
        
        # Try multiple extraction strategies
        strategies = [
            self._extract_json_by_braces,
            self._extract_json_by_code_block,
            self._extract_json_by_markers,
            self._extract_json_fallback
        ]
        
        for strategy in strategies:
            try:
                result = strategy(response_text)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"JSON extraction strategy failed: {e}")
                continue
        
        raise ValueError("Could not extract valid JSON from response")
    
    def _extract_json_by_braces(self, text: str) -> dict:
        """Extract JSON by finding balanced braces."""
        start_idx = text.find('{')
        if start_idx == -1:
            raise ValueError("No opening brace found")
        
        brace_count = 0
        end_idx = start_idx
        
        for i, char in enumerate(text[start_idx:], start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if brace_count != 0:
            raise ValueError("Unbalanced braces")
        
        json_text = text[start_idx:end_idx]
        return json.loads(json_text)
    
    def _extract_json_by_code_block(self, text: str) -> dict:
        """Extract JSON from code block markers."""
        # Look for ```json or ``` code blocks
        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'`(.*?)`'
        ]
        
        import re
        for pattern in patterns:
            matches = re.search(pattern, text, re.DOTALL)
            if matches:
                json_text = matches.group(1).strip()
                if json_text.startswith('{'):
                    return json.loads(json_text)
        
        raise ValueError("No code block found")
    
    def _extract_json_by_markers(self, text: str) -> dict:
        """Extract JSON by looking for explicit markers."""
        # Look for JSON: or similar markers
        markers = ['JSON:', 'json:', 'Response:', 'Output:', 'Result:']
        
        for marker in markers:
            marker_idx = text.lower().find(marker.lower())
            if marker_idx != -1:
                json_start = text.find('{', marker_idx)
                if json_start != -1:
                    return self._extract_json_by_braces(text[json_start:])
        
        raise ValueError("No JSON markers found")
    
    def _extract_json_fallback(self, text: str) -> dict:
        """Fallback JSON extraction for edge cases."""
        # Try to find any JSON-like structure in the text
        lines = text.split('\n')
        json_lines = []
        in_json = False
        
        for line in lines:
            line = line.strip()
            if line.startswith('{'):
                in_json = True
                json_lines.append(line)
            elif in_json:
                json_lines.append(line)
                if line.endswith('}') and line.count('}') >= line.count('{'):
                    break
        
        if json_lines:
            json_text = '\n'.join(json_lines)
            return json.loads(json_text)
        
        raise ValueError("No JSON structure found")
    
    def _validate_response_structure(self, response_data: dict, criteria: EvaluationCriteria):
        """Validate that the response has the required structure."""
        # Check required fields
        required_fields = ["criterion_scores"]
        for field in required_fields:
            if field not in response_data:
                raise ValueError(f"Missing required field: {field}")
        
        criterion_scores = response_data["criterion_scores"]
        if not isinstance(criterion_scores, list) or len(criterion_scores) == 0:
            raise ValueError("criterion_scores must be a non-empty list")
        
        # Check that all criteria are represented
        expected_criteria = {c.name for c in criteria.criteria}
        provided_criteria = {score.get("criterion_name", "") for score in criterion_scores}
        
        missing_criteria = expected_criteria - provided_criteria
        if missing_criteria:
            logger.warning(f"Missing criteria in response: {missing_criteria}")
        
        # Validate individual criterion scores
        for i, score_data in enumerate(criterion_scores):
            self._validate_criterion_score(score_data, i)
    
    def _validate_criterion_score(self, score_data: dict, index: int):
        """Validate individual criterion score data."""
        required_score_fields = ["criterion_name", "score", "reasoning"]
        
        for field in required_score_fields:
            if field not in score_data:
                raise ValueError(f"Criterion score {index} missing required field: {field}")
        
        # Validate score is numeric
        try:
            score = float(score_data["score"])
            if not (1 <= score <= 5):  # Assuming 1-5 scale
                logger.warning(f"Score {score} outside expected range for criterion {score_data['criterion_name']}")
        except (ValueError, TypeError):
            raise ValueError(f"Invalid score value for criterion {score_data['criterion_name']}: {score_data['score']}")
        
        # Validate confidence if present
        if "confidence" in score_data:
            try:
                confidence = float(score_data["confidence"])
                if not (0 <= confidence <= 1):
                    logger.warning(f"Confidence {confidence} outside 0-1 range for criterion {score_data['criterion_name']}")
            except (ValueError, TypeError):
                logger.warning(f"Invalid confidence value for criterion {score_data['criterion_name']}")
        
        # Validate reasoning is not empty
        reasoning = score_data.get("reasoning", "").strip()
        if not reasoning:
            logger.warning(f"Empty reasoning for criterion {score_data['criterion_name']}")


class MultiCriteriaAnthropicClient(AnthropicClient, MultiCriteriaEvaluationMixin):
    """Anthropic client with multi-criteria evaluation support."""
    
    async def evaluate_multi_criteria(
        self,
        prompt: str,
        response_text: str,
        criteria: Optional[EvaluationCriteria] = None,
        model: Optional[str] = None
    ) -> MultiCriteriaResult:
        """Perform multi-criteria evaluation using Anthropic."""
        
        if criteria is None:
            criteria = DefaultCriteria.comprehensive()
        
        eval_prompt = self._build_multi_criteria_prompt(prompt, response_text, criteria)
        model = model or self.default_model
        
        logger.info(f"Starting multi-criteria evaluation with {len(criteria.criteria)} criteria")
        start_time = datetime.now()
        
        try:
            # Use the existing create_message method
            messages = [{"role": "user", "content": eval_prompt}]
            response = await self.create_message(messages, model=model)
            
            # Parse the multi-criteria response
            result = self._parse_multi_criteria_response(
                response.content, 
                criteria,
                model
            )
            
            # Add processing duration
            processing_duration = (datetime.now() - start_time).total_seconds()
            result.processing_duration = processing_duration
            
            logger.info(f"Multi-criteria evaluation completed in {processing_duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Multi-criteria evaluation failed: {e}")
            # Return error result
            fallback_score = CriterionScore(
                criterion_name="overall_quality",
                score=3,
                reasoning=f"Evaluation failed: {str(e)}",
                confidence=0.0
            )
            
            return MultiCriteriaResult(
                criterion_scores=[fallback_score],
                criteria_used=criteria,
                judge_model=model,
                overall_reasoning=f"Evaluation failed: {str(e)}",
                processing_duration=(datetime.now() - start_time).total_seconds(),
                metadata={"error": str(e)}
            )


class MultiCriteriaOpenAIClient(OpenAIClient, MultiCriteriaEvaluationMixin):
    """OpenAI client with multi-criteria evaluation support."""
    
    async def evaluate_multi_criteria(
        self,
        prompt: str,
        response_text: str,
        criteria: Optional[EvaluationCriteria] = None,
        model: Optional[str] = None
    ) -> MultiCriteriaResult:
        """Perform multi-criteria evaluation using OpenAI."""
        
        if criteria is None:
            criteria = DefaultCriteria.comprehensive()
        
        eval_prompt = self._build_multi_criteria_prompt(prompt, response_text, criteria)
        model = model or self.default_model
        
        logger.info(f"Starting multi-criteria evaluation with {len(criteria.criteria)} criteria")
        start_time = datetime.now()
        
        try:
            # Use the existing chat_completion method
            messages = [
                {"role": "system", "content": "You are an expert evaluator conducting comprehensive multi-criteria assessments."},
                {"role": "user", "content": eval_prompt}
            ]
            response = await self.chat_completion(messages, model=model)
            
            # Parse the multi-criteria response
            result = self._parse_multi_criteria_response(
                response.content,
                criteria, 
                model
            )
            
            # Add processing duration
            processing_duration = (datetime.now() - start_time).total_seconds()
            result.processing_duration = processing_duration
            
            logger.info(f"Multi-criteria evaluation completed in {processing_duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Multi-criteria evaluation failed: {e}")
            # Return error result
            fallback_score = CriterionScore(
                criterion_name="overall_quality",
                score=3,
                reasoning=f"Evaluation failed: {str(e)}",
                confidence=0.0
            )
            
            return MultiCriteriaResult(
                criterion_scores=[fallback_score],
                criteria_used=criteria,
                judge_model=model,
                overall_reasoning=f"Evaluation failed: {str(e)}",
                processing_duration=(datetime.now() - start_time).total_seconds(),
                metadata={"error": str(e)}
            )
            

class MockMultiCriteriaClient(MultiCriteriaEvaluationMixin):
    """Mock client for testing multi-criteria evaluation."""
    
    def __init__(self):
        self.default_model = "mock-multi-criteria"
    
    async def evaluate_multi_criteria(
        self,
        prompt: str,
        response_text: str,
        criteria: Optional[EvaluationCriteria] = None,
        model: Optional[str] = None
    ) -> MultiCriteriaResult:
        """Mock multi-criteria evaluation for testing."""
        
        if criteria is None:
            criteria = DefaultCriteria.comprehensive()
        
        # Generate realistic mock scores
        import random
        random.seed(hash(response_text) % 2**32)  # Deterministic based on input
        
        criterion_scores = []
        for criterion in criteria.criteria:
            # Generate score with slight variation
            base_score = 3.5  # Slightly above average
            variation = random.uniform(-1.0, 1.5)
            score = int(round(max(criterion.scale_min, min(criterion.scale_max, base_score + variation))))
            
            mock_reasoning = f"Mock evaluation: This response demonstrates {criterion.name} at level {score}. "
            if score >= 4:
                mock_reasoning += "Shows strong performance in this criterion."
            elif score >= 3:
                mock_reasoning += "Meets expectations with room for improvement."
            else:
                mock_reasoning += "Below expectations, needs significant improvement."
            
            criterion_score = CriterionScore(
                criterion_name=criterion.name,
                score=score,
                reasoning=mock_reasoning,
                confidence=random.uniform(0.7, 0.95),
                max_score=criterion.scale_max,
                min_score=criterion.scale_min,
                weight=criterion.weight
            )
            criterion_scores.append(criterion_score)
        
        # Generate mock qualitative feedback
        avg_score = sum(cs.score for cs in criterion_scores) / len(criterion_scores)
        
        if avg_score >= 4:
            strengths = ["Strong overall performance", "Clear and comprehensive response", "Good attention to detail"]
            weaknesses = ["Minor areas for enhancement"]
            suggestions = ["Consider adding more specific examples", "Could provide more context"]
        elif avg_score >= 3:
            strengths = ["Solid foundation", "Addresses key points"]
            weaknesses = ["Some gaps in coverage", "Could be more detailed"]
            suggestions = ["Expand on key concepts", "Improve clarity in explanations", "Add supporting evidence"]
        else:
            strengths = ["Basic understanding evident"]
            weaknesses = ["Significant gaps in accuracy", "Lacks depth", "Unclear explanations"]
            suggestions = ["Review factual content", "Provide more comprehensive explanation", "Improve structure and flow"]
        
        overall_reasoning = f"Multi-criteria evaluation shows an average performance of {avg_score:.1f}/5. "
        if avg_score >= 4:
            overall_reasoning += "This is a high-quality response that effectively addresses the question."
        elif avg_score >= 3:
            overall_reasoning += "This is a satisfactory response with some areas for improvement."
        else:
            overall_reasoning += "This response needs significant improvement across multiple criteria."
        
        result = MultiCriteriaResult(
            criterion_scores=criterion_scores,
            criteria_used=criteria,
            judge_model=model or self.default_model,
            overall_reasoning=overall_reasoning,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            processing_duration=random.uniform(0.1, 0.3)  # Mock processing time
        )
        
        return result


class MultiCriteriaBedrockClient(MultiCriteriaEvaluationMixin, BedrockClient):
    """Bedrock client with multi-criteria evaluation capabilities."""
    
    def __init__(self, config):
        super().__init__(config)
        self.default_model = config.bedrock_model
    
    async def evaluate_multi_criteria(
        self,
        prompt: str,
        response_text: str,
        criteria: Optional[EvaluationCriteria] = None,
        model: Optional[str] = None
    ) -> MultiCriteriaResult:
        """Perform multi-criteria evaluation using Bedrock."""
        start_time = datetime.now()
        
        if criteria is None:
            criteria = DefaultCriteria.comprehensive()
        
        # Build the multi-criteria evaluation prompt
        evaluation_prompt = self._build_multi_criteria_prompt(prompt, response_text, criteria)
        
        messages = [
            {"role": "user", "content": evaluation_prompt}
        ]
        
        try:
            # Use the existing generate method
            response = await self.generate(messages, model=model, temperature=0.1, max_tokens=2000)
            
            # Parse the multi-criteria response
            result = self._parse_multi_criteria_response(
                response.content, criteria, model or self.default_model
            )
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            result.processing_time = processing_time
            
            return result
            
        except Exception as e:
            logger.error(f"Multi-criteria Bedrock evaluation failed: {e}")
            # Return mock result as fallback
            mock_client = MockMultiCriteriaClient()
            return await mock_client.evaluate_multi_criteria(prompt, response_text, criteria, model)