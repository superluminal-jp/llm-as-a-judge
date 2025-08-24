"""Entry point for llm-judge CLI."""

import sys
from .application.services.llm_judge_service import LLMJudge, CandidateResponse

def main():
    """Simple CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: python -m llm_judge <prompt> <response>")
        sys.exit(1)
    
    prompt = sys.argv[1]
    response = sys.argv[2]
    
    judge = LLMJudge()
    candidate = CandidateResponse(prompt=prompt, response=response)
    
    result = judge.evaluate_response(candidate)
    print(f"Score: {result.score}")
    print(f"Reasoning: {result.reasoning}")

if __name__ == "__main__":
    main()