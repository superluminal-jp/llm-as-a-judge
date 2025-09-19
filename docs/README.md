# LLM-as-a-Judge Documentation

This directory contains comprehensive project documentation, organized by topic and audience for easy navigation and maintenance.

## 📚 Core Documentation

| Document                                                         | Level            | Purpose                                              | Audience                     |
| ---------------------------------------------------------------- | ---------------- | ---------------------------------------------------- | ---------------------------- |
| **[STRATEGY.md](STRATEGY.md)**                                   | Strategic        | Business vision, market analysis, success metrics    | Leadership, Product Strategy |
| **[ARCHITECTURE.md](ARCHITECTURE.md)**                           | System           | Technical architecture, design patterns, scalability | Architects, Tech Leads       |
| **[DOMAIN-MODEL.md](DOMAIN-MODEL.md)**                           | Domain           | Business concepts, ubiquitous language, domain rules | Domain Experts, Developers   |
| **[IMPLEMENTATION.md](IMPLEMENTATION.md)**                       | Technical        | Detailed implementation plans, acceptance criteria   | Development Teams            |
| **[TESTING.md](TESTING.md)**                                     | Testing Overview | Basic testing architecture and strategies            | QA Engineers, Developers     |
| **[TASKS.md](TASKS.md)**                                         | Operational      | Current sprint breakdown, task tracking              | Individual Contributors      |
| **[MULTI_CRITERIA_EVALUATION.md](MULTI_CRITERIA_EVALUATION.md)** | Feature Guide    | Multi-criteria evaluation system guide               | All Users                    |
| **[API_REFERENCE.md](API_REFERENCE.md)**                         | API Reference    | Complete API documentation with examples             | Developers, Integrators      |
| **[CONFIGURATION.md](CONFIGURATION.md)**                         | Configuration    | System configuration and environment setup           | DevOps, Administrators       |

## 🔧 Development Documentation

| Document                                                                                               | Purpose                                             | Audience               |
| ------------------------------------------------------------------------------------------------------ | --------------------------------------------------- | ---------------------- |
| **[development/CODE_PLAN.md](development/CODE_PLAN.md)**                                               | Development planning, roadmap, and coding standards | Development Teams      |
| **[development/BEDROCK_INTEGRATION.md](development/BEDROCK_INTEGRATION.md)**                           | AWS Bedrock integration implementation details      | Developers, Architects |
| **[development/CONSISTENCY_IMPROVEMENTS_SUMMARY.md](development/CONSISTENCY_IMPROVEMENTS_SUMMARY.md)** | Provider consistency improvements and refactoring   | Development Teams      |

## 🧪 Testing Documentation

| Document                                                                     | Purpose                                         | Audience                    |
| ---------------------------------------------------------------------------- | ----------------------------------------------- | --------------------------- |
| **[testing/TEST_SUITE_SUMMARY.md](testing/TEST_SUITE_SUMMARY.md)**           | Complete test suite overview with 168+ tests    | QA Engineers, Developers    |
| **[testing/TEST_COVERAGE_MATRIX.md](testing/TEST_COVERAGE_MATRIX.md)**       | Detailed test coverage matrix and quality gates | QA Engineers, Test Managers |
| **[testing/TEST_SCENARIOS_DETAILED.md](testing/TEST_SCENARIOS_DETAILED.md)** | Detailed test scenarios with assertions         | QA Engineers, Developers    |
| **[testing/TEST_EXECUTION_GUIDE.md](testing/TEST_EXECUTION_GUIDE.md)**       | Test execution procedures and troubleshooting   | All Development Roles       |

## 🧭 Quick Navigation

### For New Team Members

1. Start with **[STRATEGY.md](STRATEGY.md)** - Understand the "why"
2. Review **[MULTI_CRITERIA_EVALUATION.md](MULTI_CRITERIA_EVALUATION.md)** - Learn the core feature
3. Study **[DOMAIN-MODEL.md](DOMAIN-MODEL.md)** - Learn the business language
4. Check **[ARCHITECTURE.md](ARCHITECTURE.md)** - Grasp the system design
5. Dive into **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - See how it's built

### For Development Work

1. Check **[TASKS.md](TASKS.md)** - Current priorities and status
2. Reference **[API_REFERENCE.md](API_REFERENCE.md)** - API usage and examples
3. Review **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Technical details
4. Validate against **[DOMAIN-MODEL.md](DOMAIN-MODEL.md)** - Business correctness
5. Update docs after changes - Keep synchronized

### For System Administration

1. Review **[CONFIGURATION.md](CONFIGURATION.md)** - Complete configuration guide
2. Check **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and deployment
3. Reference **[TESTING.md](TESTING.md)** - Test suite and validation

### For Architecture Decisions

1. Review **[ARCHITECTURE.md](ARCHITECTURE.md)** - Current design patterns
2. Consider **[STRATEGY.md](STRATEGY.md)** - Business alignment
3. Validate **[DOMAIN-MODEL.md](DOMAIN-MODEL.md)** - Domain fit
4. Update **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Implementation impact

## 🏗️ Project Architecture

The project implements Domain-Driven Design (DDD) with clean architecture principles:

```
src/llm_judge/                          # Main application package
├── domain/                             # 🧠 Business Logic Layer
│   ├── evaluation/                     # Core evaluation domain
│   │   ├── criteria.py                 # Multi-criteria evaluation system
│   │   ├── custom_criteria.py          # Custom criteria definition
│   │   └── weight_config.py            # Weight configuration system
│   ├── persistence/                    # Data persistence domain
│   │   ├── models.py                   # Persistence domain models
│   │   └── interfaces.py               # Repository interfaces
│   └── models/                         # Domain models and value objects
├── application/                        # 🔧 Application Service Layer
│   ├── services/
│   │   └── llm_judge_service.py       # Main evaluation service
│   └── use_cases/                     # Specific use case implementations
├── infrastructure/                     # 🔌 Infrastructure Layer
│   ├── clients/                        # External API integrations
│   │   ├── openai_client.py           # OpenAI API client
│   │   ├── anthropic_client.py        # Anthropic API client
│   │   └── http_client.py             # HTTP infrastructure
│   ├── config/                         # Configuration management
│   │   ├── config.py                  # Enhanced config with persistence & custom criteria
│   │   └── logging_config.py          # Logging setup
│   ├── persistence/                    # Data persistence infrastructure
│   │   ├── json_repository.py         # JSON-based data storage
│   │   ├── persistence_service.py     # Persistence orchestration
│   │   └── migration.py               # Data migration support
│   └── resilience/                     # Reliability patterns
│       ├── retry_strategies.py        # Retry logic with backoff
│       ├── fallback_manager.py        # Circuit breaker and fallback
│       ├── timeout_manager.py         # Request timeout handling
│       └── error_classification.py    # Error categorization
└── presentation/                       # 🖥️ Presentation Layer
    └── cli/                           # Enhanced CLI with data management
        └── main.py                    # Data commands & custom criteria support

tests/                                  # 🧪 Test Suite
├── unit/                              # Fast, isolated tests
│   ├── domain/                        # Domain logic tests (custom criteria & persistence)
│   ├── application/                   # Application service tests
│   └── infrastructure/                # Infrastructure component tests (persistence)
└── integration/                       # Cross-layer integration tests
```

### Layer Dependencies

```
Presentation  ──→  Application  ──→  Domain
     ↑                 ↑              ↑
     └─────────────────┴──────────────┘
                Infrastructure
```

**Key Principles:**

- **Dependency Inversion**: Dependencies point inward toward the domain
- **Domain Independence**: Domain layer has no external dependencies
- **Infrastructure Isolation**: Technical concerns isolated from business logic
- **Clean Interfaces**: Well-defined boundaries between layers

## 📋 Documentation Guidelines

### Living Documentation Principles

- **Synchronization**: Keep docs aligned with code changes
- **Incremental Updates**: Update relevant files after each code change
- **Ubiquitous Language**: Use consistent terminology from DOMAIN-MODEL.md
- **Code References**: Use `file_path:line_number` pattern for specific locations
- **Layered Updates**: Changes should cascade through documentation layers

### Documentation Maintenance

#### When Code Changes

1. **Domain Changes** → Update DOMAIN-MODEL.md, IMPLEMENTATION.md, TASKS.md
2. **Architecture Changes** → Update ARCHITECTURE.md, IMPLEMENTATION.md
3. **Feature Changes** → Update IMPLEMENTATION.md, TASKS.md
4. **Strategic Pivots** → Update STRATEGY.md, cascade downward

#### Quality Checks

- [ ] Documentation reflects current code state
- [ ] Examples use actual file paths and imports
- [ ] Terminology matches domain model
- [ ] Architecture diagrams show current structure
- [ ] Task status reflects actual completion

### Writing Style

- **Clear and Concise**: Focus on essential information
- **Actionable**: Include specific steps and examples
- **Hierarchical**: Use appropriate heading levels
- **Visual**: Include diagrams and code blocks
- **Searchable**: Use consistent keywords and cross-references

## 🔄 Documentation Synchronization Status

| Document          | Last Updated | Sync Status     | Notes                                       |
| ----------------- | ------------ | --------------- | ------------------------------------------- |
| STRATEGY.md       | Current      | ✅ Synchronized | Reflects business objectives                |
| ARCHITECTURE.md   | Updated      | ✅ Synchronized | Reflects Phase 2 DDD structure              |
| DOMAIN-MODEL.md   | Updated      | ✅ Synchronized | Enhanced with persistence & custom criteria |
| IMPLEMENTATION.md | Current      | ✅ Synchronized | Technical implementation details            |
| TASKS.md          | Updated      | ✅ Synchronized | Phase 2 complete, Phase 3 planning          |
| API_REFERENCE.md  | Updated      | ✅ Synchronized | Enhanced with new features                  |
| CONFIGURATION.md  | Updated      | ✅ Synchronized | Added persistence & custom criteria config  |
| README.md (root)  | Current      | ✅ Synchronized | Comprehensive project overview              |
| README.md (docs)  | Updated      | ✅ Synchronized | Navigation and guidelines                   |

## 🎯 Current Documentation Priorities

1. ✅ **ARCHITECTURE.md** - Updated to reflect Phase 2 DDD structure
2. ✅ **DOMAIN-MODEL.md** - Enhanced with persistence & custom criteria concepts
3. ✅ **TASKS.md** - Updated with Phase 2 completion and Phase 3 planning
4. ✅ **API_REFERENCE.md** - Enhanced with new features and data management
5. ✅ **CONFIGURATION.md** - Added persistence & custom criteria configuration
6. 📋 **Phase 3 Documentation** - Prepare for enhanced batch processing and REST API

---

_This documentation follows the AI Coding Agent Governance Framework with emphasis on living documentation that evolves with the codebase._
