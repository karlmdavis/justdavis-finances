#!/usr/bin/env python3
"""
E2E Test Helper Utilities

Helper functions for end-to-end tests to reduce boilerplate and improve consistency.
"""

import os
from pathlib import Path


def get_test_environment(data_dir: Path) -> dict[str, str]:
    """
    Get environment dictionary for E2E subprocess tests.

    Creates a copy of the current environment with FINANCES_DATA_DIR
    set to the specified test data directory.

    Args:
        data_dir: Path to temporary test data directory

    Returns:
        Environment dictionary for subprocess.run(env=...)

    Example:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            env = get_test_environment(tmpdir)
            result = subprocess.run(
                ["finances", "amazon", "match"],
                env=env,
                capture_output=True,
                text=True
            )
    """
    return {**os.environ, "FINANCES_DATA_DIR": str(data_dir)}
