"""
Tests for integer score functionality.

This module tests the changes made to ensure scores are stored as integers
throughout the multi-criteria evaluation system.
"""

import pytest
from src.llm_judge.domain.evaluation.results import CriterionScore, MultiCriteriaResult, AggregatedScore
from src.llm_judge.domain.evaluation.criteria import DefaultCriteria
from src.llm_judge.presentation.cli.multi_criteria_display import MultiCriteriaDisplayFormatter
import json


class TestIntegerScores:
    """Test integer score storage and functionality."""

    def test_criterion_score_stores_integer(self):
        """Test that CriterionScore stores score as integer."""
        score = CriterionScore(
            criterion_name="test",
            score=4,
            reasoning="Good performance",
            confidence=0.8
        )
        
        assert isinstance(score.score, int)
        assert score.score == 4

    def test_criterion_score_float_input_conversion(self):
        """Test that float inputs are converted to integers."""
        # This would happen in the client parsing logic
        float_value = 3.7
        score = CriterionScore(
            criterion_name="test", 
            score=int(round(float_value)),  # Simulating client conversion
            reasoning="Test",
            confidence=0.5
        )
        
        assert isinstance(score.score, int)
        assert score.score == 4  # 3.7 rounds to 4

    def test_criterion_score_properties_with_integer(self):
        """Test that CriterionScore properties work correctly with integer scores."""
        score = CriterionScore(
            criterion_name="test",
            score=3,
            reasoning="Average performance",
            confidence=0.7,
            max_score=5,
            min_score=1
        )
        
        # These should return floats for calculations
        assert isinstance(score.normalized_score, float)
        assert score.normalized_score == 0.5  # (3-1)/(5-1) = 2/4 = 0.5
        
        assert isinstance(score.weighted_score, float)
        assert score.weighted_score == 3.0  # 3 * 1.0 (default weight)
        
        assert isinstance(score.percentage_score, float)
        assert score.percentage_score == 50.0  # 0.5 * 100

    def test_aggregated_score_min_max_integers(self):
        """Test that AggregatedScore min_score and max_score are integers."""
        scores = [
            CriterionScore("accuracy", 5, "Excellent", 0.9),
            CriterionScore("clarity", 3, "Good", 0.8),
            CriterionScore("relevance", 4, "Very good", 0.85)
        ]
        
        result = MultiCriteriaResult(criterion_scores=scores)
        
        assert result.aggregated is not None
        assert isinstance(result.aggregated.min_score, int)
        assert isinstance(result.aggregated.max_score, int)
        assert result.aggregated.min_score == 3
        assert result.aggregated.max_score == 5

    def test_multi_criteria_result_aggregation(self):
        """Test that MultiCriteriaResult correctly aggregates integer scores."""
        scores = [
            CriterionScore("criterion1", 2, "Poor", 0.6),
            CriterionScore("criterion2", 4, "Good", 0.8),
            CriterionScore("criterion3", 5, "Excellent", 0.9)
        ]
        
        result = MultiCriteriaResult(criterion_scores=scores)
        
        # Check all individual scores are integers
        for score in result.criterion_scores:
            assert isinstance(score.score, int)
        
        # Check aggregated statistics
        assert result.aggregated is not None
        assert isinstance(result.aggregated.min_score, int)
        assert isinstance(result.aggregated.max_score, int)
        assert result.aggregated.min_score == 2
        assert result.aggregated.max_score == 5
        
        # Overall score should still be float (weighted average)
        assert isinstance(result.aggregated.overall_score, float)

    def test_display_json_output_integer_scores(self):
        """Test that JSON output displays integer scores."""
        scores = [
            CriterionScore("accuracy", 4, "Good accuracy", 0.8),
            CriterionScore("clarity", 3, "Fair clarity", 0.7)
        ]
        
        result = MultiCriteriaResult(criterion_scores=scores)
        formatter = MultiCriteriaDisplayFormatter(use_rich=False)
        
        json_output = formatter.format_evaluation_result(result, "json")
        data = json.loads(json_output)
        
        # Check score range is integers
        assert isinstance(data["score_range"][0], int)
        assert isinstance(data["score_range"][1], int)
        assert data["score_range"] == [3, 4]
        
        # Check individual criterion scores are integers
        for criterion in data["criterion_scores"]:
            assert isinstance(criterion["score"], int)

    def test_display_text_output_integer_scores(self):
        """Test that text output displays integer scores correctly."""
        scores = [
            CriterionScore("accuracy", 5, "Perfect accuracy", 0.95),
            CriterionScore("clarity", 2, "Needs improvement", 0.6)
        ]
        
        result = MultiCriteriaResult(criterion_scores=scores)
        formatter = MultiCriteriaDisplayFormatter(use_rich=False)
        
        text_output = formatter.format_evaluation_result(result, "text")
        
        # Should contain integer scores without decimal points
        assert "ACCURACY: 5/5" in text_output
        assert "CLARITY: 2/5" in text_output
        assert "Range: 2 - 5" in text_output
        
        # Should not contain decimal representations
        assert "5.0/5" not in text_output
        assert "2.0/5" not in text_output

    def test_score_validation_with_integers(self):
        """Test that score validation works correctly with integers."""
        # Valid integer score
        score = CriterionScore("test", 3, "Valid", 0.5)
        assert score.score == 3
        
        # Test boundary values
        min_score = CriterionScore("min_test", 1, "Minimum", 0.5)
        assert min_score.score == 1
        
        max_score = CriterionScore("max_test", 5, "Maximum", 0.5)
        assert max_score.score == 5
        
        # Invalid scores should raise ValueError
        with pytest.raises(ValueError):
            CriterionScore("invalid", 0, "Too low", 0.5)  # Below min
        
        with pytest.raises(ValueError):
            CriterionScore("invalid", 6, "Too high", 0.5)  # Above max

    def test_summary_method_integer_scores(self):
        """Test that get_summary method returns integer scores."""
        scores = [
            CriterionScore("test1", 3, "Fair", 0.7),
            CriterionScore("test2", 5, "Excellent", 0.9)
        ]
        
        result = MultiCriteriaResult(criterion_scores=scores)
        summary = result.get_summary()
        
        # Score range should be integers
        assert isinstance(summary["score_range"][0], int)
        assert isinstance(summary["score_range"][1], int)
        assert summary["score_range"] == [3, 5]
        
        # Individual criterion scores should be integers
        for criterion_name, criterion_data in summary["criterion_scores"].items():
            assert isinstance(criterion_data["score"], int)

    def test_legacy_format_integer_scores(self):
        """Test that legacy format conversion maintains integer scores."""
        scores = [
            CriterionScore("accuracy", 4, "Good", 0.8)
        ]
        
        result = MultiCriteriaResult(criterion_scores=scores)
        legacy_format = result.to_legacy_format()
        
        # Individual scores in metadata should be integers
        individual_scores = legacy_format["metadata"]["individual_scores"]
        for criterion_name, criterion_data in individual_scores.items():
            assert isinstance(criterion_data["score"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])