# Flow Execution Order Fix - Design Document

**Date:** 2025-10-19

**Related Issue:** https://github.com/karlmdavis/justdavis-finances/issues/29

**Status:** Design Complete - Ready for Implementation

---

## Problem Statement

The flow execution engine can execute nodes in the wrong order, violating their declared dependencies.
Specifically, `apple_receipt_parsing` can run before `apple_email_fetch` even though it declares a dependency on it.

**Root Cause:**

In `src/finances/core/flow_engine.py`, the `find_ready_nodes()` method considers a dependency satisfied if:

```python
dependencies_satisfied = all(
    dep_name in completed_nodes or dep_name not in remaining_nodes
    for dep_name in node.dependencies
)
```

The problem is `dep_name not in remaining_nodes` - this treats "dependency not needed" the same as "dependency completed".

---

## Design Overview

**Core Principle:** KISS - prompt user for every node in topological order, validate dependencies have data, execute immediately.

**Architecture:**

1. **Type-safe output information** - New `OutputInfo` class with `is_data_ready()` and `get_output_files()` methods
2. **Sequential execution** - Topological sort with alphabetical tie-breaking, prompt-validate-execute per node
3. **Data-based validation** - Dependencies satisfied if they have usable data (fresh or old)
4. **Automatic archiving** - Archive existing data before execution, archive new data after if changed

---

## Node Dependency Structure

**All 11 Flow Nodes (in topological order with alphabetical tie-breaking):**

Level 0 (no dependencies):
1. amazon_order_history_request
2. apple_email_fetch
3. ynab_sync

Level 1 (depends on level 0):
4. amazon_unzip (depends on amazon_order_history_request)
5. apple_receipt_parsing (depends on apple_email_fetch)
6. cash_flow_analysis (depends on ynab_sync)
7. retirement_update (depends on ynab_sync)

Level 2 (depends on level 1):
8. amazon_matching (depends on ynab_sync + amazon_unzip)
9. apple_matching (depends on ynab_sync + apple_receipt_parsing)

Level 3 (depends on level 2):
10. split_generation (depends on amazon_matching + apple_matching)

Level 4 (depends on level 3):
11. ynab_apply (depends on split_generation)

---

## Type-Safe Output Information

### New Classes

**File:** `src/finances/core/flow_node.py`

```python
@dataclass(frozen=True)
class OutputFile:
    """Information about a single output file from a flow node."""
    path: Path
    record_count: int

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

### FlowNode Abstract Method

```python
@abstractmethod
def get_output_info(self) -> OutputInfo:
    """Get information about this node's output data."""
    pass
```

### Example Implementation

**AppleReceiptParsingNode:**

```python
class AppleReceiptParsingNode(FlowNode):
    def get_output_info(self) -> OutputInfo:
        return AppleReceiptOutputInfo(self.get_output_dir())

class AppleReceiptOutputInfo(OutputInfo):
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 .html file exists (what dependencies consume)."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob('*.html'))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return all output files (.eml, .html, .txt) with counts."""
        if not self.output_dir.exists():
            return []

        files = []

        # Add .html files (what dependencies use)
        for html_file in self.output_dir.glob('*.html'):
            files.append(OutputFile(path=html_file, record_count=1))

        # Add .eml files
        for eml_file in self.output_dir.glob('*.eml'):
            files.append(OutputFile(path=eml_file, record_count=1))

        # Add text files
        for txt_file in self.output_dir.glob('*.txt'):
            files.append(OutputFile(path=txt_file, record_count=1))

        return files
```

---

## Flow Engine Execution Logic

### Topological Sort with Alphabetical Tie-Breaking

```python
def topological_sort_nodes(self) -> list[str]:
    """
    Sort nodes by dependencies with alphabetical tie-breaking.

    Returns:
        Ordered list of node names (dependencies first)
    """
    # Standard topological sort algorithm
    # When multiple nodes at same level, sort alphabetically
    # Returns deterministic ordering
```

### Execution Flow

**File:** `src/finances/core/flow_engine.py`

```python
def execute_flow(self):
    # Get nodes in dependency order (alphabetical tie-breaking)
    sorted_nodes = self.topological_sort_nodes()

    for node_name in sorted_nodes:
        node = self.nodes[node_name]

        # Get status info and format for display
        info = node.get_output_info()
        files = info.get_output_files()

        if not files:
            status = "No data"
        else:
            total_records = sum(f.record_count for f in files)
            latest_file = max(files, key=lambda f: f.path.stat().st_mtime)
            age_days = (datetime.now() - datetime.fromtimestamp(latest_file.path.stat().st_mtime)).days
            status = f"{total_records} records, {age_days} days old"

        # Display and prompt
        print(f"\n[{node_name}]")
        print(f"  Status: {status}")
        response = input("  Run this node? [y/N] ")

        if response.lower() != 'y':
            continue

        # Validate dependencies
        for dep_name in node.dependencies:
            dep_info = self.nodes[dep_name].get_output_info()
            if not dep_info.is_data_ready():
                print(f"\nERROR: Cannot run '{node_name}'")
                print(f"  Dependency '{dep_name}' has no usable data")
                print(f"  Run the flow again and say 'yes' to '{dep_name}'")
                sys.exit(1)

        # Archive existing data (if exists)
        output_dir = node.get_output_dir()
        pre_hash = None
        if output_dir and output_dir.exists() and any(output_dir.iterdir()):
            pre_hash = compute_directory_hash(output_dir)
            archive_existing_data(node, output_dir, context)

        # Execute node
        result = node.execute(context)

        if not result.success:
            print(f"ERROR: Node execution failed: {result.error_message}")
            sys.exit(1)

        # Archive new data if changed
        if output_dir and output_dir.exists():
            post_hash = compute_directory_hash(output_dir)
            if post_hash != pre_hash:
                archive_new_data(node, output_dir, context)
```

---

## Data Archiving System

### Archive Structure

```
data/apple/emails/                    # Current data (live)
data/apple/emails/archive/            # Historical archives
  2024-10-19_14-30-00_pre/            # Backup before execution
  2024-10-19_14-35-00_post/           # Audit after execution (if changed)
  2024-10-19_15-20-00_pre/            # Next run backup
  2024-10-19_15-25-00_post/           # Next run audit
```

### Archive Timing

1. **Before execution** (pre-archive):
   - Archive existing data if output_dir exists and has content
   - Creates backup in case execution fails

2. **After execution** (post-archive):
   - Archive new data only if it changed (hash comparison)
   - Creates audit trail of what was produced

### Change Detection

**Method:** SHA-256 hash of all files (recursive) in output directory

```python
def compute_directory_hash(directory: Path) -> str:
    """
    Compute SHA-256 hash of all files in directory.

    Ignores 'archive/' subdirectory to avoid recursion.
    """
    import hashlib

    hash_obj = hashlib.sha256()

    for file_path in sorted(directory.rglob("*")):
        if file_path.is_file() and "archive" not in file_path.parts:
            # Hash file path (relative)
            hash_obj.update(str(file_path.relative_to(directory)).encode())
            # Hash file contents
            hash_obj.update(file_path.read_bytes())

    return hash_obj.hexdigest()
```

### Archive Creation

```python
def archive_existing_data(node: FlowNode, output_dir: Path, context: FlowContext):
    """Archive existing data before execution."""
    try:
        archive_dir = output_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_path = archive_dir / f"{timestamp}_pre"

        shutil.copytree(output_dir, archive_path,
                      ignore=shutil.ignore_patterns('archive'))

        context.archive_manifest[f"{node.name}_pre"] = archive_path

    except Exception as e:
        print(f"\nERROR: Failed to archive existing data for '{node.name}'")
        print(f"  Reason: {e}")
        print(f"  Cannot proceed without backup - flow stopped")
        sys.exit(1)

def archive_new_data(node: FlowNode, output_dir: Path, context: FlowContext):
    """Archive new data after execution if changed."""
    try:
        archive_dir = output_dir / "archive"
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_path = archive_dir / f"{timestamp}_post"

        shutil.copytree(output_dir, archive_path,
                      ignore=shutil.ignore_patterns('archive'))

        context.archive_manifest[f"{node.name}_post"] = archive_path

    except Exception as e:
        print(f"\nERROR: Failed to archive new data for '{node.name}'")
        print(f"  Reason: {e}")
        print(f"  Data was produced but not archived - flow stopped")
        sys.exit(1)
```

### Archive Policy

- **Retention:** Keep all archives indefinitely (no automatic cleanup)
- **Cleanup:** User manually deletes old archives when needed
- **Future:** Could add `finances archive clean --older-than 90d` CLI command

---

## Error Handling

### Dependency Validation Failure

**When:** User says "yes" to a node but dependency has no usable data

**Action:** Error and stop entire flow immediately

```
ERROR: Cannot run 'apple_matching'
  Dependency 'apple_receipt_parsing' has no usable data
  Run the flow again and say 'yes' to 'apple_receipt_parsing'
```

### Node Execution Failure

**When:** Node execution returns `FlowResult(success=False)`

**Action:** Display error and stop flow

```
ERROR: Node execution failed: {result.error_message}
```

### Archive Failure

**When:** Archive operation fails (disk full, permission error, etc.)

**Action:** Stop flow immediately - archiving is critical for financial data

```
ERROR: Failed to archive existing data for 'ynab_sync'
  Reason: [Errno 28] No space left on device
  Cannot proceed without backup - flow stopped
```

### User Interruption

**When:** User presses Ctrl+C during execution

**Action:** Flow stops immediately, already-executed nodes have saved output

**Resume:** Next run will see existing data via `get_output_info()`

---

## Implementation Requirements

### All Nodes Must Implement

**1. get_output_info() → OutputInfo**

Each node must create a node-specific `OutputInfo` subclass that:
- Implements `is_data_ready()` - checks for what dependencies actually consume
- Implements `get_output_files()` - returns all files node produces

**2. get_output_dir() → Path** (if node has output)

Return the path to the node's output directory for archiving.
Return `None` if node has no persistent output.

**Example for all 11 nodes:**

- `AppleEmailFetchNode` → `data/apple/emails`
- `AppleReceiptParsingNode` → `data/apple/exports`
- `AppleMatchingFlowNode` → `data/apple/transaction_matches`
- `AmazonUnzipFlowNode` → `data/amazon/raw`
- `AmazonMatchingFlowNode` → `data/amazon/transaction_matches`
- `YnabSyncFlowNode` → `data/ynab/cache`
- `RetirementUpdateFlowNode` → `data/ynab/edits`
- `SplitGenerationFlowNode` → `data/ynab/edits`
- `CashFlowAnalysisFlowNode` → `data/cash_flow/charts`
- `AmazonOrderHistoryRequestFlowNode` → `None` (manual step, no output)
- `ynab_apply` (function node) → `None` (manual step, no output)

### Remove Unused Methods

**check_changes()** - No longer used, remove from all nodes (YAGNI principle)

---

## Testing Strategy

### Unit Tests

**File:** `tests/unit/test_core/test_output_info.py`

- Test `is_data_ready()` with various directory states (empty, partial, complete)
- Test `get_output_files()` returns correct file lists and counts
- Test edge cases (missing directory, zero files, etc.)

**File:** `tests/unit/test_core/test_flow_engine.py`

- Test `topological_sort_nodes()` with alphabetical tie-breaking
- Test dependency validation logic
- Test error messages when dependencies missing

### Integration Tests

**File:** `tests/integration/test_flow_engine.py`

- Test complete flow execution with mocked nodes
- Test archive creation and verification
- Test hash-based change detection
- Test resume scenario (some nodes have old data)

### E2E Tests

**File:** `tests/e2e/test_flow_system.py`

**Expected behavior:**
- Prompts for all 11 nodes in topological order (alphabetically within levels)
- Each prompt shows formatted status from `get_output_info()`
- Dependency validation blocks execution if dependency has no data
- Archives created before and after execution (if data changed)

---

## Migration Plan

### Phase 1: Add New Types (Non-Breaking)

**Files:**
- `src/finances/core/flow_node.py`

**Tasks:**
- Add `OutputFile` dataclass
- Add `OutputInfo` abstract class
- Add `get_output_info()` abstract method to `FlowNode`

**Result:** Code doesn't compile until nodes implement new method (mypy catches)

### Phase 2: Implement for All 11 Nodes

**Files:**
- `src/finances/apple/flow.py` (3 nodes)
- `src/finances/amazon/flow.py` (2 nodes)
- `src/finances/ynab/flow.py` (2 nodes)
- `src/finances/ynab/split_generation_flow.py` (1 node)
- `src/finances/analysis/flow.py` (1 node)

**Tasks:**
- Implement node-specific `OutputInfo` subclasses
- Write unit tests for each `OutputInfo` implementation

**Result:** All nodes satisfy abstract method requirement

### Phase 3: Update Flow Engine

**Files:**
- `src/finances/core/flow_engine.py`

**Tasks:**
- Add `topological_sort_nodes()` with alphabetical tie-breaking
- Add `compute_directory_hash()` for change detection
- Add `archive_existing_data()` and `archive_new_data()` functions
- Rewrite `execute_flow()` with prompt-validate-execute loop
- Remove old `find_ready_nodes()` method

**Result:** New execution model in place

### Phase 4: Update E2E Tests

**Files:**
- `tests/e2e/test_flow_system.py`

**Tasks:**
- Update test to expect 11 prompts in topological order
- Add dependency validation error test cases
- Add archive verification tests

**Result:** Tests verify new behavior

### Phase 5: Cleanup

**Tasks:**
- Remove `check_changes()` method from all nodes
- Remove any tests relying on old execution logic
- Run full test suite to verify everything works

**Result:** Clean codebase with no dead code

---

## Files Affected

**Core Infrastructure:**
- `src/finances/core/flow_node.py` - Add OutputFile, OutputInfo, get_output_info()
- `src/finances/core/flow_engine.py` - Rewrite execute_flow(), add archiving

**Domain Nodes:**
- `src/finances/apple/flow.py` - 3 nodes updated
- `src/finances/amazon/flow.py` - 2 nodes updated
- `src/finances/ynab/flow.py` - 2 nodes updated
- `src/finances/ynab/split_generation_flow.py` - 1 node updated
- `src/finances/analysis/flow.py` - 1 node updated
- `src/finances/cli/flow.py` - ynab_apply function node (2 nodes total)

**Tests:**
- `tests/unit/test_core/test_output_info.py` - New OutputInfo tests
- `tests/unit/test_core/test_flow_engine.py` - Update engine tests
- `tests/integration/test_flow_engine.py` - Add archiving tests
- `tests/e2e/test_flow_system.py` - Update execution order expectations

**Documentation:**
- `dev/specs/2025-09-24-financial-flow-system.md` - Update spec
- `dev/plans/2025-10-19-flow-execution-order-fix.md` - This document

---

## Benefits of This Design

1. **Correct execution order** - Topological sort guarantees dependencies run before dependents
2. **Type safety** - `OutputInfo` provides structured, type-checked output information
3. **User transparency** - User sees and controls every decision
4. **Data safety** - Automatic archiving before and after execution
5. **Simple validation** - Dependencies validated by data existence, not execution status
6. **Deterministic ordering** - Alphabetical tie-breaking ensures same order every time
7. **Clean code** - Removes unused `check_changes()` method (YAGNI)

---

## Success Criteria

- ☐ All 11 nodes prompt in correct topological order (alphabetically within levels)
- ☐ Dependency validation blocks execution if dependency has no data
- ☐ Dependency validation allows execution if dependency has old data
- ☐ Archives created before execution (if data exists)
- ☐ Archives created after execution (if data changed)
- ☐ Archive failure stops flow immediately
- ☐ All nodes implement `get_output_info()` with node-specific `OutputInfo` subclass
- ☐ All nodes implement `get_output_dir()` (or return None)
- ☐ `check_changes()` removed from all nodes
- ☐ All unit tests pass
- ☐ All integration tests pass
- ☐ All E2E tests pass
- ☐ Mypy passes with zero errors
