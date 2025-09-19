# LLM-as-a-Judge Architecture

This document describes the architecture of the LLM-as-a-Judge system, which follows Domain-Driven Design (DDD), Clean Architecture, and SOLID principles.

## 🏗️ Architecture Overview

The system is organized into four main layers following Clean Architecture principles:

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   CLI Interface │  │   REST API      │  │   Web UI    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Use Cases     │  │   Application   │  │   Services  │ │
│  │                 │  │   Services      │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                      Domain Layer                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Evaluation    │  │   Batch         │  │   Shared    │ │
│  │   Bounded       │  │   Processing    │  │   Kernel    │ │
│  │   Context       │  │   Bounded       │  │             │ │
│  │                 │  │   Context       │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   LLM Providers │  │   Persistence   │  │   Resilience│ │
│  │                 │  │                 │  │   & Config  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Directory Structure

```
src/llm_judge/
├── domain/                          # Domain Layer
│   ├── shared_kernel/              # Shared Kernel
│   │   ├── value_objects.py        # Common value objects
│   │   ├── domain_events.py        # Domain events
│   │   └── exceptions.py           # Domain exceptions
│   ├── evaluation/                 # Evaluation Bounded Context
│   │   ├── entities.py             # Domain entities
│   │   ├── value_objects.py        # Context-specific value objects
│   │   ├── services.py             # Domain services
│   │   ├── repositories.py         # Repository interfaces
│   │   └── specifications.py       # Business rules
│   ├── batch_processing/           # Batch Processing Bounded Context
│   │   ├── entities.py             # Batch entities
│   │   ├── value_objects.py        # Batch value objects
│   │   ├── services.py             # Batch services
│   │   ├── repositories.py         # Batch repositories
│   │   └── specifications.py       # Batch specifications
│   └── persistence/                # Persistence Bounded Context
│       ├── models.py               # Persistence models
│       ├── interfaces.py           # Repository interfaces
│       └── exceptions.py           # Persistence exceptions
├── application/                     # Application Layer
│   ├── use_cases/                  # Use Cases
│   │   ├── evaluation_use_cases.py # Evaluation use cases
│   │   ├── batch_use_cases.py      # Batch use cases
│   │   ├── criteria_use_cases.py   # Criteria use cases
│   │   └── persistence_use_cases.py# Persistence use cases
│   └── services/                   # Application Services
│       ├── llm_judge_service.py    # Main judge service
│       └── batch_service.py        # Batch processing service
├── infrastructure/                  # Infrastructure Layer
│   ├── llm_providers/              # LLM Provider Implementations
│   │   ├── base.py                 # Base provider interface
│   │   ├── openai_provider.py      # OpenAI implementation
│   │   ├── anthropic_provider.py   # Anthropic implementation
│   │   ├── bedrock_provider.py     # AWS Bedrock implementation
│   │   ├── mock_provider.py        # Mock implementation
│   │   └── provider_factory.py     # Provider factory
│   ├── persistence/                # Persistence Implementations
│   │   ├── json_repository.py      # JSON file storage
│   │   ├── persistence_service.py  # Persistence service
│   │   └── migration.py            # Data migrations
│   ├── resilience/                 # Resilience Patterns
│   │   ├── retry_strategies.py     # Retry logic
│   │   ├── timeout_manager.py      # Timeout handling
│   │   ├── circuit_breaker.py      # Circuit breaker pattern
│   │   └── error_classification.py # Error handling
│   └── config/                     # Configuration
│       ├── config.py               # Main configuration
│       └── logging_config.py       # Logging configuration
└── presentation/                    # Presentation Layer
    ├── cli/                        # Command Line Interface
    │   ├── main.py                 # CLI entry point
    │   ├── commands/               # CLI commands
    │   └── formatters/             # Output formatters
    └── api/                        # REST API
        ├── app.py                  # FastAPI application
        ├── routes/                 # API routes
        ├── schemas/                # Request/Response schemas
        └── middleware/             # API middleware
```

## 🎯 Bounded Contexts

### 1. Evaluation Bounded Context

**Purpose**: Handles the core business logic of evaluating LLM responses.

**Key Concepts**:

- `Evaluation`: Root entity representing an evaluation
- `CriterionDefinition`: Definition of evaluation criteria
- `CriterionScore`: Score for a specific criterion
- `MultiCriteriaResult`: Result of multi-criteria evaluation

**Domain Services**:

- `EvaluationService`: Core evaluation logic
- `CriteriaService`: Criteria management
- `ScoringService`: Scoring algorithms

### 2. Batch Processing Bounded Context

**Purpose**: Manages batch processing of multiple evaluations.

**Key Concepts**:

- `BatchRequest`: Request for batch processing
- `BatchResult`: Result of batch processing
- `BatchProgress`: Progress tracking
- `BatchConfiguration`: Processing configuration

**Domain Services**:

- `BatchProcessingService`: Batch orchestration
- `BatchMonitoringService`: Progress monitoring
- `BatchValidationService`: Batch validation

### 3. Shared Kernel

**Purpose**: Common domain concepts used across bounded contexts.

**Key Concepts**:

- `EntityId`: Base identifier
- `Timestamp`: Time value object
- `Score`: Score value object
- `Confidence`: Confidence value object
- `ModelName`: Model name value object
- `ProviderName`: Provider name value object

**Domain Events**:

- `EvaluationCompleted`: Raised when evaluation completes
- `EvaluationFailed`: Raised when evaluation fails
- `BatchProcessingStarted`: Raised when batch starts
- `BatchProcessingCompleted`: Raised when batch completes

## 🔧 Design Patterns

### 1. Domain-Driven Design (DDD)

- **Entities**: Objects with identity (Evaluation, BatchRequest)
- **Value Objects**: Immutable objects defined by attributes (Score, Confidence)
- **Aggregates**: Consistency boundaries (Evaluation aggregate)
- **Domain Services**: Business logic that doesn't belong to entities
- **Repositories**: Data access abstraction
- **Specifications**: Business rules encapsulation

### 2. Clean Architecture

- **Dependency Inversion**: Dependencies point inward
- **Interface Segregation**: Small, focused interfaces
- **Single Responsibility**: Each class has one reason to change
- **Open/Closed**: Open for extension, closed for modification

### 3. SOLID Principles

- **S**ingle Responsibility: Each class has one responsibility
- **O**pen/Closed: Open for extension, closed for modification
- **L**iskov Substitution: Derived classes must be substitutable
- **I**nterface Segregation: Many specific interfaces vs one general
- **D**ependency Inversion: Depend on abstractions, not concretions

### 4. Resilience Patterns

- **Circuit Breaker**: Prevent cascading failures
- **Retry with Backoff**: Handle transient failures
- **Timeout Management**: Prevent hanging requests
- **Bulkhead**: Isolate resources
- **Fallback**: Graceful degradation

## 🚀 Use Cases

### Evaluation Use Cases

1. **EvaluateResponseUseCase**: Evaluate a single response
2. **CompareResponsesUseCase**: Compare two responses
3. **MultiCriteriaEvaluationUseCase**: Multi-criteria evaluation

### Batch Use Cases

1. **ProcessBatchUseCase**: Process a batch of evaluations
2. **CreateBatchUseCase**: Create a new batch
3. **MonitorBatchUseCase**: Monitor batch progress
4. **CancelBatchUseCase**: Cancel a running batch

### Criteria Use Cases

1. **CreateCriteriaUseCase**: Create new evaluation criteria
2. **UpdateCriteriaUseCase**: Update existing criteria
3. **DeleteCriteriaUseCase**: Delete criteria
4. **ListCriteriaUseCase**: List available criteria

## 🔌 Infrastructure

### LLM Providers

- **OpenAIProvider**: OpenAI GPT models
- **AnthropicProvider**: Anthropic Claude models
- **BedrockProvider**: AWS Bedrock models
- **MockProvider**: Mock implementation for testing

### Persistence

- **JsonRepository**: JSON file-based storage
- **PersistenceService**: High-level persistence operations
- **MigrationService**: Database migrations

### Resilience

- **RetryManager**: Retry logic with exponential backoff
- **TimeoutManager**: Request timeout handling
- **CircuitBreaker**: Circuit breaker pattern
- **ErrorClassifier**: Error classification and handling

## 📊 Domain Events

The system uses domain events for loose coupling and event-driven architecture:

```python
# Example: Evaluation completed event
@dataclass(frozen=True)
class EvaluationCompleted(DomainEvent):
    evaluation_id: EvaluationId
    score: float
    confidence: float
    criteria_count: int
    processing_duration_ms: float
    provider: str
    model: str
```

## 🔄 Data Flow

1. **Request**: User sends evaluation request via CLI/API
2. **Use Case**: Application layer orchestrates the use case
3. **Domain**: Domain layer validates business rules
4. **Infrastructure**: Infrastructure layer calls external services
5. **Response**: Result flows back through the layers
6. **Events**: Domain events are published for side effects

## 🧪 Testing Strategy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **Domain Tests**: Test business logic and rules
- **Contract Tests**: Test external service contracts
- **End-to-End Tests**: Test complete user workflows

## 📈 Monitoring & Observability

- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Metrics**: Performance and business metrics
- **Tracing**: Distributed request tracing
- **Health Checks**: Service health monitoring
- **Error Tracking**: Comprehensive error classification

## 🔒 Security

- **Input Validation**: All inputs are validated
- **Authentication**: API key-based authentication
- **Authorization**: Role-based access control
- **Data Protection**: Sensitive data encryption
- **Audit Logging**: Comprehensive audit trails

This architecture ensures the system is maintainable, testable, scalable, and follows industry best practices for enterprise software development.
