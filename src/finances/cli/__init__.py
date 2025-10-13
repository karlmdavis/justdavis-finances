"""
Command Line Interface Package

Unified CLI for all financial management operations.

This package provides:
- Main CLI entry point (finances)
- Flow-based workflow system (finances flow)
- Interactive execution with user prompts
- Configuration management and environment support
- Progress reporting and error handling

Command Structure:
- finances: Main entry point with utility commands (version, config)
- finances flow: Interactive workflow system for all financial operations

Flow System Features:
- Interactive prompts with data summary and age display
- Automatic dependency management between processing nodes
- Change detection to minimize unnecessary processing
- Archive creation for data recovery
- Comprehensive execution summaries

The flow system replaced the previous command-based architecture, unifying
Amazon matching, Apple receipt processing, YNAB sync, split generation,
retirement updates, and cash flow analysis into a single guided workflow.
"""

# CLI exports will be added as commands are implemented
