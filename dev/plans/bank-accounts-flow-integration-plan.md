# Bank Accounts Flow Integration - Implementation Plan

**Status**: Ready for Implementation
**Created**: 2026-01-08
**Design Reference**: `dev/designs/bank-accounts-flow-integration.md`

## Overview

This plan implements the bank accounts flow integration design, adding 3 FlowNode classes and 2 DataStore classes to enable bank reconciliation via `finances flow` command.

## Prerequisites

- ✅ Bank account nodes (retrieve, parse, reconcile) implemented and working standalone
- ✅ Code review improvements completed (PR #40)
- ✅ Engineering design formalized

## Implementation Phases

### Phase 1: DataStore Implementation

**Goal**: Create DataStore classes for normalized data and reconciliation operations.

**File**: `src/finances/bank_accounts/datastore.py`

#### Task 1.1: Create BankNormalizedDataStore

**Implementation**:
```python
"""DataStore implementations for bank accounts domain."""

from datetime import datetime
from pathlib import Path
from typing import Any

from finances.core.datastore_mixin import DataStoreMixin
from finances.core.json_utils import read_json, write_json


class BankNormalizedDataStore(DataStoreMixin):
    """
    Pattern C: Timestamped Accumulation for normalized account data.

    Files are stored as: {timestamp}_{slug}.json
    Each parse run creates new files (one per account).
    Files accumulate forever (no cleanup).
    """

    def __init__(self, normalized_dir: Path):
        """Initialize store with normalized data directory."""
        super().__init__()
        self.normalized_dir = normalized_dir

    def exists(self) -> bool:
        """Check if any normalized files exist."""
        return self.normalized_dir.exists() and len(
            self._get_files_cached(self.normalized_dir, "*.json")
        ) > 0

    def load(self) -> dict[str, Any]:
        """
        Load most recent normalized data (by mtime).

        Returns:
            Dict containing account_slug, parsed_at, transactions, balance_points

        Raises:
            FileNotFoundError: If no normalized files exist
        """
        files = self._get_files_cached(self.normalized_dir, "*.json")
        if not files:
            raise FileNotFoundError(f"No normalized data found in {self.normalized_dir}")

        most_recent = max(files, key=lambda f: f.stat().st_mtime)
        return read_json(most_recent)

    def save(self, account_slug: str, data: dict[str, Any]) -> Path:
        """
        Save normalized data with timestamp and account slug.

        Args:
            account_slug: Account identifier (e.g., "apple-card")
            data: Normalized account data (transactions, balances)

        Returns:
            Path to created file
        """
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.normalized_dir / f"{timestamp}_{account_slug}.json"

        write_json(output_file, data)
        self._invalidate_cache()

        return output_file

    def last_modified(self) -> datetime | None:
        """Return most recent file modification time."""
        files = self._get_files_cached(self.normalized_dir, "*.json")
        if not files:
            return None

        most_recent = max(files, key=lambda f: f.stat().st_mtime)
        return datetime.fromtimestamp(most_recent.stat().st_mtime)

    def item_count(self) -> int | None:
        """Return count of normalized files."""
        return len(self._get_files_cached(self.normalized_dir, "*.json"))

    def size_bytes(self) -> int | None:
        """Return total size of all normalized files."""
        files = self._get_files_cached(self.normalized_dir, "*.json")
        if not files:
            return None
        return sum(f.stat().st_size for f in files)

    def summary_text(self) -> str:
        """Provide human-readable summary."""
        count = self.item_count() or 0
        age = self.age_days()
        age_str = f"{age}d old" if age is not None else "never"
        return f"{count} normalized files, last modified {age_str}"
```

**Acceptance Criteria**:
- [ ] Class implements all DataStore protocol methods
- [ ] Uses timestamped filenames: `{timestamp}_{slug}.json`
- [ ] `load()` returns most recent file by mtime
- [ ] `save()` creates new file and invalidates cache
- [ ] Follows existing DataStore patterns (Amazon/Apple)

#### Task 1.2: Create BankReconciliationStore

**Implementation**:
```python
class BankReconciliationStore(DataStoreMixin):
    """
    Pattern C: Timestamped Accumulation for reconciliation operations.

    Files are stored as: {timestamp}_operations.json
    Each reconcile run creates one file covering all accounts.
    Files accumulate forever (no cleanup).
    """

    def __init__(self, reconciliation_dir: Path):
        """Initialize store with reconciliation directory."""
        super().__init__()
        self.reconciliation_dir = reconciliation_dir

    def exists(self) -> bool:
        """Check if any operations files exist."""
        return self.reconciliation_dir.exists() and len(
            self._get_files_cached(self.reconciliation_dir, "*.json")
        ) > 0

    def load(self) -> dict[str, Any]:
        """
        Load most recent reconciliation (by mtime).

        Returns:
            Dict containing reconciled_at and per-account reconciliation data

        Raises:
            FileNotFoundError: If no reconciliation files exist
        """
        files = self._get_files_cached(self.reconciliation_dir, "*.json")
        if not files:
            raise FileNotFoundError(
                f"No reconciliation data found in {self.reconciliation_dir}"
            )

        most_recent = max(files, key=lambda f: f.stat().st_mtime)
        return read_json(most_recent)

    def save(self, data: dict[str, Any]) -> Path:
        """
        Save reconciliation with timestamp.

        Args:
            data: Reconciliation operations for all accounts

        Returns:
            Path to created file
        """
        self.reconciliation_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.reconciliation_dir / f"{timestamp}_operations.json"

        write_json(output_file, data)
        self._invalidate_cache()

        return output_file

    def last_modified(self) -> datetime | None:
        """Return most recent file modification time."""
        files = self._get_files_cached(self.reconciliation_dir, "*.json")
        if not files:
            return None

        most_recent = max(files, key=lambda f: f.stat().st_mtime)
        return datetime.fromtimestamp(most_recent.stat().st_mtime)

    def item_count(self) -> int | None:
        """Return count of operations files."""
        return len(self._get_files_cached(self.reconciliation_dir, "*.json"))

    def size_bytes(self) -> int | None:
        """Return total size of all operations files."""
        files = self._get_files_cached(self.reconciliation_dir, "*.json")
        if not files:
            return None
        return sum(f.stat().st_size for f in files)

    def summary_text(self) -> str:
        """Provide human-readable summary."""
        count = self.item_count() or 0
        age = self.age_days()
        age_str = f"{age}d old" if age is not None else "never"
        return f"{count} reconciliation files, last modified {age_str}"
```

**Acceptance Criteria**:
- [ ] Class implements all DataStore protocol methods
- [ ] Uses timestamped filenames: `{timestamp}_operations.json`
- [ ] `load()` returns most recent file by mtime
- [ ] `save()` creates new file and invalidates cache
- [ ] Follows existing DataStore patterns (Amazon/Apple)

#### Task 1.3: Write DataStore Unit Tests

**File**: `tests/unit/bank_accounts/test_datastore.py`

**Test Coverage**:
```python
"""Unit tests for bank accounts DataStore classes."""

import tempfile
from pathlib import Path
from time import sleep

import pytest

from finances.bank_accounts.datastore import (
    BankNormalizedDataStore,
    BankReconciliationStore,
)


class TestBankNormalizedDataStore:
    """Test BankNormalizedDataStore Pattern C behavior."""

    def test_exists_false_when_no_directory(self):
        """Store should not exist if directory doesn't exist."""
        store = BankNormalizedDataStore(Path("/nonexistent"))
        assert not store.exists()

    def test_exists_false_when_empty_directory(self, tmp_path):
        """Store should not exist if directory is empty."""
        store = BankNormalizedDataStore(tmp_path)
        assert not store.exists()

    def test_exists_true_after_save(self, tmp_path):
        """Store should exist after saving data."""
        store = BankNormalizedDataStore(tmp_path)
        store.save("apple-card", {"test": "data"})
        assert store.exists()

    def test_save_creates_timestamped_file(self, tmp_path):
        """Save should create file with timestamp and slug."""
        store = BankNormalizedDataStore(tmp_path)
        output_file = store.save("apple-card", {"test": "data"})

        assert output_file.exists()
        assert "apple-card" in output_file.name
        assert output_file.suffix == ".json"

    def test_load_returns_most_recent(self, tmp_path):
        """Load should return most recent file by mtime."""
        store = BankNormalizedDataStore(tmp_path)

        store.save("apple-card", {"version": 1})
        sleep(0.01)  # Ensure different mtime
        store.save("apple-savings", {"version": 2})

        result = store.load()
        assert result["version"] == 2

    def test_load_raises_when_empty(self, tmp_path):
        """Load should raise FileNotFoundError when no files."""
        store = BankNormalizedDataStore(tmp_path)

        with pytest.raises(FileNotFoundError, match="No normalized data found"):
            store.load()

    def test_item_count(self, tmp_path):
        """Item count should return number of files."""
        store = BankNormalizedDataStore(tmp_path)

        assert store.item_count() == 0

        store.save("apple-card", {"test": 1})
        assert store.item_count() == 1

        store.save("apple-savings", {"test": 2})
        assert store.item_count() == 2

    def test_summary_text(self, tmp_path):
        """Summary should include count and age."""
        store = BankNormalizedDataStore(tmp_path)
        store.save("apple-card", {"test": "data"})

        summary = store.summary_text()
        assert "1 normalized files" in summary
        assert "0d old" in summary


class TestBankReconciliationStore:
    """Test BankReconciliationStore Pattern C behavior."""

    def test_exists_false_when_no_directory(self):
        """Store should not exist if directory doesn't exist."""
        store = BankReconciliationStore(Path("/nonexistent"))
        assert not store.exists()

    def test_exists_false_when_empty_directory(self, tmp_path):
        """Store should not exist if directory is empty."""
        store = BankReconciliationStore(tmp_path)
        assert not store.exists()

    def test_exists_true_after_save(self, tmp_path):
        """Store should exist after saving data."""
        store = BankReconciliationStore(tmp_path)
        store.save({"test": "data"})
        assert store.exists()

    def test_save_creates_timestamped_file(self, tmp_path):
        """Save should create file with timestamp and 'operations'."""
        store = BankReconciliationStore(tmp_path)
        output_file = store.save({"test": "data"})

        assert output_file.exists()
        assert "operations" in output_file.name
        assert output_file.suffix == ".json"

    def test_load_returns_most_recent(self, tmp_path):
        """Load should return most recent file by mtime."""
        store = BankReconciliationStore(tmp_path)

        store.save({"version": 1})
        sleep(0.01)  # Ensure different mtime
        store.save({"version": 2})

        result = store.load()
        assert result["version"] == 2

    def test_load_raises_when_empty(self, tmp_path):
        """Load should raise FileNotFoundError when no files."""
        store = BankReconciliationStore(tmp_path)

        with pytest.raises(FileNotFoundError, match="No reconciliation data found"):
            store.load()

    def test_item_count(self, tmp_path):
        """Item count should return number of files."""
        store = BankReconciliationStore(tmp_path)

        assert store.item_count() == 0

        store.save({"test": 1})
        assert store.item_count() == 1

        store.save({"test": 2})
        assert store.item_count() == 2

    def test_summary_text(self, tmp_path):
        """Summary should include count and age."""
        store = BankReconciliationStore(tmp_path)
        store.save({"test": "data"})

        summary = store.summary_text()
        assert "1 reconciliation files" in summary
        assert "0d old" in summary
```

**Acceptance Criteria**:
- [ ] All tests pass with `uv run pytest tests/unit/bank_accounts/test_datastore.py`
- [ ] Tests cover exists(), load(), save(), item_count(), summary_text()
- [ ] Tests verify timestamped file creation
- [ ] Tests verify most-recent file selection in load()

---

### Phase 2: FlowNode Implementation

**Goal**: Create FlowNode wrapper classes for retrieve, parse, and reconcile operations.

**File**: `src/finances/bank_accounts/flow.py`

#### Task 2.1: Create BankDataRetrieveFlowNode

**Implementation**:
```python
"""Flow node implementations for bank accounts domain."""

from datetime import datetime
from pathlib import Path

from finances.bank_accounts.config import BankAccountsConfig
from finances.bank_accounts.datastore import (
    BankNormalizedDataStore,
    BankReconciliationStore,
)
from finances.bank_accounts.nodes.parse import parse_account_data
from finances.bank_accounts.nodes.reconcile import reconcile_account_balances
from finances.bank_accounts.nodes.retrieve import retrieve_account_data
from finances.cli.flow_core import FlowContext, FlowNode, FlowResult, OutputInfo


class BankDataRetrieveOutputInfo(OutputInfo):
    """Validates that raw account data exists for configured accounts."""

    def __init__(self, output_dir: Path, config: BankAccountsConfig):
        super().__init__(output_dir)
        self.config = config

    def is_data_ready(self) -> bool:
        """Check if at least one configured account has raw data."""
        if not self.output_dir.exists():
            return False

        for account in self.config.accounts:
            account_dir = self.output_dir / account.slug
            if account_dir.exists() and len(list(account_dir.glob("*"))) > 0:
                return True

        return False

    def get_output_files(self) -> list[Path]:
        """Return all raw export files across all accounts."""
        files = []
        for account in self.config.accounts:
            account_dir = self.output_dir / account.slug
            if account_dir.exists():
                files.extend(account_dir.glob("*"))
        return files


class BankDataRetrieveFlowNode(FlowNode):
    """
    Flow node for retrieving raw bank export files.

    Copies export files from configured source paths to data/bank_accounts/raw/{slug}/.
    No dependencies - entry point for bank account flow.
    """

    def __init__(self, data_dir: Path, config: BankAccountsConfig):
        super().__init__("bank_data_retrieve")
        self._dependencies = set()
        self.data_dir = data_dir
        self.config = config
        self.raw_dir = data_dir / "bank_accounts" / "raw"

    def get_output_info(self) -> OutputInfo:
        """Return output validation info."""
        return BankDataRetrieveOutputInfo(self.raw_dir, self.config)

    def get_output_dir(self) -> Path:
        """Return output directory path."""
        return self.raw_dir

    def get_data_summary(self, context: FlowContext) -> dict:
        """Return summary of raw data status."""
        summary = {"accounts": {}}

        for account in self.config.accounts:
            account_dir = self.raw_dir / account.slug
            if account_dir.exists():
                files = list(account_dir.glob("*"))
                summary["accounts"][account.slug] = {
                    "file_count": len(files),
                    "files": [f.name for f in files],
                }
            else:
                summary["accounts"][account.slug] = {
                    "file_count": 0,
                    "files": [],
                }

        return summary

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute retrieve operation."""
        try:
            # Call existing retrieve function
            stats = retrieve_account_data(self.config, self.data_dir)

            # Collect all output files for cleanup protection
            output_files = self.get_output_info().get_output_files()

            # Build summary
            total_copied = sum(acct["copied"] for acct in stats.values())
            total_skipped = sum(acct["skipped"] for acct in stats.values())

            summary = f"Retrieved {total_copied} files, skipped {total_skipped} existing"

            if total_copied == 0 and total_skipped == 0:
                return FlowResult.warning(
                    node_id=self.node_id,
                    outputs=output_files,
                    summary="No files found to retrieve",
                )

            return FlowResult.success(
                node_id=self.node_id,
                outputs=output_files,
                summary=summary,
            )

        except Exception as e:
            return FlowResult.error(
                node_id=self.node_id,
                outputs=[],
                summary=f"Retrieve failed: {e}",
            )
```

**Acceptance Criteria**:
- [ ] Node wraps existing `retrieve_account_data()` function
- [ ] OutputInfo validates at least one account has raw data
- [ ] Returns all raw files in FlowResult.outputs (cleanup protection)
- [ ] Follows existing FlowNode patterns (Amazon/Apple)

#### Task 2.2: Create BankDataParseFlowNode

**Implementation**:
```python
class BankDataParseOutputInfo(OutputInfo):
    """Validates that normalized data exists."""

    def is_data_ready(self) -> bool:
        """Check if at least one normalized file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.json"))) >= 1

    def get_output_files(self) -> list[Path]:
        """Return all normalized JSON files."""
        if not self.output_dir.exists():
            return []
        return list(self.output_dir.glob("*.json"))


class BankDataParseFlowNode(FlowNode):
    """
    Flow node for parsing raw bank exports to normalized format.

    Reads from: data/bank_accounts/raw/{slug}/
    Writes to: data/bank_accounts/normalized/{timestamp}_{slug}.json
    Depends on: bank_data_retrieve
    """

    def __init__(self, data_dir: Path, config: BankAccountsConfig):
        super().__init__("bank_data_parse")
        self._dependencies = {"bank_data_retrieve"}
        self.data_dir = data_dir
        self.config = config
        self.normalized_dir = data_dir / "bank_accounts" / "normalized"
        self.store = BankNormalizedDataStore(self.normalized_dir)

    def get_output_info(self) -> OutputInfo:
        """Return output validation info."""
        return BankDataParseOutputInfo(self.normalized_dir)

    def get_output_dir(self) -> Path:
        """Return output directory path."""
        return self.normalized_dir

    def get_data_summary(self, context: FlowContext) -> dict:
        """Return summary of normalized data."""
        if not self.store.exists():
            return {"status": "no_data"}

        return {
            "file_count": self.store.item_count(),
            "last_modified": self.store.last_modified().isoformat() if self.store.last_modified() else None,
            "age_days": self.store.age_days(),
        }

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute parse operation."""
        try:
            # Call existing parse function
            results = parse_account_data(self.config, self.data_dir)

            # Save each account's normalized data with DataStore
            new_files = []
            for account_slug, result in results.items():
                # Serialize domain models to JSON
                data = {
                    "account_slug": account_slug,
                    "parsed_at": datetime.now().isoformat(),
                    "transactions": [tx.to_dict() for tx in result.transactions],
                    "balance_points": [bp.to_dict() for bp in result.balance_points],
                    "statement_date": result.statement_date.to_string() if result.statement_date else None,
                }

                output_file = self.store.save(account_slug, data)
                new_files.append(output_file)

            # Get ALL existing files for cleanup protection
            all_files = self.get_output_info().get_output_files()

            # Build summary
            total_txs = sum(len(r.transactions) for r in results.values())
            summary = f"Parsed {len(results)} accounts, {total_txs} transactions"

            return FlowResult.success(
                node_id=self.node_id,
                outputs=all_files,  # Protects all accumulated files
                summary=summary,
            )

        except Exception as e:
            return FlowResult.error(
                node_id=self.node_id,
                outputs=self.get_output_info().get_output_files(),  # Protect existing on error
                summary=f"Parse failed: {e}",
            )
```

**Acceptance Criteria**:
- [ ] Node wraps existing `parse_account_data()` function
- [ ] Uses BankNormalizedDataStore for file operations
- [ ] Creates timestamped files: `{timestamp}_{slug}.json`
- [ ] Returns ALL normalized files in FlowResult.outputs (cleanup protection)
- [ ] Declares dependency on `bank_data_retrieve`

#### Task 2.3: Create BankDataReconcileFlowNode

**Implementation**:
```python
class BankDataReconcileOutputInfo(OutputInfo):
    """Validates that reconciliation operations exist."""

    def is_data_ready(self) -> bool:
        """Check if at least one operations file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.json"))) >= 1

    def get_output_files(self) -> list[Path]:
        """Return all operations JSON files."""
        if not self.output_dir.exists():
            return []
        return list(self.output_dir.glob("*.json"))


class BankDataReconcileFlowNode(FlowNode):
    """
    Flow node for reconciling bank balances with YNAB.

    Reads from: data/bank_accounts/normalized/
                data/ynab/cache/
    Writes to: data/bank_accounts/reconciliation/{timestamp}_operations.json
    Depends on: bank_data_parse, ynab_sync
    """

    def __init__(self, data_dir: Path, config: BankAccountsConfig):
        super().__init__("bank_data_reconcile")
        self._dependencies = {"bank_data_parse", "ynab_sync"}
        self.data_dir = data_dir
        self.config = config
        self.reconciliation_dir = data_dir / "bank_accounts" / "reconciliation"
        self.store = BankReconciliationStore(self.reconciliation_dir)

    def get_output_info(self) -> OutputInfo:
        """Return output validation info."""
        return BankDataReconcileOutputInfo(self.reconciliation_dir)

    def get_output_dir(self) -> Path:
        """Return output directory path."""
        return self.reconciliation_dir

    def get_data_summary(self, context: FlowContext) -> dict:
        """Return summary of reconciliation data."""
        if not self.store.exists():
            return {"status": "no_data"}

        return {
            "file_count": self.store.item_count(),
            "last_modified": self.store.last_modified().isoformat() if self.store.last_modified() else None,
            "age_days": self.store.age_days(),
        }

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute reconcile operation."""
        try:
            # Call existing reconcile function
            results = reconcile_account_balances(self.config, self.data_dir)

            # Serialize to JSON
            data = {
                "reconciled_at": datetime.now().isoformat(),
                "accounts": {
                    slug: {
                        "reconciliation": result.reconciliation.to_dict(),
                        "unmatched_bank_txs": [tx.to_dict() for tx in result.unmatched_bank_txs],
                        "unmatched_ynab_txs": [tx.to_dict() for tx in result.unmatched_ynab_txs],
                    }
                    for slug, result in results.items()
                },
            }

            # Save with DataStore
            output_file = self.store.save(data)

            # Get ALL existing files for cleanup protection
            all_files = self.get_output_info().get_output_files()

            # Build summary
            reconciled_count = sum(
                1 for r in results.values()
                if r.reconciliation.last_reconciled_date is not None
            )
            diverged_count = sum(
                1 for r in results.values()
                if r.reconciliation.first_diverged_date is not None
            )

            summary = f"Reconciled {len(results)} accounts: {reconciled_count} OK, {diverged_count} diverged"

            if diverged_count > 0:
                return FlowResult.warning(
                    node_id=self.node_id,
                    outputs=all_files,
                    summary=summary,
                )

            return FlowResult.success(
                node_id=self.node_id,
                outputs=all_files,
                summary=summary,
            )

        except Exception as e:
            return FlowResult.error(
                node_id=self.node_id,
                outputs=self.get_output_info().get_output_files(),  # Protect existing on error
                summary=f"Reconcile failed: {e}",
            )
```

**Acceptance Criteria**:
- [ ] Node wraps existing `reconcile_account_balances()` function
- [ ] Uses BankReconciliationStore for file operations
- [ ] Creates timestamped files: `{timestamp}_operations.json`
- [ ] Returns ALL reconciliation files in FlowResult.outputs (cleanup protection)
- [ ] Declares dependencies on `bank_data_parse` and `ynab_sync`
- [ ] Returns warning status if any accounts diverged

---

### Phase 3: Flow Registry Integration

**Goal**: Register bank account nodes in the flow system.

#### Task 3.1: Update Flow Registry Setup

**File**: `src/finances/cli/flow.py`

**Changes**:
```python
def setup_flow_nodes() -> None:
    """Register all flow nodes with their dependencies."""
    config = get_config()

    # Import FlowNode classes from domain modules
    from ..amazon.flow import (
        AmazonMatchingFlowNode,
        AmazonOrderHistoryRequestFlowNode,
        AmazonUnzipFlowNode,
    )
    from ..apple.flow import (
        AppleEmailFetchFlowNode,
        AppleMatchingFlowNode,
        AppleReceiptParseFlowNode,
    )

    # NEW: Import bank accounts nodes
    from ..bank_accounts.config import BankAccountsConfig
    from ..bank_accounts.flow import (
        BankDataRetrieveFlowNode,
        BankDataParseFlowNode,
        BankDataReconcileFlowNode,
    )

    from ..analysis.flow import CashFlowAnalysisFlowNode
    from ..ynab.flow import YnabSyncFlowNode

    # Register Amazon nodes
    flow_registry.register_node(AmazonOrderHistoryRequestFlowNode(config.data_dir))
    flow_registry.register_node(AmazonUnzipFlowNode(config.data_dir))
    flow_registry.register_node(AmazonMatchingFlowNode(config.data_dir))

    # Register Apple nodes
    flow_registry.register_node(AppleEmailFetchFlowNode(config.data_dir))
    flow_registry.register_node(AppleReceiptParseFlowNode(config.data_dir))
    flow_registry.register_node(AppleMatchingFlowNode(config.data_dir))

    # Register YNAB nodes
    flow_registry.register_node(YnabSyncFlowNode(config.data_dir))

    # NEW: Register bank accounts nodes
    bank_config = BankAccountsConfig.load()
    flow_registry.register_node(BankDataRetrieveFlowNode(config.data_dir, bank_config))
    flow_registry.register_node(BankDataParseFlowNode(config.data_dir, bank_config))
    flow_registry.register_node(BankDataReconcileFlowNode(config.data_dir, bank_config))

    # Register analysis nodes
    flow_registry.register_node(CashFlowAnalysisFlowNode(config.data_dir))
```

**Acceptance Criteria**:
- [ ] All 3 bank account nodes registered
- [ ] BankAccountsConfig loaded for node initialization
- [ ] No import errors
- [ ] Flow system recognizes `bank_data_*` node IDs

---

### Phase 4: Testing

#### Task 4.1: Write Integration Tests

**File**: `tests/integration/bank_accounts/test_flow_integration.py`

**Test Coverage**:
```python
"""Integration tests for bank accounts flow nodes."""

import tempfile
from pathlib import Path

import pytest

from finances.bank_accounts.config import AccountConfig, BankAccountsConfig
from finances.bank_accounts.flow import (
    BankDataRetrieveFlowNode,
    BankDataParseFlowNode,
    BankDataReconcileFlowNode,
)
from finances.cli.flow_core import FlowContext


@pytest.fixture
def test_config(tmp_path):
    """Create test configuration with synthetic data."""
    # Setup test directories
    raw_dir = tmp_path / "bank_accounts" / "raw" / "test-account"
    raw_dir.mkdir(parents=True)

    # Create dummy raw export file
    export_file = raw_dir / "test-export.ofx"
    export_file.write_text("<OFX>...</OFX>")  # Minimal OFX content

    config = BankAccountsConfig(
        accounts=[
            AccountConfig(
                slug="test-account",
                name="Test Account",
                export_format="apple_card_ofx",
                source_path=str(export_file),
                ynab_account_name="Test YNAB Account",
            )
        ]
    )

    return config, tmp_path


class TestBankDataRetrieveFlowNode:
    """Test BankDataRetrieveFlowNode integration."""

    def test_execute_success(self, test_config):
        """Node should successfully retrieve raw files."""
        config, data_dir = test_config
        node = BankDataRetrieveFlowNode(data_dir, config)

        context = FlowContext(data_dir=data_dir)
        result = node.execute(context)

        assert result.success
        assert len(result.outputs) > 0
        assert "Retrieved" in result.summary

    def test_output_info_is_ready(self, test_config):
        """OutputInfo should detect when data is ready."""
        config, data_dir = test_config
        node = BankDataRetrieveFlowNode(data_dir, config)

        output_info = node.get_output_info()
        assert output_info.is_data_ready()


class TestBankDataParseFlowNode:
    """Test BankDataParseFlowNode integration."""

    def test_execute_creates_normalized_files(self, test_config):
        """Node should create timestamped normalized files."""
        config, data_dir = test_config
        node = BankDataParseFlowNode(data_dir, config)

        context = FlowContext(data_dir=data_dir)
        result = node.execute(context)

        assert result.success
        assert len(result.outputs) > 0

        # Verify timestamped filename
        output_file = result.outputs[0]
        assert "test-account" in output_file.name
        assert output_file.suffix == ".json"

    def test_output_files_include_all_accumulated(self, test_config):
        """FlowResult.outputs should include all accumulated files."""
        config, data_dir = test_config
        node = BankDataParseFlowNode(data_dir, config)

        context = FlowContext(data_dir=data_dir)

        # First run
        result1 = node.execute(context)
        assert len(result1.outputs) == 1

        # Second run
        result2 = node.execute(context)
        assert len(result2.outputs) == 2  # Both files protected


class TestBankDataReconcileFlowNode:
    """Test BankDataReconcileFlowNode integration."""

    def test_execute_creates_operations_file(self, test_config):
        """Node should create timestamped operations file."""
        config, data_dir = test_config

        # Setup: Create normalized data first
        parse_node = BankDataParseFlowNode(data_dir, config)
        parse_node.execute(FlowContext(data_dir=data_dir))

        # Setup: Create mock YNAB cache
        ynab_dir = data_dir / "ynab" / "cache"
        ynab_dir.mkdir(parents=True)
        (ynab_dir / "transactions.json").write_text("[]")
        (ynab_dir / "accounts.json").write_text('{"accounts": []}')

        # Execute reconcile
        reconcile_node = BankDataReconcileFlowNode(data_dir, config)
        context = FlowContext(data_dir=data_dir)
        result = reconcile_node.execute(context)

        assert result.success or result.warning  # Warning if diverged
        assert len(result.outputs) > 0

        # Verify timestamped filename
        output_file = result.outputs[0]
        assert "operations" in output_file.name
        assert output_file.suffix == ".json"
```

**Acceptance Criteria**:
- [ ] All integration tests pass
- [ ] Tests verify node execute() behavior with real files
- [ ] Tests verify DataStore file creation
- [ ] Tests verify FlowResult.outputs includes all accumulated files

#### Task 4.2: Write E2E Flow Test

**File**: `tests/e2e/test_bank_accounts_flow.py`

**Test Coverage**:
```python
"""E2E tests for bank accounts flow integration."""

import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_bank_accounts_flow_end_to_end(tmp_path):
    """
    Test complete bank accounts flow via CLI.

    Verifies:
    1. Files created in correct directories
    2. Timestamped accumulation behavior
    3. Flow system change detection
    """
    # Setup test environment with config
    # ... (similar to integration test setup)

    # Run flow nodes
    result = subprocess.run(
        ["finances", "flow", "bank_data_retrieve", "bank_data_parse", "bank_data_reconcile"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "bank_data_retrieve" in result.stdout
    assert "bank_data_parse" in result.stdout
    assert "bank_data_reconcile" in result.stdout

    # Verify files created
    normalized_dir = tmp_path / "bank_accounts" / "normalized"
    assert normalized_dir.exists()
    assert len(list(normalized_dir.glob("*.json"))) > 0

    reconciliation_dir = tmp_path / "bank_accounts" / "reconciliation"
    assert reconciliation_dir.exists()
    assert len(list(reconciliation_dir.glob("*.json"))) > 0


@pytest.mark.e2e
def test_flow_skips_when_no_changes(tmp_path):
    """Flow should skip nodes when dependencies haven't changed."""
    # ... (run flow twice, verify second run skips nodes)
```

**Acceptance Criteria**:
- [ ] E2E test passes with `uv run pytest tests/e2e/test_bank_accounts_flow.py`
- [ ] Test runs actual `finances flow` command via subprocess
- [ ] Test verifies files created in correct directories
- [ ] Test verifies flow change detection works

---

## Verification Checklist

Before marking implementation complete:

- [ ] All DataStore unit tests pass
- [ ] All FlowNode integration tests pass
- [ ] E2E flow test passes
- [ ] `mypy src/finances/bank_accounts/` passes with no errors
- [ ] `uv run pytest tests/` passes (full test suite)
- [ ] Manual test: `finances flow bank_data_retrieve bank_data_parse bank_data_reconcile` works
- [ ] Manual test: Run twice, verify second run detects no changes and skips
- [ ] Files accumulate correctly (no unexpected cleanup)
- [ ] All design document requirements met

## Post-Implementation Tasks

- [ ] Update `dev/todos.md` to mark flow integration complete
- [ ] Update PR #40 description with flow integration completion
- [ ] Run code review (`finances review` if available)
- [ ] Push changes and verify CI passes
- [ ] Document flow usage in CLAUDE.md if needed

## Notes

- **No Business Logic Changes**: All existing retrieve/parse/reconcile functions work correctly, we're only wrapping them
- **Pattern C Everywhere**: Both DataStores use timestamped accumulation, matching Amazon/Apple patterns
- **File Cleanup Protection**: Critical to include ALL files in FlowResult.outputs to prevent FlowEngine cleanup
- **Type Safety**: Maintain Money/FinancialDate throughout, serialize via `.to_dict()` only at JSON boundaries
