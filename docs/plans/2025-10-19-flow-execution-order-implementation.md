# Flow Execution Order Fix - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix flow engine to execute nodes in correct dependency order with automatic archiving of changed data.

**Architecture:** Add type-safe OutputInfo abstraction for node output inspection, rewrite flow engine with topological sort and sequential prompt-validate-execute, implement SHA-256 hash-based archiving with pre/post snapshots.

**Tech Stack:** Python 3.13, pytest, mypy strict mode, pathlib, hashlib, shutil

**Related:** Issue #29, Design doc at `dev/plans/2025-10-19-flow-execution-order-fix.md`

---

## Task 1: Add OutputFile and OutputInfo Base Classes

**Files:**
- Modify: `src/finances/core/flow_node.py:9` (add imports after existing imports)
- Modify: `src/finances/core/flow_node.py:19` (add classes before FlowNode)

**Background:** Create type-safe abstractions for node output information.

**Step 1: Add OutputFile dataclass**

Add to `src/finances/core/flow_node.py` after line 9 (after imports):

```python
from abc import ABC, abstractmethod
from pathlib import Path
```

Add after line 19 (before FlowNode class):

```python
@dataclass(frozen=True)
class OutputFile:
    """Information about a single output file from a flow node."""
    path: Path
    record_count: int
```

**Step 2: Add OutputInfo abstract class**

Add after OutputFile:

```python
class OutputInfo(ABC):
    """Information about a flow node's output data."""

    @abstractmethod
    def is_data_ready(self) -> bool:
        """Returns True if output data is complete enough for dependencies to use."""
        pass

    @abstractmethod
    def get_output_files(self) -> list[OutputFile]:
        """Returns list of output files with their record counts."""
        pass
```

**Step 3: Run mypy to verify types**

```bash
uv run mypy src/finances/core/flow_node.py
```

Expected: PASS (no type errors)

**Step 4: Commit**

```bash
git add src/finances/core/flow_node.py
git commit -m "feat: add OutputFile and OutputInfo base classes"
```

---

## Task 2: Add get_output_info Abstract Method to FlowNode

**Files:**
- Modify: `src/finances/core/flow_node.py:150` (add after execute method)

**Background:** FlowNode interface must require get_output_info implementation.

**Step 1: Add abstract method to FlowNode**

Add to `src/finances/core/flow_node.py` after the `execute` method (around line 150):

```python
@abstractmethod
def get_output_info(self) -> OutputInfo:
    """
    Get information about this node's output data.

    Returns OutputInfo with methods to check data readiness and list output files.
    Used by flow engine for dependency validation and status display.

    Returns:
        OutputInfo instance with node's current output state
    """
    pass
```

**Step 2: Run mypy to verify abstract method**

```bash
uv run mypy src/finances/core/flow_node.py
```

Expected: PASS

**Step 3: Run mypy on entire codebase to see what breaks**

```bash
uv run mypy src/finances/ 2>&1 | head -20
```

Expected: FAIL - all FlowNode subclasses missing get_output_info

**Step 4: Commit**

```bash
git add src/finances/core/flow_node.py
git commit -m "feat: add get_output_info abstract method to FlowNode"
```

---

## Task 3: Implement OutputInfo for AppleEmailFetchNode

**Files:**
- Modify: `src/finances/apple/flow.py:14` (add after imports)
- Modify: `src/finances/apple/flow.py:24` (add method to AppleEmailFetchFlowNode)
- Create: `tests/unit/test_apple/test_apple_flow_output_info.py`

**Background:** First node implementation - establishes pattern for others.

**Step 1: Write test for AppleEmailOutputInfo**

Create `tests/unit/test_apple/test_apple_flow_output_info.py`:

```python
"""Tests for Apple flow node OutputInfo implementations."""

import tempfile
from pathlib import Path

import pytest

from finances.apple.flow import AppleEmailFetchFlowNode


def test_apple_email_output_info_is_data_ready_returns_false_when_no_files():
    """Verify is_data_ready returns False when no .eml files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        node = AppleEmailFetchFlowNode(data_dir)

        info = node.get_output_info()

        assert info.is_data_ready() is False


def test_apple_email_output_info_is_data_ready_returns_true_with_eml_files():
    """Verify is_data_ready returns True when .eml files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        emails_dir = data_dir / "apple" / "emails"
        emails_dir.mkdir(parents=True)

        # Create .eml file
        (emails_dir / "test_email.eml").write_text("From: test@apple.com")

        node = AppleEmailFetchFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_apple_email_output_info_get_output_files_returns_empty_when_no_dir():
    """Verify get_output_files returns empty list when directory doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        node = AppleEmailFetchFlowNode(data_dir)

        info = node.get_output_info()
        files = info.get_output_files()

        assert files == []


def test_apple_email_output_info_get_output_files_returns_eml_files():
    """Verify get_output_files returns all .eml files with record counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        emails_dir = data_dir / "apple" / "emails"
        emails_dir.mkdir(parents=True)

        # Create .eml files
        (emails_dir / "email1.eml").write_text("From: test1@apple.com")
        (emails_dir / "email2.eml").write_text("From: test2@apple.com")

        node = AppleEmailFetchFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 2
        assert all(f.path.suffix == ".eml" for f in files)
        assert all(f.record_count == 1 for f in files)
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_apple/test_apple_flow_output_info.py::test_apple_email_output_info_is_data_ready_returns_false_when_no_files -v
```

Expected: FAIL - get_output_info not implemented

**Step 3: Implement AppleEmailOutputInfo class**

Add to `src/finances/apple/flow.py` after imports (around line 11):

```python
from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary, OutputFile, OutputInfo
```

Add before AppleEmailFetchFlowNode class:

```python
class AppleEmailOutputInfo(OutputInfo):
    """Output information for Apple email fetch node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 .eml file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.eml"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return list of .eml files (1 record per file)."""
        if not self.output_dir.exists():
            return []

        files = []
        for eml_file in self.output_dir.glob("*.eml"):
            files.append(OutputFile(path=eml_file, record_count=1))
        return files
```

**Step 4: Add get_output_info method to AppleEmailFetchFlowNode**

Add to AppleEmailFetchFlowNode class (after `__init__` method):

```python
def get_output_info(self) -> OutputInfo:
    """Get output information for email fetch node."""
    return AppleEmailOutputInfo(self.data_dir / "apple" / "emails")
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_apple/test_apple_flow_output_info.py -v
```

Expected: PASS (all 4 tests)

**Step 6: Commit**

```bash
git add tests/unit/test_apple/test_apple_flow_output_info.py src/finances/apple/flow.py
git commit -m "feat: implement OutputInfo for AppleEmailFetchNode"
```

---

## Task 4: Implement OutputInfo for AppleReceiptParsingNode

**Files:**
- Modify: `src/finances/apple/flow.py:90` (add OutputInfo class before node)
- Modify: `src/finances/apple/flow.py:104` (add method to node)
- Modify: `tests/unit/test_apple/test_apple_flow_output_info.py` (add tests)

**Background:** Receipt parsing produces .html, .eml, .txt files but dependencies only consume .html.

**Step 1: Write tests for AppleReceiptOutputInfo**

Add to `tests/unit/test_apple/test_apple_flow_output_info.py`:

```python
from finances.apple.flow import AppleReceiptParsingFlowNode


def test_apple_receipt_output_info_is_data_ready_returns_true_with_html_files():
    """Verify is_data_ready returns True when .html files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        exports_dir = data_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)

        # Create .html file (what dependencies consume)
        (exports_dir / "receipt.html").write_text("<html>Receipt</html>")

        node = AppleReceiptParsingFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_apple_receipt_output_info_is_data_ready_returns_false_without_html():
    """Verify is_data_ready returns False even if other files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        exports_dir = data_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)

        # Create .eml and .txt but no .html
        (exports_dir / "receipt.eml").write_text("Email content")
        (exports_dir / "receipt.txt").write_text("Text content")

        node = AppleReceiptParsingFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is False


def test_apple_receipt_output_info_get_output_files_returns_all_types():
    """Verify get_output_files returns all file types (.html, .eml, .txt)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        exports_dir = data_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)

        # Create all file types
        (exports_dir / "receipt.html").write_text("<html>Receipt</html>")
        (exports_dir / "receipt.eml").write_text("Email content")
        (exports_dir / "receipt.txt").write_text("Text content")

        node = AppleReceiptParsingFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 3
        suffixes = {f.path.suffix for f in files}
        assert suffixes == {".html", ".eml", ".txt"}
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_apple/test_apple_flow_output_info.py::test_apple_receipt_output_info_is_data_ready_returns_true_with_html_files -v
```

Expected: FAIL - get_output_info not implemented

**Step 3: Implement AppleReceiptOutputInfo class**

Add to `src/finances/apple/flow.py` before AppleReceiptParsingFlowNode class:

```python
class AppleReceiptOutputInfo(OutputInfo):
    """Output information for Apple receipt parsing node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 .html file exists (what dependencies consume)."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.html"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return all output files (.eml, .html, .txt) with counts."""
        if not self.output_dir.exists():
            return []

        files = []

        # Add .html files (what dependencies use)
        for html_file in self.output_dir.glob("*.html"):
            files.append(OutputFile(path=html_file, record_count=1))

        # Add .eml files
        for eml_file in self.output_dir.glob("*.eml"):
            files.append(OutputFile(path=eml_file, record_count=1))

        # Add text files
        for txt_file in self.output_dir.glob("*.txt"):
            files.append(OutputFile(path=txt_file, record_count=1))

        return files
```

**Step 4: Add get_output_info method to AppleReceiptParsingFlowNode**

Add to AppleReceiptParsingFlowNode class (after `__init__` method):

```python
def get_output_info(self) -> OutputInfo:
    """Get output information for receipt parsing node."""
    return AppleReceiptOutputInfo(self.data_dir / "apple" / "exports")
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_apple/test_apple_flow_output_info.py -v
```

Expected: PASS (all 7 tests)

**Step 6: Commit**

```bash
git add tests/unit/test_apple/test_apple_flow_output_info.py src/finances/apple/flow.py
git commit -m "feat: implement OutputInfo for AppleReceiptParsingNode"
```

---

## Task 5: Implement OutputInfo for AppleMatchingFlowNode

**Files:**
- Modify: `src/finances/apple/flow.py:198` (add OutputInfo class before node)
- Modify: `src/finances/apple/flow.py:212` (add method to node)
- Modify: `tests/unit/test_apple/test_apple_flow_output_info.py` (add tests)

**Background:** Apple matching produces JSON match results.

**Step 1: Write tests for AppleMatchingOutputInfo**

Add to `tests/unit/test_apple/test_apple_flow_output_info.py`:

```python
from finances.apple.flow import AppleMatchingFlowNode


def test_apple_matching_output_info_is_data_ready_returns_true_with_json_files():
    """Verify is_data_ready returns True when .json match files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        matches_dir = data_dir / "apple" / "transaction_matches"
        matches_dir.mkdir(parents=True)

        # Create match result JSON
        (matches_dir / "2024-10-19_results.json").write_text('{"matches": []}')

        node = AppleMatchingFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_apple_matching_output_info_get_output_files_returns_json_with_match_counts():
    """Verify get_output_files returns .json files with match counts from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        matches_dir = data_dir / "apple" / "transaction_matches"
        matches_dir.mkdir(parents=True)

        # Create match result JSON with matches
        import json
        match_data = {"matches": [{"tx_id": "1"}, {"tx_id": "2"}, {"tx_id": "3"}]}
        (matches_dir / "2024-10-19_results.json").write_text(json.dumps(match_data))

        node = AppleMatchingFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 1
        assert files[0].path.suffix == ".json"
        assert files[0].record_count == 3  # 3 matches
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_apple/test_apple_flow_output_info.py::test_apple_matching_output_info_is_data_ready_returns_true_with_json_files -v
```

Expected: FAIL - get_output_info not implemented

**Step 3: Implement AppleMatchingOutputInfo class**

Add to `src/finances/apple/flow.py` before AppleMatchingFlowNode class:

```python
class AppleMatchingOutputInfo(OutputInfo):
    """Output information for Apple matching node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 .json match result file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.json"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return .json match result files with match counts."""
        if not self.output_dir.exists():
            return []

        from ..core.json_utils import read_json

        files = []
        for json_file in self.output_dir.glob("*.json"):
            try:
                data = read_json(json_file)
                match_count = len(data.get("matches", []))
                files.append(OutputFile(path=json_file, record_count=match_count))
            except Exception:
                # If JSON is malformed, count as 0 records
                files.append(OutputFile(path=json_file, record_count=0))

        return files
```

**Step 4: Add get_output_info method to AppleMatchingFlowNode**

Add to AppleMatchingFlowNode class (after `__init__` method):

```python
def get_output_info(self) -> OutputInfo:
    """Get output information for matching node."""
    return AppleMatchingOutputInfo(self.data_dir / "apple" / "transaction_matches")
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_apple/test_apple_flow_output_info.py -v
```

Expected: PASS (all 9 tests)

**Step 6: Commit**

```bash
git add tests/unit/test_apple/test_apple_flow_output_info.py src/finances/apple/flow.py
git commit -m "feat: implement OutputInfo for AppleMatchingFlowNode"
```

---

## Task 6: Implement OutputInfo for Amazon Nodes (Unzip and Matching)

**Files:**
- Create: `tests/unit/test_amazon/test_amazon_flow_output_info.py`
- Modify: `src/finances/amazon/flow.py:46,120` (add OutputInfo classes and methods)

**Background:** Amazon has 2 nodes with output: unzip (produces CSVs) and matching (produces JSON).

**Step 1: Write tests for Amazon OutputInfo implementations**

Create `tests/unit/test_amazon/test_amazon_flow_output_info.py`:

```python
"""Tests for Amazon flow node OutputInfo implementations."""

import json
import tempfile
from pathlib import Path

import pytest

from finances.amazon.flow import AmazonMatchingFlowNode, AmazonUnzipFlowNode


def test_amazon_unzip_output_info_is_data_ready_returns_true_with_csv_files():
    """Verify is_data_ready returns True when CSV files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        raw_dir = data_dir / "amazon" / "raw"
        raw_dir.mkdir(parents=True)

        # Create CSV file
        (raw_dir / "orders.csv").write_text("order_id,date\n123,2024-01-01")

        node = AmazonUnzipFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_amazon_unzip_output_info_get_output_files_counts_csv_rows():
    """Verify get_output_files returns CSV files with row counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        raw_dir = data_dir / "amazon" / "raw"
        raw_dir.mkdir(parents=True)

        # Create CSV with 3 data rows
        csv_content = "order_id,date\n123,2024-01-01\n456,2024-01-02\n789,2024-01-03"
        (raw_dir / "orders.csv").write_text(csv_content)

        node = AmazonUnzipFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 1
        assert files[0].path.suffix == ".csv"
        assert files[0].record_count == 3  # Data rows (excludes header)


def test_amazon_matching_output_info_is_data_ready_returns_true_with_json_files():
    """Verify is_data_ready returns True when JSON match files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        matches_dir = data_dir / "amazon" / "transaction_matches"
        matches_dir.mkdir(parents=True)

        # Create match result JSON
        (matches_dir / "2024-10-19_results.json").write_text('{"matches": []}')

        node = AmazonMatchingFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_amazon_matching_output_info_get_output_files_returns_json_with_match_counts():
    """Verify get_output_files returns .json files with match counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        matches_dir = data_dir / "amazon" / "transaction_matches"
        matches_dir.mkdir(parents=True)

        # Create match result JSON
        match_data = {"matches": [{"id": "1"}, {"id": "2"}]}
        (matches_dir / "2024-10-19_results.json").write_text(json.dumps(match_data))

        node = AmazonMatchingFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 1
        assert files[0].record_count == 2
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_amazon/test_amazon_flow_output_info.py -v
```

Expected: FAIL - get_output_info not implemented

**Step 3: Implement AmazonUnzipOutputInfo**

Add to `src/finances/amazon/flow.py` after imports:

```python
from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary, OutputFile, OutputInfo
```

Add before AmazonUnzipFlowNode class:

```python
class AmazonUnzipOutputInfo(OutputInfo):
    """Output information for Amazon unzip node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 .csv file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("**/*.csv"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return CSV files with row counts."""
        if not self.output_dir.exists():
            return []

        files = []
        for csv_file in self.output_dir.rglob("*.csv"):
            try:
                lines = csv_file.read_text().strip().split("\n")
                # Count data rows (exclude header)
                row_count = max(0, len(lines) - 1)
                files.append(OutputFile(path=csv_file, record_count=row_count))
            except Exception:
                files.append(OutputFile(path=csv_file, record_count=0))

        return files
```

**Step 4: Add get_output_info to AmazonUnzipFlowNode**

Add to AmazonUnzipFlowNode class (after `__init__`):

```python
def get_output_info(self) -> OutputInfo:
    """Get output information for unzip node."""
    return AmazonUnzipOutputInfo(self.data_dir / "amazon" / "raw")
```

**Step 5: Implement AmazonMatchingOutputInfo**

Add before AmazonMatchingFlowNode class:

```python
class AmazonMatchingOutputInfo(OutputInfo):
    """Output information for Amazon matching node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 .json match result file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.json"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return .json match result files with match counts."""
        if not self.output_dir.exists():
            return []

        from ..core.json_utils import read_json

        files = []
        for json_file in self.output_dir.glob("*.json"):
            try:
                data = read_json(json_file)
                match_count = len(data.get("matches", []))
                files.append(OutputFile(path=json_file, record_count=match_count))
            except Exception:
                files.append(OutputFile(path=json_file, record_count=0))

        return files
```

**Step 6: Add get_output_info to AmazonMatchingFlowNode**

Add to AmazonMatchingFlowNode class (after `__init__`):

```python
def get_output_info(self) -> OutputInfo:
    """Get output information for matching node."""
    return AmazonMatchingOutputInfo(self.data_dir / "amazon" / "transaction_matches")
```

**Step 7: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_amazon/test_amazon_flow_output_info.py -v
```

Expected: PASS (all 4 tests)

**Step 8: Commit**

```bash
git add tests/unit/test_amazon/test_amazon_flow_output_info.py src/finances/amazon/flow.py
git commit -m "feat: implement OutputInfo for Amazon nodes"
```

---

## Task 7: Implement OutputInfo for YNAB Nodes

**Files:**
- Create: `tests/unit/test_ynab/test_ynab_flow_output_info.py`
- Modify: `src/finances/ynab/flow.py:15,74` (add OutputInfo classes and methods)
- Modify: `src/finances/ynab/split_generation_flow.py:10,100` (add OutputInfo class and method)

**Background:** YNAB has 3 nodes with output: sync (cache), retirement_update (edits), split_generation (edits).

**Step 1: Write tests for YNAB OutputInfo implementations**

Create `tests/unit/test_ynab/test_ynab_flow_output_info.py`:

```python
"""Tests for YNAB flow node OutputInfo implementations."""

import json
import tempfile
from pathlib import Path

import pytest

from finances.ynab.flow import RetirementUpdateFlowNode, YnabSyncFlowNode
from finances.ynab.split_generation_flow import SplitGenerationFlowNode


def test_ynab_sync_output_info_is_data_ready_returns_true_with_json_cache():
    """Verify is_data_ready returns True when cache JSON files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        cache_dir = data_dir / "ynab" / "cache"
        cache_dir.mkdir(parents=True)

        # Create cache files
        (cache_dir / "transactions.json").write_text("[]")

        node = YnabSyncFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_ynab_sync_output_info_get_output_files_counts_transactions():
    """Verify get_output_files counts transactions in transactions.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        cache_dir = data_dir / "ynab" / "cache"
        cache_dir.mkdir(parents=True)

        # Create transactions.json with 5 transactions
        transactions = [{"id": f"tx{i}"} for i in range(5)]
        (cache_dir / "transactions.json").write_text(json.dumps(transactions))
        (cache_dir / "accounts.json").write_text('{"accounts": []}')

        node = YnabSyncFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        # Should have transactions.json with 5 records
        tx_file = [f for f in files if f.path.name == "transactions.json"][0]
        assert tx_file.record_count == 5


def test_retirement_update_output_info_is_data_ready_returns_true_with_edits():
    """Verify is_data_ready returns True when retirement edit files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        edits_dir = data_dir / "ynab" / "edits"
        edits_dir.mkdir(parents=True)

        # Create retirement edit file
        (edits_dir / "2024-10-19_retirement_balances.json").write_text("[]")

        node = RetirementUpdateFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_split_generation_output_info_is_data_ready_returns_true_with_splits():
    """Verify is_data_ready returns True when split edit files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        edits_dir = data_dir / "ynab" / "edits"
        edits_dir.mkdir(parents=True)

        # Create split edit file
        (edits_dir / "2024-10-19_splits.json").write_text('{"edits": []}')

        node = SplitGenerationFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_ynab/test_ynab_flow_output_info.py -v
```

Expected: FAIL - get_output_info not implemented

**Step 3: Implement YnabSyncOutputInfo**

Add to `src/finances/ynab/flow.py` after imports:

```python
from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary, OutputFile, OutputInfo
```

Add before YnabSyncFlowNode class:

```python
class YnabSyncOutputInfo(OutputInfo):
    """Output information for YNAB sync node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if cache JSON files exist."""
        if not self.output_dir.exists():
            return False

        # Check for key cache files
        required_files = ["transactions.json", "accounts.json", "categories.json"]
        return all((self.output_dir / f).exists() for f in required_files)

    def get_output_files(self) -> list[OutputFile]:
        """Return cache JSON files with record counts."""
        if not self.output_dir.exists():
            return []

        from ..core.json_utils import read_json

        files = []

        # transactions.json - count array length
        tx_file = self.output_dir / "transactions.json"
        if tx_file.exists():
            try:
                data = read_json(tx_file)
                count = len(data) if isinstance(data, list) else 0
                files.append(OutputFile(path=tx_file, record_count=count))
            except Exception:
                files.append(OutputFile(path=tx_file, record_count=0))

        # accounts.json - count accounts array
        acc_file = self.output_dir / "accounts.json"
        if acc_file.exists():
            try:
                data = read_json(acc_file)
                count = len(data.get("accounts", [])) if isinstance(data, dict) else 0
                files.append(OutputFile(path=acc_file, record_count=count))
            except Exception:
                files.append(OutputFile(path=acc_file, record_count=0))

        # categories.json - count category groups
        cat_file = self.output_dir / "categories.json"
        if cat_file.exists():
            try:
                data = read_json(cat_file)
                count = len(data.get("category_groups", [])) if isinstance(data, dict) else 0
                files.append(OutputFile(path=cat_file, record_count=count))
            except Exception:
                files.append(OutputFile(path=cat_file, record_count=0))

        return files
```

**Step 4: Add get_output_info to YnabSyncFlowNode**

Add to YnabSyncFlowNode class (after `__init__`):

```python
def get_output_info(self) -> OutputInfo:
    """Get output information for YNAB sync node."""
    return YnabSyncOutputInfo(self.data_dir / "ynab" / "cache")
```

**Step 5: Implement RetirementUpdateOutputInfo**

Add before RetirementUpdateFlowNode class:

```python
class RetirementUpdateOutputInfo(OutputInfo):
    """Output information for retirement update node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 retirement edit file exists."""
        if not self.output_dir.exists():
            return False

        # Look for retirement edit files (contain "retirement" in name)
        retirement_files = list(self.output_dir.glob("*retirement*.json"))
        return len(retirement_files) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return retirement edit JSON files with edit counts."""
        if not self.output_dir.exists():
            return []

        from ..core.json_utils import read_json

        files = []
        for json_file in self.output_dir.glob("*retirement*.json"):
            try:
                data = read_json(json_file)
                # Count edits (array or object with edits key)
                if isinstance(data, list):
                    count = len(data)
                elif isinstance(data, dict):
                    count = len(data.get("edits", []))
                else:
                    count = 0
                files.append(OutputFile(path=json_file, record_count=count))
            except Exception:
                files.append(OutputFile(path=json_file, record_count=0))

        return files
```

**Step 6: Add get_output_info to RetirementUpdateFlowNode**

Add to RetirementUpdateFlowNode class (after `__init__`):

```python
def get_output_info(self) -> OutputInfo:
    """Get output information for retirement update node."""
    return RetirementUpdateOutputInfo(self.data_dir / "ynab" / "edits")
```

**Step 7: Implement SplitGenerationOutputInfo in split_generation_flow.py**

Add to `src/finances/ynab/split_generation_flow.py` after imports:

```python
from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary, OutputFile, OutputInfo
```

Add before SplitGenerationFlowNode class:

```python
class SplitGenerationOutputInfo(OutputInfo):
    """Output information for split generation node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 split edit file exists."""
        if not self.output_dir.exists():
            return False

        # Look for split edit files (contain "split" in name or have "edits" key)
        json_files = list(self.output_dir.glob("*.json"))
        if not json_files:
            return False

        # Check if any file has split/edit content
        from ..core.json_utils import read_json

        for json_file in json_files:
            try:
                data = read_json(json_file)
                if isinstance(data, dict) and "edits" in data:
                    return True
            except Exception:
                continue

        return False

    def get_output_files(self) -> list[OutputFile]:
        """Return split edit JSON files with edit counts."""
        if not self.output_dir.exists():
            return []

        from ..core.json_utils import read_json

        files = []
        for json_file in self.output_dir.glob("*.json"):
            try:
                data = read_json(json_file)
                # Count edits in batch structure
                if isinstance(data, dict) and "edits" in data:
                    count = len(data.get("edits", []))
                    files.append(OutputFile(path=json_file, record_count=count))
            except Exception:
                # Skip files that don't match expected format
                pass

        return files
```

**Step 8: Add get_output_info to SplitGenerationFlowNode**

Add to SplitGenerationFlowNode class (after `__init__`):

```python
def get_output_info(self) -> OutputInfo:
    """Get output information for split generation node."""
    return SplitGenerationOutputInfo(self.data_dir / "ynab" / "edits")
```

**Step 9: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_ynab/test_ynab_flow_output_info.py -v
```

Expected: PASS (all 4 tests)

**Step 10: Commit**

```bash
git add tests/unit/test_ynab/test_ynab_flow_output_info.py src/finances/ynab/flow.py src/finances/ynab/split_generation_flow.py
git commit -m "feat: implement OutputInfo for YNAB nodes"
```

---

## Task 8: Implement OutputInfo for Remaining Nodes

**Files:**
- Modify: `src/finances/analysis/flow.py:10,15` (add OutputInfo for cash flow analysis)
- Modify: `src/finances/amazon/flow.py:18` (add NoOutputInfo for manual node)
- Modify: `src/finances/cli/flow.py:75` (add NoOutputInfo for ynab_apply)
- Create: `tests/unit/test_analysis/test_analysis_flow_output_info.py`
- Create: `tests/unit/test_core/test_no_output_info.py`

**Background:** Complete OutputInfo implementation for all nodes. Manual nodes return NoOutputInfo.

**Step 1: Write test for NoOutputInfo (manual nodes)**

Create `tests/unit/test_core/test_no_output_info.py`:

```python
"""Tests for NoOutputInfo (nodes with no persistent output)."""

from finances.core.flow_node import NoOutputInfo


def test_no_output_info_is_data_ready_returns_true():
    """Verify NoOutputInfo is always ready (no dependencies blocked)."""
    info = NoOutputInfo()
    assert info.is_data_ready() is True


def test_no_output_info_get_output_files_returns_empty():
    """Verify NoOutputInfo returns no files."""
    info = NoOutputInfo()
    assert info.get_output_files() == []
```

**Step 2: Implement NoOutputInfo class**

Add to `src/finances/core/flow_node.py` after OutputInfo class:

```python
class NoOutputInfo(OutputInfo):
    """Output info for nodes with no persistent output (manual steps)."""

    def is_data_ready(self) -> bool:
        """Manual nodes are always ready (no data required)."""
        return True

    def get_output_files(self) -> list[OutputFile]:
        """Manual nodes have no output files."""
        return []
```

**Step 3: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_core/test_no_output_info.py -v
```

Expected: PASS (both tests)

**Step 4: Write test for CashFlowAnalysisOutputInfo**

Create `tests/unit/test_analysis/test_analysis_flow_output_info.py`:

```python
"""Tests for Analysis flow node OutputInfo implementations."""

import tempfile
from pathlib import Path

import pytest

from finances.analysis.flow import CashFlowAnalysisFlowNode


def test_cash_flow_output_info_is_data_ready_returns_true_with_png_files():
    """Verify is_data_ready returns True when chart PNG files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        charts_dir = data_dir / "cash_flow" / "charts"
        charts_dir.mkdir(parents=True)

        # Create chart file
        (charts_dir / "dashboard.png").write_bytes(b"PNG_DATA")

        node = CashFlowAnalysisFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_cash_flow_output_info_get_output_files_returns_png_files():
    """Verify get_output_files returns PNG chart files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        charts_dir = data_dir / "cash_flow" / "charts"
        charts_dir.mkdir(parents=True)

        # Create chart files
        (charts_dir / "dashboard.png").write_bytes(b"PNG_DATA")
        (charts_dir / "trend.png").write_bytes(b"PNG_DATA")

        node = CashFlowAnalysisFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 2
        assert all(f.path.suffix == ".png" for f in files)
        assert all(f.record_count == 1 for f in files)  # 1 chart per file
```

**Step 5: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_analysis/test_analysis_flow_output_info.py -v
```

Expected: FAIL - get_output_info not implemented

**Step 6: Implement CashFlowAnalysisOutputInfo**

Add to `src/finances/analysis/flow.py` after imports:

```python
from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary, OutputFile, OutputInfo
```

Add before CashFlowAnalysisFlowNode class:

```python
class CashFlowAnalysisOutputInfo(OutputInfo):
    """Output information for cash flow analysis node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 chart file exists."""
        if not self.output_dir.exists():
            return False

        # Check for chart files (.png)
        return len(list(self.output_dir.glob("*.png"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return chart PNG files."""
        if not self.output_dir.exists():
            return []

        files = []
        for png_file in self.output_dir.glob("*.png"):
            # Each chart is 1 record
            files.append(OutputFile(path=png_file, record_count=1))

        return files
```

**Step 7: Add get_output_info to CashFlowAnalysisFlowNode**

Add to CashFlowAnalysisFlowNode class (after `__init__`):

```python
def get_output_info(self) -> OutputInfo:
    """Get output information for cash flow analysis node."""
    return CashFlowAnalysisOutputInfo(self.data_dir / "cash_flow" / "charts")
```

**Step 8: Add get_output_info to AmazonOrderHistoryRequestFlowNode**

Add to `src/finances/amazon/flow.py` imports:

```python
from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary, NoOutputInfo, OutputInfo
```

Add to AmazonOrderHistoryRequestFlowNode class (after `__init__`):

```python
def get_output_info(self) -> OutputInfo:
    """Manual step - no persistent output."""
    return NoOutputInfo()
```

**Step 9: Add get_output_info to ynab_apply function node**

Modify `src/finances/cli/flow.py` - find the `ynab_apply_executor` function and add get_output_info registration:

After the function definition, update the registration call:

```python
# Import NoOutputInfo
from ..core.flow import NoOutputInfo

# Update registration
flow_registry.register_function_node(
    name="ynab_apply",
    func=ynab_apply_executor,
    dependencies=["split_generation"],
)

# Add get_output_info to the registered node
ynab_apply_node = flow_registry.get_node("ynab_apply")
if ynab_apply_node:
    # Override with NoOutputInfo since it's a manual step
    original_get_output_info = ynab_apply_node.get_output_info
    ynab_apply_node.get_output_info = lambda: NoOutputInfo()
```

Actually, function nodes need special handling. Let me simplify - add a method to FunctionFlowNode:

Update `src/finances/core/flow.py` in FunctionFlowNode class - add get_output_info implementation:

```python
def get_output_info(self) -> OutputInfo:
    """Get output info - defaults to NoOutputInfo for function nodes."""
    return NoOutputInfo()
```

This makes all function nodes default to NoOutputInfo (which is correct for ynab_apply).

**Step 10: Run all tests to verify they pass**

```bash
uv run pytest tests/unit/test_core/test_no_output_info.py tests/unit/test_analysis/test_analysis_flow_output_info.py -v
```

Expected: PASS (all tests)

**Step 11: Run mypy on entire codebase to verify all nodes satisfy abstract method**

```bash
uv run mypy src/finances/ 2>&1 | grep "get_output_info"
```

Expected: No errors (all nodes implement get_output_info)

**Step 12: Commit**

```bash
git add tests/unit/test_core/test_no_output_info.py tests/unit/test_analysis/test_analysis_flow_output_info.py src/finances/core/flow_node.py src/finances/core/flow.py src/finances/analysis/flow.py src/finances/amazon/flow.py
git commit -m "feat: implement OutputInfo for remaining nodes

- Add NoOutputInfo for manual nodes (no persistent output)
- Implement CashFlowAnalysisOutputInfo for chart files
- Add get_output_info to AmazonOrderHistoryRequestFlowNode
- FunctionFlowNode defaults to NoOutputInfo"
```

---

## Task 9: Implement Topological Sort with Alphabetical Tie-Breaking

**Files:**
- Create: `tests/unit/test_core/test_flow_engine_topological_sort.py`
- Modify: `src/finances/core/flow_engine.py:100` (add method after __init__)

**Background:** Flow engine needs deterministic node ordering for prompting.

**Step 1: Write tests for topological sort**

Create `tests/unit/test_core/test_flow_engine_topological_sort.py`:

```python
"""Tests for flow engine topological sort."""

from finances.core.flow import FlowNode, FlowContext, FlowResult, NodeDataSummary, NoOutputInfo, OutputInfo
from finances.core.flow_engine import FlowExecutionEngine
from finances.core.flow import flow_registry


class MockNode(FlowNode):
    """Mock node for testing."""

    def __init__(self, name: str, deps: list[str] = None):
        super().__init__(name)
        if deps:
            self._dependencies = set(deps)

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        return True, []

    def execute(self, context: FlowContext) -> FlowResult:
        return FlowResult(success=True)

    def get_output_info(self) -> OutputInfo:
        return NoOutputInfo()


def test_topological_sort_returns_nodes_in_dependency_order():
    """Verify nodes sorted so dependencies come before dependents."""
    # Create nodes: B depends on A, C depends on B
    registry = flow_registry
    original_nodes = registry._nodes.copy()

    try:
        registry._nodes = {}
        registry.register_node(MockNode("node_a"))
        registry.register_node(MockNode("node_b", deps=["node_a"]))
        registry.register_node(MockNode("node_c", deps=["node_b"]))

        engine = FlowExecutionEngine()
        sorted_names = engine.topological_sort_nodes()

        # node_a must come before node_b
        assert sorted_names.index("node_a") < sorted_names.index("node_b")
        # node_b must come before node_c
        assert sorted_names.index("node_b") < sorted_names.index("node_c")
    finally:
        registry._nodes = original_nodes


def test_topological_sort_breaks_ties_alphabetically():
    """Verify nodes at same level sorted alphabetically."""
    registry = flow_registry
    original_nodes = registry._nodes.copy()

    try:
        registry._nodes = {}
        # Three nodes with no dependencies (same level)
        registry.register_node(MockNode("zebra"))
        registry.register_node(MockNode("apple"))
        registry.register_node(MockNode("banana"))

        engine = FlowExecutionEngine()
        sorted_names = engine.topological_sort_nodes()

        # Should be alphabetical: apple, banana, zebra
        assert sorted_names == ["apple", "banana", "zebra"]
    finally:
        registry._nodes = original_nodes


def test_topological_sort_handles_diamond_dependency():
    """Verify diamond dependency graph handled correctly."""
    registry = flow_registry
    original_nodes = registry._nodes.copy()

    try:
        registry._nodes = {}
        # Diamond: A -> B, A -> C, B -> D, C -> D
        registry.register_node(MockNode("node_a"))
        registry.register_node(MockNode("node_b", deps=["node_a"]))
        registry.register_node(MockNode("node_c", deps=["node_a"]))
        registry.register_node(MockNode("node_d", deps=["node_b", "node_c"]))

        engine = FlowExecutionEngine()
        sorted_names = engine.topological_sort_nodes()

        # node_a must be first
        assert sorted_names[0] == "node_a"
        # node_b and node_c must come before node_d
        assert sorted_names.index("node_b") < sorted_names.index("node_d")
        assert sorted_names.index("node_c") < sorted_names.index("node_d")
        # node_b and node_c should be alphabetical
        assert sorted_names.index("node_b") < sorted_names.index("node_c")
    finally:
        registry._nodes = original_nodes
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_core/test_flow_engine_topological_sort.py::test_topological_sort_returns_nodes_in_dependency_order -v
```

Expected: FAIL - method doesn't exist

**Step 3: Implement topological_sort_nodes method**

Add to `src/finances/core/flow_engine.py` after `__init__` method:

```python
def topological_sort_nodes(self) -> list[str]:
    """
    Sort nodes by dependencies with alphabetical tie-breaking.

    Uses Kahn's algorithm for topological sort. When multiple nodes
    have zero in-degree (no remaining dependencies), they are processed
    in alphabetical order to ensure deterministic execution.

    Returns:
        Ordered list of node names (dependencies always before dependents)

    Raises:
        ValueError: If circular dependencies detected
    """
    from collections import deque

    # Build in-degree map and adjacency list
    in_degree = {name: 0 for name in self.registry.get_all_nodes()}
    adjacency = {name: [] for name in self.registry.get_all_nodes()}

    for name, node in self.registry.get_all_nodes().items():
        for dep_name in node.dependencies:
            adjacency[dep_name].append(name)
            in_degree[name] += 1

    # Start with nodes that have no dependencies (in-degree 0)
    # Sort alphabetically for deterministic ordering
    zero_in_degree = sorted([name for name, degree in in_degree.items() if degree == 0])
    queue = deque(zero_in_degree)
    result = []

    while queue:
        # Process node
        current = queue.popleft()
        result.append(current)

        # Reduce in-degree for dependent nodes
        next_batch = []
        for dependent in adjacency[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                next_batch.append(dependent)

        # Add newly zero in-degree nodes in alphabetical order
        next_batch.sort()
        queue.extend(next_batch)

    # Check for cycles
    if len(result) != len(self.registry.get_all_nodes()):
        raise ValueError("Circular dependency detected in flow graph")

    return result
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_core/test_flow_engine_topological_sort.py -v
```

Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add tests/unit/test_core/test_flow_engine_topological_sort.py src/finances/core/flow_engine.py
git commit -m "feat: implement topological sort with alphabetical tie-breaking"
```

---

## Task 10: Implement Directory Hash Computation

**Files:**
- Create: `tests/unit/test_core/test_flow_engine_archiving.py`
- Modify: `src/finances/core/flow_engine.py:180` (add method)

**Background:** Need SHA-256 hash to detect if node output changed.

**Step 1: Write tests for compute_directory_hash**

Create `tests/unit/test_core/test_flow_engine_archiving.py`:

```python
"""Tests for flow engine archiving functionality."""

import tempfile
from pathlib import Path

import pytest

from finances.core.flow_engine import FlowExecutionEngine


def test_compute_directory_hash_returns_same_hash_for_identical_content():
    """Verify identical directory contents produce identical hashes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir1 = Path(tmpdir) / "dir1"
        dir2 = Path(tmpdir) / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create identical files in both directories
        (dir1 / "file.txt").write_text("content")
        (dir2 / "file.txt").write_text("content")

        engine = FlowExecutionEngine()
        hash1 = engine.compute_directory_hash(dir1)
        hash2 = engine.compute_directory_hash(dir2)

        assert hash1 == hash2


def test_compute_directory_hash_returns_different_hash_for_different_content():
    """Verify different directory contents produce different hashes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir1 = Path(tmpdir) / "dir1"
        dir2 = Path(tmpdir) / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create different content
        (dir1 / "file.txt").write_text("content1")
        (dir2 / "file.txt").write_text("content2")

        engine = FlowExecutionEngine()
        hash1 = engine.compute_directory_hash(dir1)
        hash2 = engine.compute_directory_hash(dir2)

        assert hash1 != hash2


def test_compute_directory_hash_ignores_archive_subdirectory():
    """Verify archive/ subdirectory is excluded from hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir1 = Path(tmpdir) / "dir1"
        dir2 = Path(tmpdir) / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create identical main files
        (dir1 / "file.txt").write_text("content")
        (dir2 / "file.txt").write_text("content")

        # Create different archive subdirectories (should be ignored)
        archive1 = dir1 / "archive"
        archive2 = dir2 / "archive"
        archive1.mkdir()
        archive2.mkdir()
        (archive1 / "old.txt").write_text("old_data_1")
        (archive2 / "old.txt").write_text("old_data_2")

        engine = FlowExecutionEngine()
        hash1 = engine.compute_directory_hash(dir1)
        hash2 = engine.compute_directory_hash(dir2)

        # Hashes should be identical (archive ignored)
        assert hash1 == hash2


def test_compute_directory_hash_returns_empty_string_for_nonexistent_directory():
    """Verify empty string returned for nonexistent directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = Path(tmpdir) / "doesnt_exist"

        engine = FlowExecutionEngine()
        hash_result = engine.compute_directory_hash(nonexistent)

        assert hash_result == ""
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_core/test_flow_engine_archiving.py::test_compute_directory_hash_returns_same_hash_for_identical_content -v
```

Expected: FAIL - method doesn't exist

**Step 3: Implement compute_directory_hash method**

Add to `src/finances/core/flow_engine.py` after `topological_sort_nodes`:

```python
def compute_directory_hash(self, directory: Path) -> str:
    """
    Compute SHA-256 hash of all files in directory.

    Hash includes both file paths (relative to directory) and file contents
    for comprehensive change detection. Ignores 'archive' subdirectory to
    avoid recursion.

    Args:
        directory: Path to directory to hash

    Returns:
        Hex digest of SHA-256 hash, or empty string if directory doesn't exist
    """
    import hashlib

    if not directory.exists():
        return ""

    hash_obj = hashlib.sha256()

    # Sort files for deterministic ordering
    for file_path in sorted(directory.rglob("*")):
        if file_path.is_file() and "archive" not in file_path.parts:
            # Hash relative path
            rel_path = file_path.relative_to(directory)
            hash_obj.update(str(rel_path).encode())

            # Hash file contents
            hash_obj.update(file_path.read_bytes())

    return hash_obj.hexdigest()
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_core/test_flow_engine_archiving.py -v
```

Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add tests/unit/test_core/test_flow_engine_archiving.py src/finances/core/flow_engine.py
git commit -m "feat: implement directory hash computation for change detection"
```

---

## Task 11: Implement Archive Functions

**Files:**
- Modify: `tests/unit/test_core/test_flow_engine_archiving.py` (add tests)
- Modify: `src/finances/core/flow_engine.py:230` (add methods)

**Background:** Create pre/post archives when data changes.

**Step 1: Write tests for archive functions**

Add to `tests/unit/test_core/test_flow_engine_archiving.py`:

```python
from finances.core.flow import FlowContext, FlowNode, NoOutputInfo, OutputInfo
from datetime import datetime


class MockNodeWithOutput(FlowNode):
    """Mock node with output directory."""

    def __init__(self, output_dir: Path):
        super().__init__("mock_node")
        self.output_dir = output_dir

    def get_output_dir(self) -> Path:
        return self.output_dir

    def check_changes(self, context):
        return True, []

    def execute(self, context):
        from finances.core.flow import FlowResult
        return FlowResult(success=True)

    def get_output_info(self) -> OutputInfo:
        return NoOutputInfo()


def test_archive_existing_data_creates_pre_archive():
    """Verify archive_existing_data creates timestamped pre-archive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        # Create existing data
        (output_dir / "file1.txt").write_text("data1")
        (output_dir / "file2.txt").write_text("data2")

        node = MockNodeWithOutput(output_dir)
        context = FlowContext(start_time=datetime.now())

        engine = FlowExecutionEngine()
        engine.archive_existing_data(node, output_dir, context)

        # Verify archive created
        archive_dir = output_dir / "archive"
        assert archive_dir.exists()

        pre_archives = list(archive_dir.glob("*_pre"))
        assert len(pre_archives) == 1

        # Verify archived files
        pre_archive = pre_archives[0]
        assert (pre_archive / "file1.txt").exists()
        assert (pre_archive / "file2.txt").exists()
        assert (pre_archive / "file1.txt").read_text() == "data1"


def test_archive_existing_data_excludes_archive_subdirectory():
    """Verify archive/ subdirectory not included in archive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        # Create data and existing archive
        (output_dir / "file.txt").write_text("data")
        archive_dir = output_dir / "archive"
        archive_dir.mkdir()
        (archive_dir / "old.txt").write_text("old")

        node = MockNodeWithOutput(output_dir)
        context = FlowContext(start_time=datetime.now())

        engine = FlowExecutionEngine()
        engine.archive_existing_data(node, output_dir, context)

        # Verify new archive doesn't contain old archive
        pre_archives = list(archive_dir.glob("*_pre"))
        assert len(pre_archives) == 1

        pre_archive = pre_archives[0]
        assert (pre_archive / "file.txt").exists()
        assert not (pre_archive / "archive").exists()


def test_archive_new_data_creates_post_archive():
    """Verify archive_new_data creates timestamped post-archive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        # Create new data
        (output_dir / "result.json").write_text('{"result": "success"}')

        node = MockNodeWithOutput(output_dir)
        context = FlowContext(start_time=datetime.now())

        engine = FlowExecutionEngine()
        engine.archive_new_data(node, output_dir, context)

        # Verify archive created
        archive_dir = output_dir / "archive"
        assert archive_dir.exists()

        post_archives = list(archive_dir.glob("*_post"))
        assert len(post_archives) == 1

        # Verify archived file
        post_archive = post_archives[0]
        assert (post_archive / "result.json").exists()


def test_archive_existing_data_stops_flow_on_error():
    """Verify archive failure raises exception."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        # Create read-only directory (simulates permission error)
        (output_dir / "file.txt").write_text("data")
        output_dir.chmod(0o444)  # Read-only

        node = MockNodeWithOutput(output_dir)
        context = FlowContext(start_time=datetime.now())

        engine = FlowExecutionEngine()

        # Should raise exception on archive failure
        with pytest.raises(SystemExit):
            engine.archive_existing_data(node, output_dir, context)

        # Cleanup
        output_dir.chmod(0o755)
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_core/test_flow_engine_archiving.py::test_archive_existing_data_creates_pre_archive -v
```

Expected: FAIL - methods don't exist

**Step 3: Implement archive_existing_data method**

Add to `src/finances/core/flow_engine.py` after `compute_directory_hash`:

```python
def archive_existing_data(
    self, node: FlowNode, output_dir: Path, context: FlowContext
) -> None:
    """
    Archive existing data before node execution.

    Creates timestamped backup in output_dir/archive/ subdirectory.
    Exits flow on failure (archiving is critical).

    Args:
        node: Flow node whose output is being archived
        output_dir: Path to node's output directory
        context: Flow execution context
    """
    import shutil
    from datetime import datetime

    try:
        archive_dir = output_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_path = archive_dir / f"{timestamp}_pre"

        # Copy all files except archive subdirectory
        shutil.copytree(
            output_dir, archive_path, ignore=shutil.ignore_patterns("archive")
        )

        context.archive_manifest[f"{node.name}_pre"] = archive_path
        logger.info(f"Archived existing data for {node.name} to {archive_path.name}")

    except Exception as e:
        print(f"\nERROR: Failed to archive existing data for '{node.name}'")
        print(f"  Reason: {e}")
        print(f"  Cannot proceed without backup - flow stopped")
        import sys
        sys.exit(1)
```

**Step 4: Implement archive_new_data method**

Add after `archive_existing_data`:

```python
def archive_new_data(
    self, node: FlowNode, output_dir: Path, context: FlowContext
) -> None:
    """
    Archive new data after node execution.

    Creates timestamped audit trail in output_dir/archive/ subdirectory.
    Exits flow on failure (archiving is critical).

    Args:
        node: Flow node whose output is being archived
        output_dir: Path to node's output directory
        context: Flow execution context
    """
    import shutil
    from datetime import datetime

    try:
        archive_dir = output_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_path = archive_dir / f"{timestamp}_post"

        # Copy all files except archive subdirectory
        shutil.copytree(
            output_dir, archive_path, ignore=shutil.ignore_patterns("archive")
        )

        context.archive_manifest[f"{node.name}_post"] = archive_path
        logger.info(f"Archived new data for {node.name} to {archive_path.name}")

    except Exception as e:
        print(f"\nERROR: Failed to archive new data for '{node.name}'")
        print(f"  Reason: {e}")
        print(f"  Data was produced but not archived - flow stopped")
        import sys
        sys.exit(1)
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_core/test_flow_engine_archiving.py -v
```

Expected: PASS (all 8 tests)

**Step 6: Commit**

```bash
git add tests/unit/test_core/test_flow_engine_archiving.py src/finances/core/flow_engine.py
git commit -m "feat: implement archive creation functions"
```

---

---

## Task 12: Rewrite execute_flow with Sequential Prompt-Validate-Execute

**Files:**
- Modify: `src/finances/core/flow_engine.py:300` (rewrite execute_flow method)

**Background:** Replace batch execution with per-node prompt-validate-execute loop.

**Step 1: Backup existing execute_flow**

```bash
# Just for reference - we'll rewrite this method
git diff src/finances/core/flow_engine.py > /tmp/old_execute_flow.patch
```

**Step 2: Rewrite execute_flow method**

Replace the entire `execute_flow` method in `src/finances/core/flow_engine.py`:

```python
def execute_flow(self) -> dict[str, Any]:
    """
    Execute flow with sequential prompt-validate-execute per node.

    Prompts user for each node in topological order, validates dependencies,
    and executes immediately if approved. Archives data before and after
    execution when changes detected.

    Returns:
        Dictionary with execution summary
    """
    from datetime import datetime

    context = FlowContext(start_time=datetime.now())

    # Get nodes in dependency order (alphabetical tie-breaking)
    sorted_nodes = self.topological_sort_nodes()

    executed_nodes = []
    skipped_nodes = []

    for node_name in sorted_nodes:
        node = self.registry.get_node(node_name)
        if not node:
            continue

        # Get status info and format for display
        info = node.get_output_info()
        files = info.get_output_files()

        if not files:
            status = "No data"
        else:
            total_records = sum(f.record_count for f in files)
            latest_file = max(files, key=lambda f: f.path.stat().st_mtime)
            age_days = (
                datetime.now() - datetime.fromtimestamp(latest_file.path.stat().st_mtime)
            ).days
            status = f"{total_records} records, {age_days} days old"

        # Display and prompt
        print(f"\n[{node_name}]")
        print(f"  Status: {status}")

        import click
        response = click.confirm("  Run this node?", default=False)

        if not response:
            skipped_nodes.append(node_name)
            logger.info(f"Skipped node: {node_name}")
            continue

        # Validate dependencies
        for dep_name in node.dependencies:
            dep_node = self.registry.get_node(dep_name)
            if not dep_node:
                continue

            dep_info = dep_node.get_output_info()
            if not dep_info.is_data_ready():
                print(f"\nERROR: Cannot run '{node_name}'")
                print(f"  Dependency '{dep_name}' has no usable data")
                print(f"  Run the flow again and say 'yes' to '{dep_name}'")
                import sys
                sys.exit(1)

        # Archive existing data (if exists)
        output_dir = node.get_output_dir()
        pre_hash = None

        if output_dir and output_dir.exists() and any(output_dir.iterdir()):
            pre_hash = self.compute_directory_hash(output_dir)
            self.archive_existing_data(node, output_dir, context)

        # Execute node
        logger.info(f"Executing node: {node_name}")
        result = node.execute(context)

        if not result.success:
            print(f"\nERROR: Node execution failed: {result.error_message}")
            import sys
            sys.exit(1)

        executed_nodes.append(node_name)
        logger.info(f"Node {node_name} completed successfully")

        # Archive new data if changed
        if output_dir and output_dir.exists():
            post_hash = self.compute_directory_hash(output_dir)
            if post_hash != pre_hash:
                self.archive_new_data(node, output_dir, context)

    # Print summary
    print("\n" + "=" * 60)
    print("EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Executed: {len(executed_nodes)} nodes")
    print(f"Skipped: {len(skipped_nodes)} nodes")

    if executed_nodes:
        print("\nExecuted nodes:")
        for name in executed_nodes:
            print(f"  ✓ {name}")

    return {
        "executed": executed_nodes,
        "skipped": skipped_nodes,
        "total": len(sorted_nodes),
    }
```

**Step 3: Run mypy to verify**

```bash
uv run mypy src/finances/core/flow_engine.py
```

Expected: PASS

**Step 4: Commit**

```bash
git add src/finances/core/flow_engine.py
git commit -m "refactor: rewrite execute_flow with sequential prompt-validate-execute

- Topological sort with alphabetical tie-breaking
- Per-node prompt with formatted status display
- Dependency validation before execution
- Integrated archiving (pre/post)
- Clear execution summary"
```

---

## Task 13: Update E2E Test for New Execution Order

**Files:**
- Modify: `tests/e2e/test_flow_system.py:530` (update test expectations)

**Background:** E2E test needs to expect 11 prompts in correct topological order.

**Step 1: Review current E2E test structure**

```bash
grep -A 20 "def test_flow_interactive_execution_with_matching" tests/e2e/test_flow_system.py | head -30
```

**Step 2: Update test docstring with expected node order**

Find `test_flow_interactive_execution_with_matching` and update docstring:

```python
"""
Test complete interactive flow execution with coordinated data.

Expected execution sequence (11 nodes in topological order with alphabetical tie-breaking):

Level 0 (no dependencies, alphabetical):
1. amazon_order_history_request
2. apple_email_fetch
3. ynab_sync

Level 1 (depends on level 0, alphabetical):
4. amazon_unzip (depends on amazon_order_history_request)
5. apple_receipt_parsing (depends on apple_email_fetch)
6. cash_flow_analysis (depends on ynab_sync)
7. retirement_update (depends on ynab_sync)

Level 2:
8. amazon_matching (depends on ynab_sync + amazon_unzip)
9. apple_matching (depends on ynab_sync + apple_receipt_parsing)

Level 3:
10. split_generation (depends on amazon_matching + apple_matching)

Level 4:
11. ynab_apply (depends on split_generation)

This test verifies:
- Nodes prompt in correct topological order
- Dependency validation blocks execution if dependency has no data
- Archives created when data changes
"""
```

**Step 3: Run E2E test to see current behavior**

```bash
uv run pytest tests/e2e/test_flow_system.py::test_flow_interactive_execution_with_matching -v -s 2>&1 | head -100
```

Expected: May fail due to different prompt order

**Step 4: Update test to handle new prompt order**

This requires analyzing the specific test implementation. The test should:
- Expect prompts in the order listed above
- Handle "Run this node?" prompts (not the old prompt style)
- Verify archives created in second run

**Step 5: Commit**

```bash
git add tests/e2e/test_flow_system.py
git commit -m "test: update E2E test for new execution order

- Expect 11 prompts in topological order
- Update prompt text expectations
- Add archive verification"
```

---

## Task 14: Remove check_changes from All Nodes

**Files:**
- Modify: `src/finances/apple/flow.py` (3 nodes)
- Modify: `src/finances/amazon/flow.py` (3 nodes)
- Modify: `src/finances/ynab/flow.py` (2 nodes)
- Modify: `src/finances/ynab/split_generation_flow.py` (1 node)
- Modify: `src/finances/analysis/flow.py` (1 node)
- Modify: `src/finances/core/flow.py` (remove from FlowNode base)

**Background:** check_changes() is no longer used (YAGNI), remove it.

**Step 1: Remove check_changes from FlowNode base class**

Edit `src/finances/core/flow.py` - find and remove the `check_changes` abstract method:

```python
# DELETE THIS METHOD:
@abstractmethod
def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
    """
    Check if this node needs to execute based on upstream changes.
    ...
    """
    pass
```

**Step 2: Remove check_changes from Apple nodes**

Edit `src/finances/apple/flow.py` - remove check_changes method from:
- AppleEmailFetchFlowNode
- AppleReceiptParsingFlowNode
- AppleMatchingFlowNode

**Step 3: Remove check_changes from Amazon nodes**

Edit `src/finances/amazon/flow.py` - remove check_changes method from:
- AmazonOrderHistoryRequestFlowNode
- AmazonUnzipFlowNode
- AmazonMatchingFlowNode

**Step 4: Remove check_changes from YNAB nodes**

Edit `src/finances/ynab/flow.py` - remove check_changes method from:
- YnabSyncFlowNode
- RetirementUpdateFlowNode

Edit `src/finances/ynab/split_generation_flow.py` - remove check_changes method from:
- SplitGenerationFlowNode

**Step 5: Remove check_changes from Analysis nodes**

Edit `src/finances/analysis/flow.py` - remove check_changes method from:
- CashFlowAnalysisFlowNode

**Step 6: Remove check_changes from FunctionFlowNode**

Edit `src/finances/core/flow.py` in FunctionFlowNode class - remove check_changes method

**Step 7: Remove check_changes from CLIAdapterNode**

Edit `src/finances/core/flow.py` in CLIAdapterNode class - remove check_changes method

**Step 8: Run mypy to verify no references remain**

```bash
uv run mypy src/finances/ 2>&1 | grep "check_changes"
```

Expected: No results (method completely removed)

**Step 9: Commit**

```bash
git add src/finances/core/flow.py src/finances/apple/flow.py src/finances/amazon/flow.py src/finances/ynab/flow.py src/finances/ynab/split_generation_flow.py src/finances/analysis/flow.py
git commit -m "refactor: remove check_changes method (YAGNI)

check_changes() no longer used in new execution model.
User decides whether to run nodes via interactive prompts.

Removed from:
- FlowNode base class
- All 10 domain node implementations
- FunctionFlowNode
- CLIAdapterNode"
```

---

## Task 15: Run Full Test Suite and Fix Issues

**Files:**
- Various (as needed based on failures)

**Background:** Verify all changes work together correctly.

**Step 1: Run unit tests**

```bash
uv run pytest tests/unit/ -v
```

Expected: PASS (or identify specific failures to fix)

**Step 2: Run integration tests**

```bash
uv run pytest tests/integration/ -v
```

Expected: PASS (or identify specific failures to fix)

**Step 3: Run E2E tests**

```bash
uv run pytest tests/e2e/ -v -s
```

Expected: PASS (or identify specific failures to fix)

**Step 4: Run mypy on entire codebase**

```bash
uv run mypy src/finances/
```

Expected: PASS (no type errors)

**Step 5: Run code formatting checks**

```bash
uv run black --check src/ tests/
uv run ruff check src/ tests/
```

Expected: PASS (no formatting issues)

**Step 6: Fix any identified issues**

For each failing test:
- Read failure message
- Identify root cause
- Make minimal fix
- Re-run specific test
- Commit fix

**Step 7: Commit fixes (if any)**

```bash
git add [files]
git commit -m "fix: [description of what was fixed]"
```

---

## Task 16: Update Documentation

**Files:**
- Modify: `dev/specs/2025-09-24-financial-flow-system.md` (update spec)
- Modify: `CLAUDE.md` (update if flow execution mentioned)

**Background:** Documentation should reflect new execution model.

**Step 1: Update flow system specification**

Edit `dev/specs/2025-09-24-financial-flow-system.md` - find sections about execution and update:

```markdown
## Execution Model

**Sequential Prompt-Validate-Execute:**

1. **Topological Sort**: Sort all nodes by dependencies with alphabetical tie-breaking
2. **Per-Node Loop**: For each node in sorted order:
   - Display status from `get_output_info()`
   - Prompt user: "Run this node? [y/N]"
   - If no: Skip and continue
   - If yes: Validate dependencies, archive existing data, execute, archive new data
3. **Dependency Validation**: Check all dependencies via `is_data_ready()` before execution
4. **Archiving**: SHA-256 hash-based change detection with pre/post snapshots

**Node Output Information:**

- `OutputInfo` class with `is_data_ready()` and `get_output_files()` methods
- Type-safe `OutputFile` dataclass with path and record count
- Engine formats output info for display (records, age)
- No more `check_changes()` - user decides via interactive prompts

**Archive Structure:**
```
data/{domain}/{node}/          # Live data
data/{domain}/{node}/archive/  # Historical archives
  YYYY-MM-DD_HH-MM-SS_pre/     # Before execution backup
  YYYY-MM-DD_HH-MM-SS_post/    # After execution audit
```
```

**Step 2: Check if CLAUDE.md mentions flow execution**

```bash
grep -i "flow\|execution" CLAUDE.md | head -20
```

If flow execution is mentioned, update with new model.

**Step 3: Commit documentation updates**

```bash
git add dev/specs/2025-09-24-financial-flow-system.md CLAUDE.md
git commit -m "docs: update flow execution documentation

- Document sequential prompt-validate-execute model
- Update OutputInfo and archiving sections
- Remove references to check_changes()
- Add archive structure examples"
```

---

## Task 17: Create Pull Request

**Files:**
- None (git operations)

**Background:** Package all changes into PR for review and merge.

**Step 1: Ensure all changes committed**

```bash
git status
```

Expected: Clean working directory

**Step 2: Review commit history**

```bash
git log --oneline origin/main..HEAD
```

Expected: Should see all commits from Tasks 1-16

**Step 3: Push feature branch**

```bash
git push -u origin fix/flow-execution-order-issue-29
```

**Step 4: Create pull request**

```bash
gh pr create --title "Fix flow execution order and add archiving (Issue #29)" --body "$(cat <<'EOF'
## Summary

Fixes #29 - Flow engine execution order and automatic archiving

**Changes:**
- Add type-safe OutputInfo abstraction for node output inspection
- Implement topological sort with alphabetical tie-breaking
- Rewrite execute_flow with sequential prompt-validate-execute
- Add SHA-256 hash-based archiving with pre/post snapshots
- Remove unused check_changes() method (YAGNI)

## Implementation Details

**Type Safety:**
- New `OutputInfo` abstract class with `is_data_ready()` and `get_output_files()`
- `OutputFile` dataclass for file metadata
- All 11 nodes implement node-specific OutputInfo subclasses

**Execution Model:**
- Topological sort ensures dependencies execute before dependents
- Alphabetical tie-breaking for deterministic ordering
- Per-node prompt-validate-execute loop
- User controls all execution decisions

**Archiving:**
- SHA-256 hash-based change detection
- Pre-execution backup (if data exists)
- Post-execution audit (if data changed)
- Archive structure: `data/{domain}/{node}/archive/YYYY-MM-DD_HH-MM-SS_{pre|post}/`

**All 11 nodes updated:**
- Apple: email_fetch, receipt_parsing, matching
- Amazon: order_history_request, unzip, matching
- YNAB: sync, retirement_update, split_generation, apply
- Analysis: cash_flow_analysis

## Testing

**Unit Tests:**
- OutputInfo implementations for all nodes (9 test files)
- Topological sort with tie-breaking (3 tests)
- Directory hash computation (4 tests)
- Archive creation functions (8 tests)

**Integration Tests:**
- Complete flow execution scenarios
- Archive verification
- Hash-based change detection

**E2E Tests:**
- Updated for 11 prompts in topological order
- Dependency validation verification
- Archive creation in multi-run scenarios

**Test Results:**
- Unit: PASS (all tests)
- Integration: PASS (all tests)
- E2E: PASS (all tests)
- Mypy: PASS (no type errors)
- Black/Ruff: PASS (formatting correct)

## Documentation

**Updated:**
- Flow system specification (execution model, archiving)
- Design document (complete architecture)
- Implementation plan (task-by-task guide)

**Success Criteria:**

- ✓ All 11 nodes prompt in correct topological order (alphabetically within levels)
- ✓ Dependency validation blocks execution if dependency has no data
- ✓ Dependency validation allows execution if dependency has old data
- ✓ Archives created before execution (if data exists)
- ✓ Archives created after execution (if data changed)
- ✓ Archive failure stops flow immediately
- ✓ All nodes implement get_output_info() with node-specific OutputInfo subclass
- ✓ All nodes implement get_output_dir() (or return None)
- ✓ check_changes() removed from all nodes
- ✓ All unit tests pass
- ✓ All integration tests pass
- ✓ All E2E tests pass
- ✓ Mypy passes with zero errors

---

Related: #29
Design: `dev/plans/2025-10-19-flow-execution-order-fix.md`
Plan: `docs/plans/2025-10-19-flow-execution-order-implementation.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**Step 5: Verify PR created**

```bash
gh pr view
```

Expected: Shows PR details with link

---

## Summary

This implementation plan provides complete task-by-task guidance for fixing Issue #29:

**Total Tasks:** 17

**Approach:**
- TDD throughout (test first, implement, verify)
- Bite-sized steps (2-5 minutes each)
- Frequent commits (every task)
- Complete code examples (no "add validation" placeholders)
- Exact file paths and line numbers
- Clear expected outcomes

**Key Architectural Changes:**
1. Type-safe OutputInfo abstraction (Tasks 1-8)
2. Topological sort with alphabetical tie-breaking (Task 9)
3. SHA-256 hash-based change detection (Task 10)
4. Archiving infrastructure (Task 11)
5. Sequential execution model (Task 12)
6. Test updates (Task 13)
7. Cleanup and documentation (Tasks 14-16)
8. PR creation (Task 17)

**Execution Time:** 6-8 hours for experienced developer with TDD discipline

**Success Metrics:**
- All 11 nodes prompt in topological order
- Archives created when data changes
- All tests pass
- Zero type errors
- Clean documentation
