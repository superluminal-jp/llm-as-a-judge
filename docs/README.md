# LLM-as-a-Judge Documentation

This directory contains comprehensive project documentation following a layered strategy from strategic vision to implementation details.

## 📚 Documentation Structure

| Document | Level | Purpose | Audience |
|----------|-------|---------|----------|
| **[STRATEGY.md](STRATEGY.md)** | Strategic | Business vision, market analysis, success metrics | Leadership, Product Strategy |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System | Technical architecture, design patterns, scalability | Architects, Tech Leads |
| **[DOMAIN-MODEL.md](DOMAIN-MODEL.md)** | Domain | Business concepts, ubiquitous language, domain rules | Domain Experts, Developers |
| **[IMPLEMENTATION.md](IMPLEMENTATION.md)** | Technical | Detailed implementation plans, acceptance criteria | Development Teams |
| **[TESTING.md](TESTING.md)** | **NEW** | **Comprehensive testing architecture, 123 tests** | **QA Engineers, Developers** |
| **[TASKS.md](TASKS.md)** | Operational | Current sprint breakdown, task tracking | Individual Contributors |

## 🧭 Quick Navigation

### For New Team Members
1. Start with **[STRATEGY.md](STRATEGY.md)** - Understand the "why"
2. Review **[DOMAIN-MODEL.md](DOMAIN-MODEL.md)** - Learn the business language
3. Study **[ARCHITECTURE.md](ARCHITECTURE.md)** - Grasp the system design
4. Dive into **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - See how it's built

### For Development Work
1. Check **[TASKS.md](TASKS.md)** - Current priorities and status
2. Reference **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Technical details
3. Validate against **[DOMAIN-MODEL.md](DOMAIN-MODEL.md)** - Business correctness
4. Update docs after changes - Keep synchronized

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
│   │   ├── config.py                  # Config loading and validation
│   │   └── logging_config.py          # Logging setup
│   └── resilience/                     # Reliability patterns
│       ├── retry_strategies.py        # Retry logic with backoff
│       ├── fallback_manager.py        # Circuit breaker and fallback
│       ├── timeout_manager.py         # Request timeout handling
│       └── error_classification.py    # Error categorization
└── presentation/                       # 🖥️ Presentation Layer
    └── cli/                           # Command-line interface

tests/                                  # 🧪 Test Suite
├── unit/                              # Fast, isolated tests
│   ├── domain/                        # Domain logic tests
│   ├── application/                   # Application service tests
│   └── infrastructure/                # Infrastructure component tests
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

| Document | Last Updated | Sync Status | Notes |
|----------|--------------|-------------|-------|
| STRATEGY.md | Current | ✅ Synchronized | Reflects business objectives |
| ARCHITECTURE.md | Needs Update | 🔄 Updating | Must reflect new DDD structure |
| DOMAIN-MODEL.md | Current | ✅ Synchronized | Domain concepts established |
| IMPLEMENTATION.md | Needs Update | 🔄 Updating | Must update file paths |
| TASKS.md | Current | ✅ Synchronized | Task tracking active |
| README.md (root) | Just Updated | ✅ Synchronized | Comprehensive project overview |
| README.md (docs) | Just Updated | ✅ Synchronized | Navigation and guidelines |

## 🎯 Current Documentation Priorities

1. **Update ARCHITECTURE.md** - Reflect DDD layered structure
2. **Update IMPLEMENTATION.md** - New file paths and import patterns
3. **Enhance DOMAIN-MODEL.md** - Add evaluation domain concepts
4. **Maintain TASKS.md** - Keep task tracking current
5. **Create Module Docs** - Add README files for major modules

---

*This documentation follows the AI Coding Agent Governance Framework with emphasis on living documentation that evolves with the codebase.*