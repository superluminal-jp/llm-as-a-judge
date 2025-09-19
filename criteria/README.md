# Criteria Directory

This directory contains evaluation criteria configuration files for the LLM-as-a-Judge system.

## Structure

```
criteria/
├── README.md                    # This file
├── academic.json               # Academic evaluation criteria
├── template.json               # Template for custom criteria
└── [custom criteria files]     # User-defined criteria files
```

## Files

### academic.json

Comprehensive academic evaluation criteria including:

- **accuracy** (25%): Factual correctness and truthfulness
- **completeness** (20%): Thoroughness and comprehensiveness
- **relevance** (15%): Relevance to the original prompt
- **clarity** (15%): Clarity of expression and understanding
- **helpfulness** (10%): Practical value and usefulness
- **coherence** (10%): Logical flow and consistency
- **appropriateness** (5%): Suitability for academic context

### template.json

Template for creating custom evaluation criteria. Copy this file and modify it to create your own criteria sets.

## Usage

### Using Criteria Files

```bash
# Use academic criteria
python -m src.llm_judge evaluate "Question" "Answer" --criteria-file criteria/academic.json

# Use custom criteria
python -m src.llm_judge evaluate "Question" "Answer" --criteria-file criteria/my-custom.json
```

### Creating Custom Criteria

1. Copy `criteria/template.json` to create your custom criteria file
2. Modify the criteria definitions as needed
3. Use the file with `--criteria-file` option

### CLI String Format

You can also define criteria directly via CLI:

```bash
python -m src.llm_judge evaluate "Question" "Answer" --custom-criteria "accuracy:Factual correctness:0.4,clarity:How clear the response is:0.3,helpfulness:How useful the response is:0.3"
```

## Criteria Structure

Each criteria file contains:

```json
{
  "name": "Criteria Set Name",
  "description": "Description of the criteria set",
  "criteria": [
    {
      "name": "criterion_name",
      "description": "What this criterion measures",
      "weight": 0.5,
      "evaluation_prompt": "Specific prompt for the LLM judge",
      "examples": {
        "1": "Poor example",
        "5": "Excellent example"
      },
      "domain_specific": false,
      "requires_context": false,
      "metadata": {
        "importance": "high",
        "category": "content_quality",
        "tags": ["tag1", "tag2"]
      }
    }
  ]
}
```

## Best Practices

- **Criteria Names**: Use descriptive, lowercase names with underscores
- **Weights**: Ensure weights sum to 1.0 or let the system normalize them
- **Examples**: Provide clear examples for each score level (1-5)
- **Evaluation Prompts**: Write specific, actionable prompts for the LLM judge
- **Metadata**: Use metadata to categorize and organize criteria
