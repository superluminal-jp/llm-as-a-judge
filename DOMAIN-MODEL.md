# LLM-as-a-Judge: Domain Model & Ubiquitous Language

## Bounded Context: LLM Evaluation Services

### Context Map
```
┌─────────────────────────────────────────────────┐
│              LLM Evaluation Context             │
│                                                 │
│  ┌─────────────────┐  ┌─────────────────────┐   │
│  │   Evaluation    │  │    Judge Models     │   │
│  │   Orchestration │◄─┤    & Templates     │   │
│  └─────────────────┘  └─────────────────────┘   │
│           │                       │             │
│           ▼                       ▼             │
│  ┌─────────────────┐  ┌─────────────────────┐   │
│  │   Candidate     │  │    Evaluation       │   │
│  │   Responses     │  │    Results          │   │
│  └─────────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────┘
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
  │   LLM API   │ │  Storage    │ │ Monitoring  │
  │  Services   │ │  Services   │ │  Services   │
  └─────────────┘ └─────────────┘ └─────────────┘
```

## Ubiquitous Language

### Core Domain Terms

#### Judge (Entity)
**Definition**: An LLM system that evaluates other LLM responses according to specified criteria.
**Business Rules**:
- Must have consistent evaluation behavior across similar inputs
- Must provide reasoning for all evaluation decisions
- Must operate within defined confidence thresholds
- Must respect rate limits and cost constraints

**Invariants**:
- Judge must be available before accepting evaluation requests
- Judge responses must be parseable into structured format
- Judge must maintain evaluation history for calibration

#### Candidate Response (Value Object)
**Definition**: An LLM-generated response that requires evaluation.
**Composition**:
- Original prompt that generated the response
- The actual response text
- Generating model identification
- Generation metadata (temperature, tokens, etc.)

**Business Rules**:
- Must contain the complete original prompt for context
- Response text must be non-empty
- Model identification required for comparative analysis

#### Evaluation Criteria (Value Object)
**Definition**: Specific dimensions along which responses are assessed.
**Standard Criteria**:
- **Relevance**: How well the response addresses the prompt
- **Accuracy**: Factual correctness of information provided
- **Clarity**: How clearly and understandably the response is written
- **Completeness**: Whether the response fully addresses all aspects
- **Helpfulness**: Practical utility of the response to the user

**Custom Criteria Structure**:
- Name and description
- Scoring scale (typically 1-5)
- Weighting for multi-criteria evaluations
- Evaluation instructions for judge

#### Evaluation Session (Aggregate Root)
**Definition**: A complete evaluation workflow encompassing request, processing, and results.
**Lifecycle States**:
1. **Requested**: Initial state when evaluation is submitted
2. **Queued**: Waiting for available judge processing capacity
3. **Processing**: Judge is actively evaluating the response
4. **Completed**: Evaluation finished successfully with results
5. **Failed**: Evaluation could not be completed (error state)
6. **Cancelled**: Evaluation was cancelled before completion

**Domain Events**:
- `EvaluationRequested`: New evaluation submitted to system
- `EvaluationStarted`: Judge begins processing evaluation
- `EvaluationCompleted`: Results available for retrieval
- `EvaluationFailed`: Processing encountered unrecoverable error
- `EvaluationCancelled`: User or system cancelled processing

#### Evaluation Result (Value Object)
**Definition**: The structured output of a judge's assessment.
**Components**:
- **Primary Score**: Main evaluation score (1-5 scale)
- **Reasoning**: Natural language explanation of the score
- **Confidence**: Judge's confidence in the assessment (0-1)
- **Dimensional Scores**: Breakdown by individual criteria
- **Metadata**: Processing information (model, timestamp, etc.)

**Quality Constraints**:
- Score must be within specified range
- Reasoning must be substantial (minimum character count)
- Confidence must reflect actual certainty
- All dimensional scores must sum coherently

### Evaluation Methodologies

#### Direct Scoring
**Definition**: Judge evaluates a single response against specified criteria.
**Process Flow**:
1. Present original prompt and candidate response to judge
2. Specify evaluation criteria and scoring scale
3. Request structured assessment with reasoning
4. Validate and parse judge response into result format

**Business Rules**:
- Must include complete original context
- Criteria must be clearly defined and measurable
- Judge must provide reasoning for transparency
- Results must be repeatable within confidence bounds

#### Pairwise Comparison
**Definition**: Judge compares two responses to determine which is superior.
**Process Flow**:
1. Present original prompt and both responses (A and B)
2. Request comparative assessment across multiple dimensions
3. Determine overall winner or declare tie
4. Provide detailed reasoning for decision

**Business Rules**:
- Both responses must address the same original prompt
- Judge must evaluate multiple comparative dimensions
- Winner determination must be based on objective criteria
- Tie declarations allowed when responses are equivalent

#### Reference-Based Evaluation
**Definition**: Judge evaluates response quality by comparison to golden examples.
**Process Flow**:
1. Present candidate response and reference examples
2. Request assessment of similarity and quality gaps
3. Score based on alignment with reference standards
4. Identify specific strengths and improvement areas

**Business Rules**:
- Reference examples must be high-quality and relevant
- Evaluation must identify specific differences
- Scoring must reflect degree of alignment with references
- Feedback must be actionable for improvement

### Quality Assurance Concepts

#### Judge Calibration
**Definition**: Process of verifying and adjusting judge consistency.
**Mechanisms**:
- **Ground Truth Validation**: Compare judge results to human expert assessments
- **Inter-Judge Consistency**: Compare multiple judges on same evaluations
- **Temporal Stability**: Verify judge maintains consistent behavior over time
- **Bias Detection**: Identify and correct systematic evaluation biases

#### Evaluation Confidence
**Definition**: Measure of reliability in a specific evaluation result.
**Factors Affecting Confidence**:
- Judge model's stated confidence level
- Consistency with historical similar evaluations
- Alignment with ground truth examples
- Clear reasoning and specific evidence
- Absence of contradictory assessments

#### Quality Metrics
**Definition**: Measurable indicators of evaluation system performance.
**Key Metrics**:
- **Accuracy**: Correlation with human expert judgments
- **Consistency**: Repeatability of results for identical inputs
- **Coverage**: Percentage of evaluation requests successfully processed
- **Latency**: Time from request to result availability
- **Cost Efficiency**: Economic cost per evaluation

## Domain Services

### Judge Selection Service
**Responsibility**: Determine optimal judge for specific evaluation requirements.
**Logic**:
- Match judge capabilities to evaluation criteria
- Consider cost and performance tradeoffs
- Account for current system load and availability
- Apply domain-specific judge preferences

### Evaluation Orchestration Service
**Responsibility**: Coordinate complex evaluation workflows.
**Capabilities**:
- Batch processing management
- Multi-judge consensus building
- Retry and fallback handling
- Result aggregation and synthesis

### Quality Assurance Service
**Responsibility**: Monitor and maintain evaluation quality standards.
**Functions**:
- Continuous judge calibration
- Anomaly detection in results
- Performance trend analysis
- Ground truth dataset management

## Business Invariants

### System-Level Invariants
1. **Evaluation Completeness**: Every requested evaluation must reach a terminal state (completed, failed, or cancelled)
2. **Result Immutability**: Once an evaluation is completed, its core results cannot be modified
3. **Traceability**: Every evaluation must maintain complete audit trail from request to result
4. **Cost Control**: System must respect configured budget limits and never exceed spending thresholds

### Judge-Level Invariants
1. **Response Format**: Judge responses must always be parseable into the expected result structure
2. **Reasoning Requirement**: Every evaluation must include human-readable reasoning
3. **Score Validity**: All scores must fall within the specified valid ranges
4. **Context Preservation**: Judge must base evaluation solely on provided context, not external knowledge

### Quality Invariants
1. **Minimum Confidence**: Results below minimum confidence threshold must be flagged or rejected
2. **Consistency Bounds**: Repeated evaluations of identical inputs must fall within acceptable variance
3. **Ground Truth Alignment**: Judge behavior must correlate with validated ground truth examples
4. **Bias Limitations**: Systematic biases must be detected and remain within acceptable bounds

## Domain Events

### Evaluation Lifecycle Events
- `EvaluationRequested(sessionId, candidateResponse, criteria, requestedBy, timestamp)`
- `EvaluationQueued(sessionId, estimatedProcessingTime, queuePosition)`
- `EvaluationStarted(sessionId, assignedJudge, startTime)`
- `EvaluationCompleted(sessionId, result, processingDuration, cost)`
- `EvaluationFailed(sessionId, errorType, errorMessage, retryable)`
- `EvaluationCancelled(sessionId, reason, cancelledBy)`

### Quality Assurance Events
- `JudgeCalibrationStarted(judgeId, groundTruthSet, calibrationType)`
- `JudgeCalibrationCompleted(judgeId, accuracyScore, biasMetrics, recommendations)`
- `QualityThresholdViolation(sessionId, violationType, measuredValue, threshold)`
- `GroundTruthUpdated(datasetId, addedExamples, removedExamples, version)`

### System Events
- `JudgeAvailabilityChanged(judgeId, previousStatus, currentStatus, reason)`
- `CostThresholdApproached(currentCost, threshold, projectedOverage)`
- `PerformanceDegradation(metricType, currentValue, expectedValue, severity)`

This domain model provides the sophisticated conceptual foundation needed to guide all implementation decisions and ensure the system correctly reflects the business domain of LLM evaluation services.