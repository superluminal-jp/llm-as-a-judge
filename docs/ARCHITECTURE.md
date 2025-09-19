# LLM-as-a-Judge: System Architecture

## Overview

The LLM-as-a-Judge system follows a layered architecture with clear separation of concerns, enabling scalability, maintainability, and extensibility.

## Evolutionary Architecture Design

### Current State: Domain-Driven Design Implementation (✅ Phase 2 Complete - Data Persistence & Custom Criteria)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       src/llm_judge/                                   │
├─────────────────────────────────────────────────────────────────────────┤
│ presentation/                    🖥️ Presentation Layer                 │
│ ├── cli/                        │                                      │
│ │   └── main.py                  │ • CLI Interface with Data Management│
│ └── (future: web, api)          │ • User Input/Output                │
├─────────────────────────────────────────────────────────────────────────┤
│ application/                     🔧 Application Layer                  │
│ ├── services/                   │                                      │
│ │   └── llm_judge_service.py    │ • Use Case Orchestration           │
│ └── use_cases/                  │ • Application Services              │
│     └── (planned)               │ • Cross-cutting Concerns            │
├─────────────────────────────────────────────────────────────────────────┤
│ domain/                         🧠 Domain Layer                        │
│ ├── evaluation/                 │                                      │
│ │   ├── criteria.py             │ • Multi-Criteria Evaluation Logic  │
│ │   ├── custom_criteria.py      │ • Custom Criteria Definition       │
│ │   └── weight_config.py        │ • Weight Configuration System      │
│ ├── persistence/                │                                      │
│ │   ├── models.py               │ • Data Persistence Models          │
│ │   └── interfaces.py           │ • Repository Interfaces            │
│ └── models/                     │ • Domain Models & Value Objects     │
├─────────────────────────────────────────────────────────────────────────┤
│ infrastructure/                 🔌 Infrastructure Layer               │
│ ├── clients/                    │                                      │
│ │   ├── openai_client.py        │ • External API Integration         │
│ │   ├── anthropic_client.py     │ • Data Persistence                 │
│ │   └── http_client.py          │ • External API Integration         │
│ ├── config/                     │ • Configuration Management         │
│ │   ├── config.py               │                                      │
│ │   └── logging_config.py       │                                      │
│ ├── persistence/                │ • Data Persistence Infrastructure   │
│ │   ├── json_repository.py      │                                      │
│ │   ├── persistence_service.py  │                                      │
│ │   └── migration.py            │                                      │
│ └── resilience/                 │ • Reliability Patterns             │
│     ├── retry_strategies.py     │                                      │
│     ├── fallback_manager.py     │                                      │
│     ├── timeout_manager.py      │                                      │
│     └── error_classification.py │                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Target State: Layered Production Architecture (Phase 3-4)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Layer                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   CLI Interface │  │   Web Dashboard │  │   REST APIs     │ │
│  │   (Click/Rich)  │  │   (React/Vue)   │  │   (FastAPI)     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Evaluation      │  │ Batch           │  │ Analytics       │ │
│  │ Orchestrator    │  │ Processing      │  │ Service         │ │
│  │                 │  │ Engine          │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Configuration   │  │ Error Handling  │  │ Monitoring      │ │
│  │ Management      │  │ & Resilience    │  │ & Observability │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                      Domain Layer                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Evaluation      │  │ Judge Models    │  │ Prompt          │ │
│  │ Aggregates      │  │ & Selection     │  │ Templates       │ │
│  │                 │  │ Strategy        │  │ & Engineering   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Quality         │  │ Ground Truth    │  │ Domain          │ │
│  │ Assurance       │  │ Management      │  │ Events          │ │
│  │ Services        │  │                 │  │ Publishing      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ LLM Provider    │  │ Data Storage    │  │ External        │ │
│  │ Clients         │  │ Systems         │  │ Integrations    │ │
│  │ • OpenAI        │  │ • PostgreSQL    │  │ • Monitoring    │ │
│  │ • Anthropic     │  │ • Redis Cache   │  │ • Analytics     │ │
│  │ • Local Models  │  │ • S3 Storage    │  │ • Alerting      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Testing Architecture

### Test Suite Organization (✅ COMPLETE - 123/123 Tests Passing)

The testing architecture follows the same layered approach as the application architecture, ensuring comprehensive coverage at each level:

```
tests/
├── unit/                           # 104 Unit Tests (100% passing)
│   ├── infrastructure/             # 76 Infrastructure tests
│   │   ├── test_openai_client.py   # OpenAI SDK integration tests
│   │   ├── test_anthropic_client.py# Anthropic SDK integration tests
│   │   ├── test_config.py          # Configuration management tests
│   │   ├── test_error_classification.py # Error handling tests (28 tests)
│   │   ├── test_fallback_manager.py# Resilience pattern tests (30 tests)
│   │   ├── test_http_client.py     # HTTP client infrastructure tests
│   │   └── test_timeout_manager.py # Timeout management tests (21 tests)
│   ├── application/                # Application layer tests (planned)
│   └── domain/                     # Domain layer tests (planned)
└── integration/                    # 19 Integration Tests (100% passing)
    ├── test_llm_judge_integration.py # End-to-end LLM judge functionality
    ├── test_error_integration.py     # Cross-system error handling
    └── test_timeout_integration.py   # Timeout behavior integration
```

### Testing Strategy by Layer

#### Infrastructure Layer Testing (76 tests)

- **API Client Testing**: Proper SDK mocking for OpenAI and Anthropic clients
- **Resilience Pattern Testing**: Circuit breakers, fallback management, retry strategies
- **Configuration Testing**: Environment loading, validation, error handling
- **Error Classification Testing**: 28 tests covering 6 error categories
- **Timeout Management Testing**: 21 tests covering async timeout patterns

#### Integration Layer Testing (19 tests)

- **End-to-End Functionality**: Full LLM judge workflows including compare_responses
- **Provider Integration**: Real and mock LLM provider testing
- **Error Recovery Testing**: Cross-system error handling and resilience
- **Fallback Behavior Testing**: Degraded mode operation validation

### Test Infrastructure Improvements

#### ✅ Completed Pytest Overhaul

- **AsyncMock Configuration**: Fixed incorrect async mocking for synchronous SDK methods
- **SDK Exception Mocking**: Proper response object creation for OpenAI/Anthropic exceptions
- **Test Isolation**: Eliminated state pollution between tests
- **Async Decorator Management**: Added missing `@pytest.mark.asyncio` decorators
- **Pytest Configuration**: Updated for proper async support and warning filtering

#### Test Reliability Metrics

- **Success Rate**: 123/123 tests passing (100%)
- **Unit Test Coverage**: 104 tests covering all infrastructure components
- **Integration Coverage**: 19 tests validating cross-system functionality
- **Error Coverage**: Comprehensive testing of all 6 error categories
- **Resilience Coverage**: All fallback and retry patterns tested

### Architecture Evolution Path

#### DDD Architecture Implementation Status

```
✅ COMPLETED: Domain-Driven Structure (Phase 1-2)
├── src/llm_judge/                    # Main package with proper layering
│   ├── domain/                       # Business logic (minimal dependencies)
│   │   ├── evaluation/               # Core evaluation domain
│   │   │   ├── criteria.py           # ✅ Multi-criteria evaluation system
│   │   │   ├── custom_criteria.py    # ✅ Custom criteria definition
│   │   │   └── weight_config.py      # ✅ Weight configuration system
│   │   ├── persistence/              # ✅ Data persistence domain
│   │   │   ├── models.py             # ✅ Persistence domain models
│   │   │   └── interfaces.py         # ✅ Repository interfaces
│   │   └── models/                   # Domain models and value objects
│   ├── application/                  # Use cases and orchestration
│   │   ├── services/
│   │   │   └── llm_judge_service.py # ✅ Enhanced with persistence & custom criteria
│   │   └── use_cases/               # Specific use case implementations
│   ├── infrastructure/              # External concerns
│   │   ├── clients/                 # ✅ Real LLM API integrations
│   │   │   ├── openai_client.py    # ✅ OpenAI GPT-4 client
│   │   │   ├── anthropic_client.py # ✅ Anthropic Claude client
│   │   │   └── http_client.py      # ✅ HTTP infrastructure
│   │   ├── config/                  # ✅ Configuration management
│   │   │   ├── config.py           # ✅ Enhanced with persistence & custom criteria
│   │   │   └── logging_config.py   # ✅ Structured logging
│   │   ├── persistence/             # ✅ Data persistence infrastructure
│   │   │   ├── json_repository.py  # ✅ JSON-based data storage
│   │   │   ├── persistence_service.py # ✅ Persistence orchestration
│   │   │   └── migration.py        # ✅ Data migration support
│   │   └── resilience/             # ✅ Production reliability patterns
│   │       ├── retry_strategies.py # ✅ Exponential backoff retry
│   │       ├── fallback_manager.py # ✅ Circuit breaker & fallback
│   │       ├── timeout_manager.py  # ✅ Request timeout handling
│   │       └── error_classification.py # ✅ Error categorization
│   └── presentation/                # User interfaces
│       ├── cli/                     # ✅ Enhanced CLI with data management
│       │   └── main.py             # ✅ Data commands & custom criteria support
│       └── (future: web, api)       # 🔄 Planned REST API (Phase 3)
├── tests/                           # ✅ Comprehensive test suite
│   ├── unit/                        # ✅ Layer-separated unit tests
│   │   ├── domain/                  # ✅ Custom criteria & persistence tests
│   │   ├── application/
│   │   └── infrastructure/          # ✅ Persistence infrastructure tests
│   └── integration/                 # ✅ Cross-layer integration tests
└── docs/                           # ✅ Layered documentation strategy
```

#### Component Interaction Patterns

**Request Processing Flow (Current DDD Implementation)**:

```
1. CLI Input (presentation/cli/__main__.py)
   ↓
2. Application Service Invocation (application/services/llm_judge_service.py)
   ↓
3. Configuration Loading (infrastructure/config/config.py)
   ↓
4. Provider Selection & Client Creation (infrastructure/clients/)
   ↓
5. Resilience Pattern Application (infrastructure/resilience/)
   ├── Retry Logic (retry_strategies.py)
   ├── Timeout Management (timeout_manager.py)
   ├── Circuit Breaker (fallback_manager.py)
   └── Error Classification (error_classification.py)
   ↓
6. LLM API Invocation (openai_client.py / anthropic_client.py)
   ↓
7. Response Processing & Domain Model Creation (domain/)
   ↓
8. Result Return through Application Layer
   ↓
9. CLI Output Formatting (presentation/cli/)
```

**Error Handling Flow (Current Implementation)**:

```
Error Detection (All Layers)
   ↓
Error Classification (infrastructure/resilience/error_classification.py)
├── Transient Errors (Network, Rate Limits)
├── Permanent Errors (Auth, Client Errors)
├── Server Errors (5xx responses)
└── Timeout Errors (Request timeouts)
   ↓
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ Transient   │ Rate Limit  │ Server      │ Permanent   │
│ → Retry     │ → Backoff   │ → Fallback  │ → Fail Fast│
│   Logic     │   Strategy  │   Provider  │   Response  │
└─────────────┴─────────────┴─────────────┴─────────────┘
   ↓
Structured Logging (infrastructure/config/logging_config.py)
├── Error Details with Context
├── Performance Metrics
├── Audit Trail
└── Debug Information
   ↓
Graceful Degradation (infrastructure/resilience/fallback_manager.py)
├── Cached Response (if available)
├── Simplified Response
├── Alternative Provider
└── User-Friendly Error Message
```

## Core Components

### 1. Domain Layer

#### Evaluation Models

```python
@dataclass
class Evaluation:
    id: str
    candidate_response: CandidateResponse
    judge_model: str
    evaluation_type: EvaluationType
    result: Optional[EvaluationResult]
    status: EvaluationStatus
    created_at: datetime
    completed_at: Optional[datetime]

@dataclass
class CandidateResponse:
    prompt: str
    response: str
    model: str
    metadata: Dict[str, Any]

@dataclass
class EvaluationResult:
    score: float
    reasoning: str
    confidence: float
    detailed_scores: Dict[str, float]
```

#### Prompt Templates

- **DirectScoringTemplate**: Single response evaluation
- **PairwiseComparisonTemplate**: A vs B comparison
- **ReferenceBasedTemplate**: Comparison with golden examples
- **CustomTemplate**: User-defined evaluation criteria

#### Judge Models

- **LLMJudge**: Core evaluation engine
- **EnsembleJudge**: Multiple judge consensus
- **CalibratedJudge**: Bias-corrected evaluations

### 2. Application Layer

#### Evaluation Service

```python
class EvaluationService:
    def evaluate_single(self, request: SingleEvaluationRequest) -> EvaluationResult
    def evaluate_pairwise(self, request: PairwiseRequest) -> ComparisonResult
    def evaluate_batch(self, requests: List[EvaluationRequest]) -> BatchResult
    def get_evaluation_history(self, filters: EvaluationFilters) -> List[Evaluation]
```

#### Batch Processing

```python
class BatchProcessor:
    def process_evaluations(self, batch: EvaluationBatch) -> BatchResult
    def get_batch_status(self, batch_id: str) -> BatchStatus
    def cancel_batch(self, batch_id: str) -> bool
```

#### Analytics Service

```python
class AnalyticsService:
    def get_evaluation_metrics(self, timeframe: TimeRange) -> EvaluationMetrics
    def compare_models(self, model_ids: List[str]) -> ModelComparison
    def analyze_judge_consistency(self, judge_id: str) -> ConsistencyReport
```

### 3. Infrastructure Layer

#### LLM Clients

```python
class LLMClient(ABC):
    def generate_evaluation(self, prompt: str) -> LLMResponse
    def is_available(self) -> bool
    def get_usage_stats(self) -> UsageStats

class OpenAIClient(LLMClient): ...
class AnthropicClient(LLMClient): ...
class LocalClient(LLMClient): ...
```

#### Data Storage

- **Primary Storage**: PostgreSQL for evaluation history and metadata
- **Cache Layer**: Redis for frequently accessed data
- **File Storage**: S3-compatible for large evaluation datasets

#### Monitoring & Observability

- **Structured Logging**: JSON logs with correlation IDs
- **Metrics Collection**: Prometheus-compatible metrics
- **Health Checks**: Service availability monitoring
- **Performance Tracking**: Latency and throughput metrics

## Data Flow

### Single Evaluation Flow

1. **Request Reception**: Validate and normalize evaluation request
2. **Prompt Generation**: Select template and generate judge prompt
3. **LLM Invocation**: Call judge LLM with retry logic
4. **Response Processing**: Parse and validate LLM response
5. **Result Storage**: Persist evaluation result and metadata
6. **Response Return**: Return structured evaluation result

### Batch Processing Flow

1. **Batch Creation**: Queue evaluation requests
2. **Parallel Processing**: Distribute across worker threads
3. **Result Aggregation**: Collect and combine results
4. **Status Updates**: Track and report batch progress
5. **Completion Notification**: Alert when batch completes

## Scalability Considerations

### Horizontal Scaling

- **Stateless Services**: All application services are stateless
- **Load Balancing**: Distribute requests across service instances
- **Queue-Based Processing**: Decouple request handling from processing
- **Database Sharding**: Partition data across multiple databases

### Performance Optimization

- **Connection Pooling**: Reuse LLM API connections
- **Response Caching**: Cache identical evaluation requests
- **Batch API Usage**: Group multiple requests to LLM providers
- **Async Processing**: Non-blocking I/O for concurrent requests

### Resource Management

- **Rate Limiting**: Respect LLM provider API limits
- **Circuit Breakers**: Protect against cascading failures
- **Timeout Handling**: Graceful handling of slow requests
- **Memory Management**: Efficient handling of large datasets

## Security Architecture

### Authentication & Authorization

- **API Keys**: Secure access to system endpoints
- **Role-Based Access**: Different permission levels
- **Audit Logging**: Track all user actions
- **Rate Limiting**: Prevent abuse and DoS attacks

### Data Protection

- **Encryption**: TLS in transit, AES-256 at rest
- **PII Handling**: Automatic detection and redaction
- **Data Retention**: Configurable retention policies
- **Backup & Recovery**: Regular backups with encryption

### Infrastructure Security

- **Network Segmentation**: Isolate components
- **Container Security**: Secure container images
- **Secrets Management**: Encrypted credential storage
- **Vulnerability Scanning**: Regular security assessments

## Deployment Architecture

### Development Environment

- **Local Development**: Docker Compose for full stack
- **Testing**: Isolated test environments with mock services
- **CI/CD**: Automated testing and deployment pipelines

### Production Environment

- **Container Orchestration**: Kubernetes for service management
- **Service Mesh**: Istio for service-to-service communication
- **Monitoring Stack**: Prometheus, Grafana, ELK stack
- **Disaster Recovery**: Multi-region deployment capabilities

## Integration Patterns

### API Integration

- **REST APIs**: Standard HTTP APIs for synchronous operations
- **WebSocket APIs**: Real-time evaluation status updates
- **Webhook APIs**: Callback notifications for batch completions
- **GraphQL**: Flexible query interface for analytics

### Message Queue Integration

- **Apache Kafka**: High-throughput event streaming
- **RabbitMQ**: Reliable message queuing
- **AWS SQS**: Cloud-native queuing service
- **Redis Streams**: Lightweight message streaming

### External Service Integration

- **LLM Providers**: OpenAI, Anthropic, Cohere, local models
- **Storage Providers**: AWS S3, Google Cloud Storage, MinIO
- **Monitoring Services**: DataDog, New Relic, CloudWatch
- **Analytics Platforms**: Integration with BI tools
