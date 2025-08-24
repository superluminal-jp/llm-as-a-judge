"""Entry point for llm-judge CLI."""

import sys
import asyncio
from .application.services.llm_judge_service import LLMJudge, CandidateResponse

async def async_main():
    """Async CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: llm-judge <prompt> <response>")
        print("       python -m llm_judge <prompt> <response>")
        sys.exit(1)
    
    prompt = sys.argv[1]
    response = sys.argv[2]
    
    try:
        judge = LLMJudge()
        candidate = CandidateResponse(prompt=prompt, response=response)
        
        print(f"Evaluating response...")
        print(f"Prompt: {prompt}")
        print(f"Response: {response}")
        print("---")
        
        result = await judge.evaluate_response(candidate)
        print(f"Score: {result.score}")
        print(f"Reasoning: {result.reasoning}")
        if hasattr(result, 'confidence') and result.confidence:
            print(f"Confidence: {result.confidence}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    """Simple CLI entry point wrapper."""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()