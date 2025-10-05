#!/usr/bin/env python3
"""
End-to-end tests for the finances package.

These tests execute actual CLI commands via subprocess to validate complete
workflows from user perspective. They use synthetic test data to ensure no
PII leakage and no mutations to real financial accounts.
"""
