# Your First Evaluation

This guide walks you through your first evaluation using the LLM-as-a-Judge system.

## 🎯 What You'll Learn

- How to evaluate a single response
- How to compare two responses
- Understanding the output format
- Basic configuration options

## Step 1: Single Response Evaluation

### Basic Evaluation

```bash
# Evaluate a single response
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence"
```

**Expected Output:**

```
🎯 Multi-Criteria LLM Evaluation Results
================================================================================
╭─────────────────── Overall Score ────────────────────╮
│ 3.8/5.0                                             │
│ Confidence: 88.5%                                   │
│ Based on 7 criteria                                 │
╰──────────────────────────────────────────────────────╯

📊 Detailed Criterion Scores
┏━━━━━━━━━━━━┳━━━━┳━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Criterion  ┃ Sc…┃ We… ┃ Con… ┃ Reasoning          ┃
┡━━━━━━━━━━━━╇━━━━╇━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ accuracy   │ 4…│ 20… │ 90.… │ Factually correct  │
│ clarity    │ 4…│ 15… │ 85.… │ Well articulated   │
│ relevance  │ 5…│ 15… │ 95.… │ Directly addresses │
└────────────┴────┴─────┴──────┴────────────────────┘

✅ Strengths: Clear, accurate, relevant
⚠️  Areas for Improvement: Lacks depth, needs examples
💡 Suggestions: Add more detail, provide context
```

### Understanding the Output

- **Overall Score**: Weighted average across all criteria (1-5 scale)
- **Confidence**: Judge's confidence in the assessment (0-100%)
- **Criterion Scores**: Individual scores for each evaluation dimension
- **Strengths/Weaknesses**: Identified areas of excellence and improvement
- **Suggestions**: Actionable recommendations for enhancement

## Step 2: Response Comparison

### Compare Two Responses

```bash
# Compare two responses
python -m src.llm_judge compare "Explain machine learning" \
  "ML is a subset of AI" \
  "Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed"
```

**Expected Output:**

```
🏆 Response Comparison Results
================================================================================
╭─────────────────── Winner ────────────────────╮
│ Response B                                       │
│ Confidence: 92.3%                               │
╰──────────────────────────────────────────────────╯

📊 Comparison Analysis
Response B demonstrates superior:
• Completeness: Provides comprehensive definition
• Accuracy: Technically precise terminology
• Clarity: Well-structured explanation
• Helpfulness: More actionable information

Response A shows:
• Brevity: Concise but lacks detail
• Accuracy: Correct but incomplete
```

## Step 3: Custom Configuration

### Using Different Models

```bash
# Use specific judge model
python -m src.llm_judge --judge-model claude-3 evaluate "Question" "Answer"

# Use different provider
python -m src.llm_judge --provider openai evaluate "Question" "Answer"
```

### Output Formats

```bash
# JSON output for programmatic use
python -m src.llm_judge --output json evaluate "Question" "Answer"

# Verbose output with detailed information
python -m src.llm_judge --verbose evaluate "Question" "Answer"
```

## Step 4: Batch Processing

### Create Sample Batch

```bash
# Create a sample batch file
python -m src.llm_judge create-sample-batch sample.jsonl
```

### Process Batch

```bash
# Process the batch file
python -m src.llm_judge batch sample.jsonl --output results.json
```

## 🎉 Congratulations!

You've successfully completed your first evaluations! Here's what you've learned:

- ✅ How to evaluate single responses
- ✅ How to compare multiple responses
- ✅ Understanding the output format
- ✅ Basic configuration options
- ✅ Batch processing basics

## Next Steps

- **[Configuration Guide](../configuration/README.md)** - Advanced configuration options
- **[API Reference](../api/README.md)** - Programmatic usage
- **[Examples](../examples/README.md)** - More complex examples
- **[Architecture Overview](../architecture/README.md)** - Understanding the system

## 🆘 Need Help?

- Check the [FAQ](../overview/README.md#faq)
- Review [Common Issues](../overview/README.md#common-issues)
- [Open an issue](https://github.com/superluminal-jp/llm-as-a-judge/issues)
