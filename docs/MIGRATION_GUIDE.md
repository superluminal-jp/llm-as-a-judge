# Migration Guide: From Examples to Criteria

This guide helps you migrate from the old `examples/` directory structure to the new unified `criteria/` directory system.

## 🔄 What Changed

### Old Structure (Deprecated)

```
examples/
├── academic_criteria.json
├── custom_weights_config.json
├── default_equal_weights_config.json
├── technical_criteria.json
└── weight_configuration_examples.md
```

### New Structure (Current)

```
criteria/
├── README.md
├── default.json
├── custom.json
└── template.json
```

## 📋 Migration Steps

### Step 1: Update File References

**Old CLI Usage:**

```bash
# Old way (no longer works)
python -m src.llm_judge evaluate "Question" "Answer" --criteria-file examples/academic_criteria.json
```

**New CLI Usage:**

```bash
# New way
python -m src.llm_judge evaluate "Question" "Answer" --criteria-file criteria/default.json
```

### Step 2: Update Programmatic Usage

**Old Code:**

```python
from src.llm_judge.domain.evaluation.custom_criteria import CustomCriteriaDefinition

# Old way (deprecated)
criteria = CustomCriteriaDefinition.from_file("examples/academic_criteria.json")
```

**New Code:**

```python
from src.llm_judge.domain.evaluation.criteria import EvaluationCriteria

# New way
criteria = EvaluationCriteria.from_file("criteria/default.json")
```

### Step 3: Update Configuration Files

**Old config.json:**

```json
{
  "default_criteria_type": "academic",
  "use_equal_weights": true
}
```

**New config.json:**

```json
{
  "default_criteria_type": "default",
  "use_equal_weights": false,
  "evaluation": {
    "normalize_weights": true,
    "minimum_criteria": 1
  }
}
```

## 🔧 File Format Changes

### Old Format (Deprecated)

```json
{
  "criteria": [
    {
      "name": "accuracy",
      "description": "Factual correctness",
      "criterion_type": "factual",
      "weight": 0.25
    }
  ]
}
```

### New Format (Current)

```json
{
  "name": "Criteria Set Name",
  "description": "Description of the criteria set",
  "criteria": [
    {
      "name": "accuracy",
      "description": "Factual correctness",
      "weight": 0.25,
      "evaluation_prompt": "Rate the factual accuracy",
      "examples": {
        "1": "Poor example",
        "5": "Excellent example"
      },
      "domain_specific": false,
      "requires_context": false,
      "metadata": {
        "importance": "high",
        "category": "content_quality"
      }
    }
  ]
}
```

## 📁 Specific File Migrations

### academic_criteria.json → default.json

The old `academic_criteria.json` has been replaced with `criteria/default.json` which contains comprehensive evaluation criteria.

**Migration:**

```bash
# Old
--criteria-file examples/academic_criteria.json

# New
--criteria-file criteria/default.json
```

### technical_criteria.json → custom.json

The old `technical_criteria.json` has been replaced with `criteria/custom.json` which provides an example of custom criteria configuration.

**Migration:**

```bash
# Old
--criteria-file examples/technical_criteria.json

# New
--criteria-file criteria/custom.json
```

### weight_configuration_examples.md → criteria/README.md

The old weight configuration documentation has been integrated into the new `criteria/README.md` file.

## 🚀 New Features

### Enhanced Criteria Format

The new criteria format includes additional fields:

- `evaluation_prompt`: Specific prompts for the LLM judge
- `examples`: Examples for different score levels
- `domain_specific`: Whether the criterion is domain-specific
- `requires_context`: Whether additional context is needed
- `metadata`: Additional categorization and tagging

### Template System

The new system includes a template file for creating custom criteria:

```bash
# Create criteria template
python -m src.llm_judge create-criteria-template my-criteria.json --name "My Criteria" --description "Custom evaluation criteria"
```

### CLI String Format

You can now define criteria directly via CLI:

```bash
python -m src.llm_judge evaluate "Question" "Answer" --custom-criteria "accuracy:Factual correctness:0.4,clarity:How clear the response is:0.3,helpfulness:How useful the response is:0.3"
```

## 🔍 Validation and Testing

### Test Your Migration

1. **Validate New Criteria Files:**

```bash
# Test default criteria
python -m src.llm_judge evaluate "Test question" "Test answer" --criteria-file criteria/default.json

# Test custom criteria
python -m src.llm_judge evaluate "Test question" "Test answer" --criteria-file criteria/custom.json
```

2. **Compare Results:**

```bash
# Run with old and new criteria to ensure consistency
python -m src.llm_judge evaluate "Question" "Answer" --criteria-file criteria/default.json --output json > new_results.json
```

### Common Issues and Solutions

#### Issue: "File not found" errors

**Solution:** Update file paths from `examples/` to `criteria/`

#### Issue: "Invalid criteria format" errors

**Solution:** Update criteria files to use the new format with required fields

#### Issue: "Unknown criterion type" errors

**Solution:** Remove `criterion_type` field from criteria definitions (no longer used)

## 📚 Additional Resources

- **[Criteria Documentation](criteria/README.md)** - Complete criteria system documentation
- **[Configuration Guide](configuration/README.md)** - Updated configuration options
- **[API Reference](api/README.md)** - Updated API documentation
- **[Examples](examples/README.md)** - Updated usage examples

## 🆘 Need Help?

If you encounter issues during migration:

1. Check the [FAQ](overview/README.md#faq)
2. Review [Common Issues](overview/README.md#common-issues)
3. [Open an issue](https://github.com/superluminal-jp/llm-as-a-judge/issues)

## 🎉 Benefits of Migration

After migrating to the new criteria system, you'll have access to:

- ✅ **Unified criteria format** across all evaluation types
- ✅ **Enhanced metadata** for better categorization
- ✅ **Template system** for easy custom criteria creation
- ✅ **CLI string format** for quick criteria definition
- ✅ **Better documentation** and examples
- ✅ **Improved validation** and error handling
- ✅ **Future-proof architecture** for new features

---

**Ready to migrate?** Start with updating your file references and test with the new criteria files!
