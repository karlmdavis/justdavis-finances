"""
Command Line Interface Package

Unified CLI for all financial management operations.

This package provides:
- Main CLI entry point with subcommands
- Domain-specific command groups (Amazon, Apple, YNAB, Analysis)
- Consistent argument parsing and help documentation
- Configuration management and environment support
- Progress reporting and error handling

Command Structure:
- finances: Main entry point
- finances amazon: Amazon transaction matching commands
- finances apple: Apple receipt processing commands
- finances ynab: YNAB integration commands
- finances analysis: Financial analysis commands

Features:
- Rich help documentation
- Environment-based configuration
- Verbose and quiet output modes
- Dry-run support where applicable
- Progress bars for long operations
"""

# CLI exports will be added as commands are implemented