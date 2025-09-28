# Python Package Restructure Specification

**Created:** 2025-09-21
**Status:** Proposed
**Type:** Architecture

## Overview

Transform the current script-based personal finance project into a professional,
  idiomatic Python package that follows modern Python development practices while
  maintaining all existing functionality.

## Goals

### Primary Objectives
- **Professional Structure**: Adopt standard Python package layout with proper
    module hierarchy
- **Maintainability**: Clear separation of concerns and well-defined package
    boundaries
- **Testability**: Unified testing structure with proper import handling
- **Extensibility**: Architecture that supports future growth and new financial data
    sources
- **Developer Experience**: Modern tooling and development workflow

### Secondary Objectives
- **Distribution Ready**: Package structure suitable for PyPI distribution
- **IDE Friendly**: Standard layout that works well with Python IDEs and tools
- **Documentation**: Clear API documentation and user guides
- **Configuration Management**: Centralized configuration with environment support

## Current State Analysis

### Structural Issues
- **Flat Organization**: Domain-based directories (amazon/, apple/, analysis/)
    without proper package hierarchy
- **Mixed Concerns**: Scripts, data processing, and analysis intermixed in same
    directories
- **Import Dependencies**: Tests rely on `sys.path` manipulation for imports
- **Data Commingling**: Data files stored alongside source code
- **No Entry Points**: Inconsistent command-line interfaces across modules

### Functional Strengths to Preserve
- **Robust Matching Logic**: Amazon and Apple transaction matching systems with
    high accuracy
- **Financial Precision**: Integer arithmetic preventing floating-point currency
    errors
- **Multi-phase Safety**: Generate → Review → Apply workflow for YNAB updates
- **Comprehensive Testing**: Good test coverage for core functionality

## Proposed Architecture

### Package Layout Principles

#### Source Layout (`src/finances/`)
- **Domain Packages**: Separate packages for each financial data source (e.g.,
    amazon, apple, ynab)
- **Core Utilities**: Shared business logic and utilities in dedicated core package
- **Layered Architecture**: Clear separation between CLI, business logic, and data
    access
- **Unified Interface**: Consistent APIs across different domain packages

#### Data Separation
- **External Data Directory**: All financial data stored outside source tree
- **Configurable Paths**: Data locations configurable via environment or config
    files
- **Secure Defaults**: Gitignore patterns protect sensitive financial information

#### Testing Structure
- **Centralized Tests**: All tests under single `tests/` hierarchy
- **Mirror Source Layout**: Test structure mirrors source package organization
- **Shared Fixtures**: Common test data and utilities in centralized location
- **Multiple Test Types**: Unit tests for individual components, integration tests
    for workflows

### Domain Package Design

Each financial data source (Amazon, Apple, etc.) follows consistent internal
  structure:

#### Models Layer
- Data classes representing domain concepts (orders, receipts, transactions)
- Validation logic for data integrity
- Serialization/deserialization support

#### Processing Layer
- Data extraction from external sources
- Business logic for matching and analysis
- Scoring and confidence calculation

#### Interface Layer
- CLI commands specific to the domain
- API endpoints for programmatic access
- Configuration options and validation

### Cross-Cutting Concerns

#### Configuration Management
- Environment-based configuration with fallbacks
- Validation of required settings
- Support for multiple environments (development, production)

#### Currency Handling
- Centralized currency utilities using integer arithmetic
- Consistent conversion between milliunits, cents, and display formats
- Precision preservation across all calculations

#### Data Access Patterns
- Consistent interfaces for reading external data
- Caching strategies for expensive operations
- Error handling and retry logic

## Implementation Strategy

### Migration Approach
The restructure follows an incremental approach to minimize disruption:

1. **Foundation**: Establish new package structure and core utilities
2. **Domain Migration**: Move existing functionality into domain packages
3. **Interface Unification**: Create consistent CLI and API interfaces
4. **Testing Consolidation**: Migrate and enhance test suites
5. **Documentation**: Create comprehensive documentation

### Compatibility Considerations
- **Backward Compatibility**: Existing scripts continue working during transition
- **Data Preservation**: All existing data files remain accessible
- **Configuration Migration**: Smooth transition for existing configurations

### Quality Assurance
- **Code Formatting**: Automated formatting with black
- **Linting**: Static analysis with ruff
- **Type Checking**: Optional type hints with mypy validation
- **Test Coverage**: Maintain or improve existing test coverage

## Example Package Structure

```
src/finances/
├── core/                    # Shared business logic
│   ├── models.py           # Common data models
│   ├── currency.py         # Currency utilities
│   └── config.py           # Configuration management
├── amazon/                 # Amazon transaction processing
│   ├── models.py           # Amazon-specific models
│   ├── extractor.py        # Data extraction
│   └── matcher.py          # Transaction matching
├── apple/                  # Apple receipt processing
│   ├── models.py           # Apple-specific models
│   ├── parser.py           # Receipt parsing
│   └── matcher.py          # Transaction matching
├── ynab/                   # YNAB integration
│   ├── client.py           # YNAB API integration
│   └── updater.py          # Transaction updates
├── analysis/               # Financial analysis tools
│   ├── cash_flow.py        # Cash flow analysis
│   └── dashboard.py        # Report generation
└── cli/                    # Command-line interfaces
    ├── main.py             # Main CLI entry point
    └── commands/           # Domain-specific commands
```

## Benefits

### Developer Experience
- **Standard Structure**: Familiar layout for Python developers
- **Better IDE Support**: Proper imports and navigation
- **Modern Tooling**: Integration with contemporary Python development tools
- **Clear Dependencies**: Explicit package boundaries and import relationships

### Operational Benefits
- **Easier Deployment**: Standard package installation and distribution
- **Configuration Management**: Environment-based configuration
- **Error Handling**: Consistent error reporting and logging
- **Performance Monitoring**: Structured logging and metrics collection

### Future Extensibility
- **New Data Sources**: Easy addition of new financial institutions
- **API Development**: Foundation for web API or service interfaces
- **Advanced Analytics**: Modular architecture supports complex analysis features
- **Integration Points**: Clear interfaces for external system integration

## Success Criteria

- [ ] All existing functionality preserved and accessible
- [ ] Test suite passes with improved coverage
- [ ] Package installable via pip/uv
- [ ] Clear CLI interface with help documentation
- [ ] Development workflow includes linting, formatting, and type checking
- [ ] Data remains secure with proper gitignore patterns
- [ ] Documentation covers installation, usage, and API reference

## Considerations

### Security
- Financial data must remain protected throughout restructure
- Environment variable handling for sensitive configuration
- Audit trail preservation for YNAB transaction updates

### Performance
- Maintain existing performance characteristics
- Consider caching strategies for expensive operations
- Optimize import times for CLI responsiveness

### Compatibility
- Smooth migration path for existing users
- Backward compatibility during transition period
- Clear communication about changes and benefits
