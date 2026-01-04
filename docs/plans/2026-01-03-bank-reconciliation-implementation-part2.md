# Bank Account Reconciliation - Implementation Plan (Part 2)

**Continuation of:** `2026-01-03-bank-reconciliation-implementation.md`

**Tasks 11-20:** Configuration, Core Logic, Integration, and Testing

---

## Task 11: Configuration Models

**Files:**
- Modify: `src/finances/bank_accounts/models.py`
- Create: `tests/unit/test_bank_accounts/test_config_models.py`

**Step 1: Write failing tests for AccountConfig**

```python
# tests/unit/test_bank_accounts/test_config_models.py

import pytest
from finances.bank_accounts.models import AccountConfig, ImportPattern


def test_account_config_creation():
    """Test creating AccountConfig with all fields."""
    pattern = ImportPattern(
        pattern="Apple Card Transactions - *.csv",
        format_handler="apple_card_csv"
    )

    config = AccountConfig(
        ynab_account_id="uuid-123",
        ynab_account_name="Apple Card",
        slug="apple_card",
        bank_name="Apple",
        account_type="credit",
        statement_frequency="monthly",
        source_directory="/path/to/files",
        import_patterns=[pattern],
        download_instructions="Download from wallet.apple.com"
    )

    assert config.slug == "apple_card"
    assert len(config.import_patterns) == 1


def test_account_config_to_dict():
    """Test serialization to dict."""
    pattern = ImportPattern(
        pattern="*.csv",
        format_handler="test_csv"
    )

    config = AccountConfig(
        ynab_account_id="uuid-123",
        ynab_account_name="Test Account",
        slug="test",
        bank_name="Test Bank",
        account_type="checking",
        statement_frequency="daily",
        source_directory="/test",
        import_patterns=[pattern],
        download_instructions="Test instructions"
    )

    result = config.to_dict()

    assert result["slug"] == "test"
    assert result["import_patterns"][0]["pattern"] == "*.csv"


def test_account_config_from_dict():
    """Test deserialization from dict."""
    data = {
        "ynab_account_id": "uuid-123",
        "ynab_account_name": "Test",
        "slug": "test",
        "bank_name": "Test Bank",
        "account_type": "checking",
        "statement_frequency": "daily",
        "source_directory": "/test",
        "import_patterns": [
            {"pattern": "*.csv", "format_handler": "test_csv"}
        ],
        "download_instructions": "Test"
    }

    config = AccountConfig.from_dict(data)

    assert config.slug == "test"
    assert isinstance(config.import_patterns[0], ImportPattern)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_config_models.py::test_account_config_creation -v`

Expected: FAIL with "ImportError: cannot import name 'AccountConfig'"

**Step 3: Implement configuration models**

```python
# src/finances/bank_accounts/models.py (add to existing file)

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportPattern:
    """File import pattern with format handler."""

    pattern: str  # Glob pattern (e.g., "*.csv")
    format_handler: str  # Handler name from registry

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "format_handler": self.format_handler
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImportPattern":
        return cls(
            pattern=data["pattern"],
            format_handler=data["format_handler"]
        )


@dataclass(frozen=True)
class AccountConfig:
    """Configuration for a single bank account."""

    # Auto-filled from YNAB
    ynab_account_id: str
    ynab_account_name: str

    # User-provided
    slug: str
    bank_name: str
    account_type: str  # credit, checking, savings
    statement_frequency: str  # monthly, daily
    source_directory: str  # Where user downloads bank files
    import_patterns: tuple[ImportPattern, ...]  # Immutable sequence
    download_instructions: str

    def to_dict(self) -> dict:
        return {
            "ynab_account_id": self.ynab_account_id,
            "ynab_account_name": self.ynab_account_name,
            "slug": self.slug,
            "bank_name": self.bank_name,
            "account_type": self.account_type,
            "statement_frequency": self.statement_frequency,
            "source_directory": self.source_directory,
            "import_patterns": [p.to_dict() for p in self.import_patterns],
            "download_instructions": self.download_instructions
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AccountConfig":
        patterns = [ImportPattern.from_dict(p) for p in data["import_patterns"]]

        return cls(
            ynab_account_id=data["ynab_account_id"],
            ynab_account_name=data["ynab_account_name"],
            slug=data["slug"],
            bank_name=data["bank_name"],
            account_type=data["account_type"],
            statement_frequency=data["statement_frequency"],
            source_directory=data["source_directory"],
            import_patterns=tuple(patterns),
            download_instructions=data["download_instructions"]
        )


@dataclass(frozen=True)
class BankAccountsConfig:
    """Complete bank accounts configuration."""

    accounts: tuple[AccountConfig, ...]  # Immutable sequence

    def to_dict(self) -> dict:
        return {
            "accounts": [acc.to_dict() for acc in self.accounts]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BankAccountsConfig":
        accounts = [AccountConfig.from_dict(acc) for acc in data["accounts"]]
        return cls(accounts=tuple(accounts))

    @classmethod
    def empty(cls) -> "BankAccountsConfig":
        """Create empty config (no accounts configured)."""
        return cls(accounts=tuple())
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_config_models.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/finances/bank_accounts/models.py tests/unit/test_bank_accounts/test_config_models.py
git commit -m "feat(bank): add configuration models

- ImportPattern: file pattern with format handler
- AccountConfig: complete account configuration
- BankAccountsConfig: config file structure
- All immutable with to_dict/from_dict serialization
- Comprehensive unit tests for all models"
```

---

## Task 12: Configuration Loading and Validation

**Files:**
- Create: `src/finances/bank_accounts/config.py`
- Create: `tests/unit/test_bank_accounts/test_config.py`

**Step 1: Write failing tests**

```python
# tests/unit/test_bank_accounts/test_config.py

import pytest
from pathlib import Path
from finances.bank_accounts.config import (
    load_config,
    validate_config,
    generate_config_stub,
    ConfigValidationError
)
from finances.bank_accounts.models import BankAccountsConfig


def test_load_config_from_file(tmp_path):
    """Test loading valid config from file."""
    config_data = {
        "accounts": [
            {
                "ynab_account_id": "uuid-123",
                "ynab_account_name": "Test Account",
                "slug": "test",
                "bank_name": "Test Bank",
                "account_type": "checking",
                "statement_frequency": "daily",
                "source_directory": str(tmp_path),
                "import_patterns": [{"pattern": "*.csv", "format_handler": "test_csv"}],
                "download_instructions": "Test"
            }
        ]
    }

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data, indent=2))

    config = load_config(config_file)

    assert isinstance(config, BankAccountsConfig)
    assert len(config.accounts) == 1


def test_load_config_missing_file(tmp_path):
    """Test that missing config file raises FileNotFoundError."""
    config_file = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        load_config(config_file)


def test_validate_config_success(tmp_path):
    """Test validating a correct configuration."""
    config = BankAccountsConfig.from_dict({
        "accounts": [{
            "ynab_account_id": "uuid-123",
            "ynab_account_name": "Test",
            "slug": "test",
            "bank_name": "Test Bank",
            "account_type": "checking",
            "statement_frequency": "daily",
            "source_directory": str(tmp_path),
            "import_patterns": [{"pattern": "*.csv", "format_handler": "test_csv"}],
            "download_instructions": "Test"
        }]
    })

    # Should not raise
    validate_config(config, ynab_accounts={"uuid-123": "Test"}, available_handlers=["test_csv"])


def test_validate_config_duplicate_slug():
    """Test validation fails with duplicate slugs."""
    config = BankAccountsConfig.from_dict({
        "accounts": [
            {
                "ynab_account_id": "uuid-1",
                "ynab_account_name": "Account 1",
                "slug": "duplicate",
                "bank_name": "Bank 1",
                "account_type": "checking",
                "statement_frequency": "daily",
                "source_directory": "/path1",
                "import_patterns": [{"pattern": "*.csv", "format_handler": "test_csv"}],
                "download_instructions": "Test"
            },
            {
                "ynab_account_id": "uuid-2",
                "ynab_account_name": "Account 2",
                "slug": "duplicate",
                "bank_name": "Bank 2",
                "account_type": "savings",
                "statement_frequency": "monthly",
                "source_directory": "/path2",
                "import_patterns": [{"pattern": "*.csv", "format_handler": "test_csv"}],
                "download_instructions": "Test"
            }
        ]
    })

    with pytest.raises(ConfigValidationError, match="Duplicate slug: duplicate"):
        validate_config(config, ynab_accounts={}, available_handlers=["test_csv"])


def test_validate_config_invalid_ynab_account():
    """Test validation fails with invalid YNAB account ID."""
    config = BankAccountsConfig.from_dict({
        "accounts": [{
            "ynab_account_id": "invalid-uuid",
            "ynab_account_name": "Test",
            "slug": "test",
            "bank_name": "Test Bank",
            "account_type": "checking",
            "statement_frequency": "daily",
            "source_directory": "/path",
            "import_patterns": [{"pattern": "*.csv", "format_handler": "test_csv"}],
            "download_instructions": "Test"
        }]
    })

    with pytest.raises(ConfigValidationError, match="YNAB account ID not found"):
        validate_config(config, ynab_accounts={"uuid-123": "Other Account"}, available_handlers=["test_csv"])


def test_generate_config_stub():
    """Test generating config stub from YNAB accounts."""
    ynab_accounts = {
        "uuid-1": {"name": "Apple Card", "type": "creditCard"},
        "uuid-2": {"name": "Chase Checking", "type": "checking"}
    }

    stub = generate_config_stub(ynab_accounts)

    assert len(stub.accounts) == 2
    assert stub.accounts[0].slug == "TODO_REQUIRED"
    assert stub.accounts[0].ynab_account_id == "uuid-1"
    assert stub.accounts[1].account_type == "checking"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bank_accounts/test_config.py::test_load_config_from_file -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement config loading and validation**

```python
# src/finances/bank_accounts/config.py

import json
from pathlib import Path
from finances.bank_accounts.models import BankAccountsConfig, AccountConfig, ImportPattern
from finances.core.json_utils import read_json, write_json


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


def load_config(config_path: Path) -> BankAccountsConfig:
    """Load bank accounts configuration from JSON file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    data = read_json(config_path)
    return BankAccountsConfig.from_dict(data)


def validate_config(
    config: BankAccountsConfig,
    ynab_accounts: dict[str, str],
    available_handlers: list[str]
) -> None:
    """
    Validate bank accounts configuration.

    Raises:
        ConfigValidationError: If validation fails
    """
    slugs_seen = set()
    ynab_ids_seen = set()

    for account in config.accounts:
        # Check required fields are not TODO_REQUIRED
        if account.slug == "TODO_REQUIRED":
            raise ConfigValidationError(
                f"Account '{account.ynab_account_name}': slug must be set (currently TODO_REQUIRED)"
            )

        # Check slug uniqueness
        if account.slug in slugs_seen:
            raise ConfigValidationError(f"Duplicate slug: {account.slug}")
        slugs_seen.add(account.slug)

        # Check YNAB account ID uniqueness
        if account.ynab_account_id in ynab_ids_seen:
            raise ConfigValidationError(
                f"Account '{account.ynab_account_name}' configured multiple times"
            )
        ynab_ids_seen.add(account.ynab_account_id)

        # Check YNAB account exists
        if account.ynab_account_id not in ynab_accounts:
            raise ConfigValidationError(
                f"YNAB account ID not found: {account.ynab_account_id}. "
                f"Available accounts: {list(ynab_accounts.values())}"
            )

        # Check account_type is valid
        if account.account_type not in ("credit", "checking", "savings"):
            raise ConfigValidationError(
                f"Invalid account_type '{account.account_type}' for account '{account.slug}'. "
                f"Must be one of: credit, checking, savings"
            )

        # Check statement_frequency is valid
        if account.statement_frequency not in ("monthly", "daily"):
            raise ConfigValidationError(
                f"Invalid statement_frequency '{account.statement_frequency}' for account '{account.slug}'. "
                f"Must be one of: monthly, daily"
            )

        # Check source_directory exists
        source_dir = Path(account.source_directory).expanduser()
        if not source_dir.exists():
            raise ConfigValidationError(
                f"Source directory not found for account '{account.slug}': {account.source_directory}"
            )

        # Check import_patterns is not empty
        if not account.import_patterns:
            raise ConfigValidationError(
                f"At least one import pattern required for account '{account.slug}'"
            )

        # Check format handlers exist
        for pattern in account.import_patterns:
            if pattern.format_handler not in available_handlers:
                raise ConfigValidationError(
                    f"Unknown format handler '{pattern.format_handler}' for account '{account.slug}'. "
                    f"Available handlers: {available_handlers}"
                )


def generate_config_stub(ynab_accounts: dict[str, dict]) -> BankAccountsConfig:
    """
    Generate config stub from YNAB accounts.

    Args:
        ynab_accounts: Dict of {account_id: {"name": ..., "type": ...}}

    Returns:
        BankAccountsConfig with stub data
    """
    stub_accounts = []

    for account_id, account_data in ynab_accounts.items():
        # Infer account_type from YNAB type
        ynab_type = account_data["type"]
        if ynab_type == "creditCard":
            account_type = "credit"
        elif ynab_type == "checking":
            account_type = "checking"
        elif ynab_type == "savings":
            account_type = "savings"
        else:
            account_type = "TODO_REQUIRED"

        stub = AccountConfig(
            ynab_account_id=account_id,
            ynab_account_name=account_data["name"],
            slug="TODO_REQUIRED",
            bank_name="TODO_REQUIRED",
            account_type=account_type,
            statement_frequency="TODO_REQUIRED",
            source_directory="TODO_REQUIRED",
            import_patterns=tuple(),
            download_instructions="TODO_REQUIRED"
        )

        stub_accounts.append(stub)

    return BankAccountsConfig(accounts=tuple(stub_accounts))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bank_accounts/test_config.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/finances/bank_accounts/config.py tests/unit/test_bank_accounts/test_config.py
git commit -m "feat(bank): add configuration loading and validation

- load_config: load from JSON file
- validate_config: comprehensive validation rules
- generate_config_stub: create stub from YNAB accounts
- ConfigValidationError: validation error exception
- Unit tests for all validation rules and edge cases"
```

---

## Task 13: De-duplication Logic

**Files:**
- Create: `src/finances/bank_accounts/deduplication.py`
- Create: `tests/unit/test_bank_accounts/test_deduplication.py`

**Step 1: Write failing tests**

```python
def test_deduplicate_transactions_by_date():
    """Test deduplication keeps most recent file per date."""
    # File 1: older (2024-12-01 transactions)
    # File 2: newer (2024-12-01 transactions - should win)

def test_deduplicate_preserves_non_overlapping_dates():
    """Test that non-overlapping dates from all files are kept."""

def test_deduplicate_same_file_not_duplicates():
    """Test identical transactions in same file are NOT duplicates."""
```

**Step 2: Implement de-duplication**

Key algorithm:
```python
def deduplicate_transactions(
    file_results: list[tuple[Path, ParseResult, float]]  # (path, result, mtime)
) -> list[BankTransaction]:
    """
    Deduplicate transactions across files.

    Strategy: For each date, use transactions from most recent file (by mtime).
    """
    # Group by (date, file_path)
    by_date_file = defaultdict(list)
    for file_path, result, mtime in file_results:
        for tx in result.transactions:
            key = (tx.posted_date, file_path)
            by_date_file[key].append((tx, mtime))

    # For each date, select file with latest mtime
    final_txs = []
    by_date = defaultdict(list)
    for (date, file_path), txs in by_date_file.items():
        by_date[date].append((file_path, txs[0][1], txs))  # (path, mtime, transactions)

    for date, file_groups in by_date.items():
        # Select file with latest mtime for this date
        latest_file = max(file_groups, key=lambda x: x[1])
        final_txs.extend([tx for tx, _ in latest_file[2]])

    return sorted(final_txs, key=lambda tx: tx.posted_date)
```

**Step 3: Commit**

```bash
git commit -m "feat(bank): add transaction de-duplication logic

- Deduplicates by date using most recent file (mtime)
- Preserves all transactions within same file
- Maintains chronological order
- Comprehensive unit tests with overlapping files"
```

---

## Task 14: account_data_retrieve Flow Node

**Files:**
- Create: `src/finances/bank_accounts/nodes/retrieve.py`
- Create: `tests/integration/test_bank_accounts/test_retrieve_node.py`

**Step 1: Write integration test**

```python
def test_retrieve_copies_matching_files(tmp_path):
    """Test retrieve node copies files matching patterns."""
    # Setup: source directory with files
    # Config: patterns to match
    # Execute: retrieve node
    # Assert: files copied to raw/{slug}/

def test_retrieve_skips_existing_files(tmp_path):
    """Test that existing files with same name/size are skipped."""

def test_retrieve_fails_on_missing_source_dir(tmp_path):
    """Test that missing source directory fails with clear error."""
```

**Step 2: Implement retrieve node**

Key logic:
```python
def retrieve_account_data(config: BankAccountsConfig, base_dir: Path) -> dict:
    """
    Copy bank export files from source to raw directory.

    Returns:
        Summary dict with files_copied, files_skipped per account
    """
    summary = {}

    for account in config.accounts:
        source_dir = Path(account.source_directory).expanduser()
        dest_dir = base_dir / "raw" / account.slug
        dest_dir.mkdir(parents=True, exist_ok=True)

        files_copied = []
        files_skipped = []

        for pattern_config in account.import_patterns:
            # Find matching files
            matching_files = list(source_dir.glob(pattern_config.pattern))

            for src_file in matching_files:
                dest_file = dest_dir / src_file.name

                # Skip if exists with same size
                if dest_file.exists() and dest_file.stat().st_size == src_file.stat().st_size:
                    files_skipped.append(src_file.name)
                else:
                    shutil.copy2(src_file, dest_file)
                    files_copied.append(src_file.name)

        summary[account.slug] = {
            "files_copied": len(files_copied),
            "files_skipped": len(files_skipped)
        }

    return summary
```

**Step 3: Commit**

```bash
git commit -m "feat(bank): add account_data_retrieve flow node

- Copies files from source_directory to raw/{slug}/
- Matches files using glob patterns from config
- Skips files already copied (same name + size)
- Returns summary of files copied/skipped per account
- Integration tests with temporary directories"
```

---

## Task 15: account_data_parse Flow Node

**Files:**
- Create: `src/finances/bank_accounts/nodes/parse.py`
- Create: `tests/integration/test_bank_accounts/test_parse_node.py`

**Step 1: Write integration test**

```python
def test_parse_creates_normalized_json(tmp_path):
    """Test parse node creates normalized JSON from raw files."""
    # Setup: raw files with known content
    # Execute: parse node
    # Assert: normalized/{slug}.json exists with correct structure

def test_parse_deduplicates_overlapping_files(tmp_path):
    """Test that overlapping date ranges are deduplicated."""

def test_parse_auto_detects_date_range(tmp_path):
    """Test that data_period is auto-detected from transactions."""
```

**Step 2: Implement parse node**

Key logic:
```python
def parse_account_data(
    config: BankAccountsConfig,
    base_dir: Path,
    handler_registry: FormatHandlerRegistry
) -> dict:
    """
    Parse raw bank files into normalized JSON format.

    Returns:
        Summary dict with transaction_count, date_range per account
    """
    summary = {}

    for account in config.accounts:
        raw_dir = base_dir / "raw" / account.slug
        normalized_file = base_dir / "normalized" / f"{account.slug}.json"
        normalized_file.parent.mkdir(parents=True, exist_ok=True)

        # Parse all files
        file_results = []
        for raw_file in raw_dir.iterdir():
            # Match against import_patterns to get format_handler
            handler_name = find_format_handler(raw_file, account.import_patterns)
            if not handler_name:
                continue

            handler = handler_registry.get(handler_name)
            result = handler.parse(raw_file)
            mtime = raw_file.stat().st_mtime

            file_results.append((raw_file, result, mtime))

        # De-duplicate transactions
        all_transactions = deduplicate_transactions(file_results)
        all_balances = deduplicate_balances(file_results)

        # Auto-detect date range
        dates = [tx.posted_date for tx in all_transactions]
        data_period_start = min(dates) if dates else None
        data_period_end = max(dates) if dates else None

        # Create normalized format
        normalized_data = {
            "account_id": account.slug,
            "account_name": account.ynab_account_name,
            "account_type": account.account_type,
            "data_period": {
                "start_date": str(data_period_start),
                "end_date": str(data_period_end)
            },
            "balances": [b.to_dict() for b in all_balances],
            "transactions": [tx.to_dict() for tx in all_transactions]
        }

        write_json(normalized_file, normalized_data)

        summary[account.slug] = {
            "transaction_count": len(all_transactions),
            "date_range": f"{data_period_start} to {data_period_end}"
        }

    return summary
```

**Step 3: Commit**

```bash
git commit -m "feat(bank): add account_data_parse flow node

- Parses raw files using format handlers from registry
- De-duplicates transactions across overlapping files
- Auto-detects date range from transaction content
- Writes normalized JSON to normalized/{slug}.json
- Integration tests with multiple file formats"
```

---

## Task 16: Transaction Matching Algorithm

**Files:**
- Create: `src/finances/bank_accounts/matching.py`
- Create: `tests/unit/test_bank_accounts/test_matching.py`

**Step 1: Write unit tests**

```python
def test_exact_match_single():
    """Test matching with unique date+amount match."""
    bank_tx = BankTransaction(date="2024-12-15", amount=-1000, description="SAFEWAY")
    ynab_txs = [YnabTransaction(date="2024-12-15", amount=-1000, payee="Safeway")]

    matches = find_matches(bank_tx, ynab_txs)
    assert matches.match_type == "exact"
    assert matches.ynab_transaction == ynab_txs[0]

def test_fuzzy_match_multiple():
    """Test fuzzy matching when multiple YNAB txs have same date+amount."""
    bank_tx = BankTransaction(date="2024-12-15", amount=-5000, description="AMAZON MKTPL")
    ynab_txs = [
        YnabTransaction(date="2024-12-15", amount=-5000, payee="Amazon"),
        YnabTransaction(date="2024-12-15", amount=-5000, payee="Grocery Store")
    ]

    matches = find_matches(bank_tx, ynab_txs)
    assert matches.match_type == "fuzzy"
    assert matches.similarity_score > 0.8

def test_no_match():
    """Test when no YNAB transaction matches."""
    bank_tx = BankTransaction(date="2024-12-15", amount=-1000, description="SAFEWAY")
    ynab_txs = []

    matches = find_matches(bank_tx, ynab_txs)
    assert matches.match_type == "none"
```

**Step 2: Implement matching algorithm**

Key algorithm:
```python
def find_matches(
    bank_tx: BankTransaction,
    ynab_txs: list[YnabTransaction]
) -> MatchResult:
    """
    Find YNAB transaction matching bank transaction.

    Strategy:
    1. Filter YNAB txs by exact date + amount
    2. If unique match → return exact match
    3. If multiple matches → fuzzy match by description similarity
    4. If no matches → return none
    """
    # Filter by date + amount
    candidates = [
        tx for tx in ynab_txs
        if tx.date == bank_tx.posted_date and tx.amount == bank_tx.amount
    ]

    if len(candidates) == 0:
        return MatchResult(match_type="none")

    if len(candidates) == 1:
        return MatchResult(
            match_type="exact",
            ynab_transaction=candidates[0],
            confidence=1.0
        )

    # Multiple candidates - fuzzy match by description
    scores = []
    for ynab_tx in candidates:
        # Normalize descriptions
        bank_desc = normalize_description(bank_tx.description)
        ynab_desc = normalize_description(ynab_tx.payee_name or ynab_tx.memo or "")

        # Calculate similarity
        score = SequenceMatcher(None, bank_desc, ynab_desc).ratio()
        scores.append((ynab_tx, score))

    best_match, best_score = max(scores, key=lambda x: x[1])

    if best_score > 0.8:
        return MatchResult(
            match_type="fuzzy",
            ynab_transaction=best_match,
            confidence=best_score
        )
    else:
        return MatchResult(
            match_type="ambiguous",
            candidates=candidates,
            similarity_scores=[s for _, s in scores]
        )


def normalize_description(text: str) -> str:
    """Normalize description for fuzzy matching."""
    # Lowercase, remove numbers, normalize spaces
    text = text.lower()
    text = re.sub(r'\d+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
```

**Step 3: Commit**

```bash
git commit -m "feat(bank): add transaction matching algorithm

- Exact matching by date + amount (unique)
- Fuzzy matching with SequenceMatcher (0.8 threshold)
- Description normalization for matching
- Returns match_type and confidence score
- Comprehensive unit tests for all match scenarios"
```

---

## Task 17: Balance Reconciliation Logic

**Files:**
- Create: `src/finances/bank_accounts/balance_reconciliation.py`
- Create: `tests/unit/test_bank_accounts/test_balance_reconciliation.py`

**Step 1: Write unit tests**

```python
def test_balance_reconciliation_exact_match():
    """Test reconciliation when balances match exactly."""
    bank_balance = Money.from_cents(100000)
    ynab_balance = Money.from_cents(100000)
    unmatched_bank = Money.from_cents(0)
    unmatched_ynab = Money.from_cents(0)

    point = reconcile_balance_point(date, bank_balance, ynab_balance, unmatched_bank, unmatched_ynab)

    assert point.is_reconciled is True
    assert point.difference == Money.from_cents(0)

def test_balance_reconciliation_with_adjustments():
    """Test reconciliation with missing transactions adjustment."""
    bank_balance = Money.from_cents(100000)
    ynab_balance = Money.from_cents(95000)
    unmatched_bank = Money.from_cents(-5000)  # Missing expense

    point = reconcile_balance_point(date, bank_balance, ynab_balance, unmatched_bank, Money.from_cents(0))

    assert point.adjusted_bank_balance == Money.from_cents(95000)
    assert point.is_reconciled is True
```

**Step 2: Implement balance reconciliation**

Key logic:
```python
def reconcile_balance_point(
    date: FinancialDate,
    bank_balance: Money,
    ynab_balance: Money,
    bank_txs_not_in_ynab: Money,  # Sum of unmatched bank txs
    ynab_txs_not_in_bank: Money   # Sum of unmatched YNAB txs
) -> BalanceReconciliationPoint:
    """
    Reconcile balances at a single date.

    Formula:
        Adjusted Bank = Bank + sum(bank_txs_not_in_ynab)
        Adjusted YNAB = YNAB + sum(ynab_txs_not_in_bank)
        Difference = Adjusted Bank - Adjusted YNAB
        Reconciled = (Difference == 0)
    """
    adjusted_bank = bank_balance + bank_txs_not_in_ynab
    adjusted_ynab = ynab_balance + ynab_txs_not_in_bank
    difference = adjusted_bank - adjusted_ynab

    return BalanceReconciliationPoint(
        date=date,
        bank_balance=bank_balance,
        ynab_balance=ynab_balance,
        bank_txs_not_in_ynab=bank_txs_not_in_ynab,
        ynab_txs_not_in_bank=ynab_txs_not_in_bank,
        adjusted_bank_balance=adjusted_bank,
        adjusted_ynab_balance=adjusted_ynab,
        is_reconciled=(difference == Money.from_cents(0)),
        difference=difference
    )


def build_balance_reconciliation(
    account_id: str,
    balance_points: list[BalancePoint],
    ynab_balances: dict[FinancialDate, Money],
    unmatched_bank_txs: list[BankTransaction],
    unmatched_ynab_txs: list[YnabTransaction]
) -> BalanceReconciliation:
    """Build complete balance reconciliation history."""
    points = []

    for balance_point in balance_points:
        date = balance_point.date
        ynab_balance = ynab_balances.get(date, Money.from_cents(0))

        # Sum unmatched transactions up to this date
        bank_sum = sum(
            (tx.amount for tx in unmatched_bank_txs if tx.posted_date <= date),
            Money.from_cents(0)
        )
        ynab_sum = sum(
            (tx.amount for tx in unmatched_ynab_txs if tx.date <= date),
            Money.from_cents(0)
        )

        point = reconcile_balance_point(
            date, balance_point.amount, ynab_balance, bank_sum, ynab_sum
        )
        points.append(point)

    # Find last reconciled and first diverged
    last_reconciled = None
    first_diverged = None

    for point in points:
        if point.is_reconciled:
            last_reconciled = point.date
        elif first_diverged is None:
            first_diverged = point.date

    return BalanceReconciliation(
        account_id=account_id,
        points=tuple(points),
        last_reconciled_date=last_reconciled,
        first_diverged_date=first_diverged
    )
```

**Step 3: Commit**

```bash
git commit -m "feat(bank): add balance reconciliation logic

- reconcile_balance_point: calculate adjusted balances
- build_balance_reconciliation: create full history
- Tracks last reconciled and first diverged dates
- Exact match requirement (no tolerance)
- Comprehensive unit tests for reconciliation scenarios"
```

---

## Task 18: account_data_reconcile Flow Node

**Files:**
- Create: `src/finances/bank_accounts/nodes/reconcile.py`
- Create: `tests/integration/test_bank_accounts/test_reconcile_node.py`

**Step 1: Write integration test**

```python
def test_reconcile_generates_operations(tmp_path):
    """Test reconcile node generates unified operations."""
    # Setup: normalized bank data + YNAB cache
    # Execute: reconcile node
    # Assert: operations JSON created with create_transaction ops

def test_reconcile_matches_transactions_both_ways(tmp_path):
    """Test both bank→YNAB and YNAB→bank matching."""

def test_reconcile_builds_balance_history(tmp_path):
    """Test balance reconciliation history in output."""
```

**Step 2: Implement reconcile node**

Orchestrates matching and balance reconciliation:
```python
def reconcile_account_data(
    config: BankAccountsConfig,
    base_dir: Path,
    ynab_cache_dir: Path
) -> Path:
    """
    Reconcile bank data with YNAB transactions.

    Returns:
        Path to generated operations JSON file
    """
    # Load YNAB data
    ynab_transactions = load_ynab_transactions(ynab_cache_dir)
    ynab_accounts = load_ynab_accounts(ynab_cache_dir)

    all_operations = []
    balance_reconciliations = {}

    for account in config.accounts:
        # Load normalized bank data
        normalized_file = base_dir / "normalized" / f"{account.slug}.json"
        bank_account = BankAccount.from_normalized_file(normalized_file)

        # Get YNAB transactions for this account
        account_ynab_txs = [
            tx for tx in ynab_transactions
            if tx.account_id == account.ynab_account_id
        ]

        # Match transactions (both directions)
        matches_bank_to_ynab = match_all_transactions(bank_account.transactions, account_ynab_txs)
        matches_ynab_to_bank = match_all_transactions(account_ynab_txs, bank_account.transactions)

        # Generate operations
        for bank_tx, match_result in matches_bank_to_ynab.items():
            if match_result.match_type == "none":
                op = create_transaction_operation(bank_tx, account)
                all_operations.append(op)
            elif match_result.match_type == "ambiguous":
                op = flag_discrepancy_operation(bank_tx, match_result)
                all_operations.append(op)

        for ynab_tx, match_result in matches_ynab_to_bank.items():
            if match_result.match_type == "none":
                op = flag_ynab_not_in_bank_operation(ynab_tx)
                all_operations.append(op)

        # Balance reconciliation
        balance_recon = build_balance_reconciliation(
            account.slug,
            bank_account.balances,
            ynab_balances,
            unmatched_bank_txs,
            unmatched_ynab_txs
        )
        balance_reconciliations[account.slug] = balance_recon

    # Write unified operations file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = base_dir / "reconciliation" / f"{timestamp}_reconciliation.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "version": "1.0",
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "source_system": "bank_reconciliation"
        },
        "operations": [op.to_dict() for op in all_operations],
        "summary": generate_summary(all_operations, balance_reconciliations)
    }

    write_json(output_file, output_data)

    return output_file
```

**Step 3: Commit**

```bash
git commit -m "feat(bank): add account_data_reconcile flow node

- Matches transactions in both directions
- Generates create_transaction operations for missing txs
- Generates flag_discrepancy for ambiguous/extra txs
- Builds balance reconciliation history
- Writes unified operations JSON with metadata
- Integration tests with complete reconciliation scenarios"
```

---

## Task 19: E2E Tests for Complete Flow

**Files:**
- Create: `tests/e2e/test_bank_accounts/test_complete_flow.py`

**Step 1: Write E2E test**

```python
def test_complete_bank_reconciliation_flow(tmp_path):
    """
    Test complete flow: retrieve → parse → reconcile.

    Setup:
    - Synthetic bank export files (CSV + OFX)
    - Config file with account configuration
    - YNAB cache with test data

    Execute:
    - retrieve: Copy files to raw/
    - parse: Create normalized JSON
    - reconcile: Generate operations JSON

    Assert:
    - Operations file exists
    - Contains expected create_transaction ops
    - Balance reconciliation in summary
    """
    # Create test data
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    # Write synthetic bank files
    write_apple_card_csv(source_dir / "transactions.csv")
    write_apple_card_ofx(source_dir / "transactions.ofx")

    # Create config
    config_data = create_test_config(source_dir)
    config_file = tmp_path / "config.json"
    write_json(config_file, config_data)

    # Create YNAB cache
    ynab_dir = tmp_path / "ynab_cache"
    create_ynab_cache(ynab_dir)

    # Run flow
    base_dir = tmp_path / "bank_accounts"

    # Step 1: Retrieve
    config = load_config(config_file)
    retrieve_summary = retrieve_account_data(config, base_dir)
    assert retrieve_summary["apple_card"]["files_copied"] == 2

    # Step 2: Parse
    parse_summary = parse_account_data(config, base_dir, registry)
    assert parse_summary["apple_card"]["transaction_count"] > 0

    # Step 3: Reconcile
    operations_file = reconcile_account_data(config, base_dir, ynab_dir)
    assert operations_file.exists()

    # Verify operations
    operations_data = read_json(operations_file)
    assert operations_data["version"] == "1.0"
    assert len(operations_data["operations"]) > 0
    assert "balance_reconciliation" in operations_data["summary"]
```

**Step 2: Commit**

```bash
git commit -m "test(bank): add E2E tests for complete flow

- Tests full retrieve → parse → reconcile pipeline
- Uses synthetic bank export files (CSV + OFX)
- Verifies operations JSON structure and content
- Tests balance reconciliation in summary
- Ensures end-to-end integration works correctly"
```

---

## Task 20: CLI Integration and Documentation

**Files:**
- Create: `src/finances/cli/bank_accounts.py`
- Modify: `src/finances/cli/main.py`
- Create: `docs/bank-accounts-reconciliation.md`

**Step 1: Implement CLI commands**

```python
# src/finances/cli/bank_accounts.py

import click
from finances.bank_accounts.config import load_config
from finances.bank_accounts.nodes.retrieve import retrieve_account_data
from finances.bank_accounts.nodes.parse import parse_account_data
from finances.bank_accounts.nodes.reconcile import reconcile_account_data


@click.group()
def bank_accounts():
    """Bank account reconciliation commands."""
    pass


@bank_accounts.command()
def retrieve():
    """Copy bank export files from source directories."""
    config = load_config(CONFIG_PATH)
    summary = retrieve_account_data(config, BASE_DIR)

    click.echo("✅ account_data_retrieve completed\n")
    for account_id, stats in summary.items():
        click.echo(f"{account_id}:")
        click.echo(f"  Files copied: {stats['files_copied']}")
        click.echo(f"  Files skipped: {stats['files_skipped']}")


@bank_accounts.command()
def parse():
    """Parse raw bank files into normalized JSON."""
    config = load_config(CONFIG_PATH)
    summary = parse_account_data(config, BASE_DIR, HANDLER_REGISTRY)

    click.echo("✅ account_data_parse completed\n")
    for account_id, stats in summary.items():
        click.echo(f"{account_id}:")
        click.echo(f"  Transactions: {stats['transaction_count']}")
        click.echo(f"  Date range: {stats['date_range']}")


@bank_accounts.command()
def reconcile():
    """Reconcile bank data with YNAB transactions."""
    config = load_config(CONFIG_PATH)
    operations_file = reconcile_account_data(config, BASE_DIR, YNAB_CACHE_DIR)

    click.echo(f"✅ account_data_reconcile completed")
    click.echo(f"\nOperations written to: {operations_file}")
```

**Step 2: Add to main CLI**

```python
# src/finances/cli/main.py

from finances.cli.bank_accounts import bank_accounts

cli.add_command(bank_accounts, name="bank")
```

**Step 3: Write documentation**

Create `docs/bank-accounts-reconciliation.md` with:
- Overview of reconciliation system
- Configuration setup guide
- Usage examples for each command
- Troubleshooting common issues

**Step 4: Commit**

```bash
git commit -m "feat(bank): add CLI integration and documentation

- CLI commands: finances bank retrieve/parse/reconcile
- Integrated with main finances CLI
- User-friendly output with summaries
- Complete documentation in docs/bank-accounts-reconciliation.md
- Usage examples and troubleshooting guide"
```

---

## Execution Plan Summary

**Total Tasks:** 20

**Grouped by Phase:**

**Phase 1: Foundation (Tasks 1-3)**
- Package structure and base models
- Format handler architecture and registry

**Phase 2: Format Handlers (Tasks 4-10)**
- 7 handlers for all bank account formats
- CSV, OFX, and QIF parsing

**Phase 3: Configuration (Tasks 11-12)**
- Config models and validation
- Stub generation and loading

**Phase 4: Core Logic (Tasks 13-17)**
- De-duplication algorithm
- Flow nodes (retrieve, parse)
- Transaction matching and balance reconciliation

**Phase 5: Integration (Tasks 18-20)**
- Reconcile flow node
- E2E tests
- CLI integration and docs

**Estimated Time:** 3-5 days for experienced developer (20-40 hours)

**Critical Path:**
1. Complete foundation (Tasks 1-3)
2. Implement at least one format handler to test architecture (Task 4)
3. Build configuration system (Tasks 11-12)
4. Implement core matching logic (Task 16)
5. Integrate flow nodes (Tasks 14-15, 18)
6. E2E testing (Task 19)

---

## Plan Complete!

The implementation plan is now complete with all 20 tasks detailed. Each task follows TDD principles:
1. Write failing test
2. Verify failure
3. Implement minimal code
4. Verify pass
5. Commit

Ready to execute with `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
