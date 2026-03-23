"""Flow node implementations for bank accounts domain."""

import re
from datetime import datetime
from pathlib import Path

from finances.bank_accounts.datastore import (
    BankNormalizedDataStore,
    BankReconciliationStore,
)
from finances.bank_accounts.models import BankAccountsConfig
from finances.bank_accounts.nodes.parse import parse_account_data
from finances.bank_accounts.nodes.reconcile import reconcile_account_data
from finances.bank_accounts.nodes.retrieve import retrieve_account_data
from finances.core.flow import (
    FlowContext,
    FlowNode,
    FlowResult,
    NodeDataSummary,
    OutputFile,
    OutputInfo,
)

_TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S"


class BankDataRetrieveOutputInfo(OutputInfo):
    """Validates that raw account data exists for configured accounts."""

    def __init__(self, output_dir: Path, config: BankAccountsConfig):
        self.output_dir = output_dir
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

    def get_output_files(self) -> list[OutputFile]:
        """Return all raw export files across all accounts."""
        files: list[OutputFile] = []
        for account in self.config.accounts:
            account_dir = self.output_dir / account.slug
            if account_dir.exists():
                files.extend(
                    OutputFile(path=file_path, record_count=1) for file_path in account_dir.glob("*")
                )
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

    def get_output_dir(self) -> Path | None:
        """Return output directory path."""
        return self.raw_dir

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Return summary of raw data status."""
        if not self.raw_dir.exists():
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=0,
                size_bytes=0,
                summary_text="No raw data found",
            )

        file_count = 0
        for account in self.config.accounts:
            account_dir = self.raw_dir / account.slug
            if account_dir.exists():
                file_count += len(list(account_dir.glob("*")))

        return NodeDataSummary(
            exists=file_count > 0,
            last_updated=None,
            age_days=None,
            item_count=file_count,
            size_bytes=None,
            summary_text=f"{file_count} raw files across {len(self.config.accounts)} accounts",
        )

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute retrieve operation."""
        try:
            # Call existing retrieve function with correct base directory
            stats = retrieve_account_data(self.config, self.data_dir / "bank_accounts")

            # Collect all output files for cleanup protection
            output_info = self.get_output_info()
            output_files = output_info.get_output_files()
            all_paths = [f.path for f in output_files]

            # Build summary
            total_copied = sum(acct["copied"] for acct in stats.values())
            total_skipped = sum(acct["skipped"] for acct in stats.values())

            if total_copied == 0 and total_skipped == 0:
                return FlowResult(
                    success=False,
                    error_message="No files found to retrieve",
                    outputs=all_paths,
                )

            return FlowResult(
                success=True,
                items_processed=total_copied + total_skipped,
                new_items=total_copied,
                outputs=all_paths,
                metadata={
                    "copied": total_copied,
                    "skipped": total_skipped,
                    "accounts": list(stats.keys()),
                },
            )

        except Exception as e:
            return FlowResult(
                success=False,
                error_message=f"Retrieve failed: {e}",
                outputs=[],
            )


class BankDataParseOutputInfo(OutputInfo):
    """Validates that normalized data exists."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Check if at least one normalized file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.json"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return all normalized JSON files with transaction counts."""
        if not self.output_dir.exists():
            return []

        files = []
        for json_file in self.output_dir.glob("*.json"):
            # Try to count transactions in file
            try:
                from finances.core.json_utils import read_json

                data = read_json(json_file)
                tx_count = len(data.get("transactions", []))
                files.append(OutputFile(path=json_file, record_count=tx_count))
            except Exception:
                files.append(OutputFile(path=json_file, record_count=0))

        return files


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

    def get_output_dir(self) -> Path | None:
        """Return output directory path."""
        return self.normalized_dir

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Return summary of normalized data."""
        if not self.store.exists():
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=0,
                size_bytes=0,
                summary_text="No normalized data",
            )

        return NodeDataSummary(
            exists=True,
            last_updated=self.store.last_modified(),
            age_days=self.store.age_days(),
            item_count=self.store.item_count(),
            size_bytes=self.store.size_bytes(),
            summary_text=self.store.summary_text(),
        )

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute parse operation."""
        try:
            # Import and create handler registry
            from finances.cli.bank_accounts import create_format_handler_registry

            handler_registry = create_format_handler_registry()

            # Call parse function (now returns ParseResult objects)
            parse_results = parse_account_data(self.config, self.data_dir / "bank_accounts", handler_registry)

            # Serialize and save each account's data with DataStore (Pattern C)
            new_files = []
            total_txs = 0
            for account_slug, result in parse_results.items():
                # Count transactions
                total_txs += len(result.transactions)

                # Serialize domain models to JSON
                data = {
                    "account_slug": account_slug,
                    "parsed_at": datetime.now().isoformat(),
                    "transactions": [tx.to_dict() for tx in result.transactions],
                    "balance_points": [bp.to_dict() for bp in result.balance_points],
                    "coverage_intervals": [
                        {"start_date": str(start), "end_date": str(end)}
                        for start, end in result.coverage_intervals
                    ],
                }

                # Use DataStore to create timestamped file
                output_file = self.store.save(account_slug, data)
                new_files.append(output_file)

            return FlowResult(
                success=True,
                items_processed=len(parse_results),
                new_items=len(new_files),
                outputs=new_files,  # Only protect newly created files; flow engine archives and cleans up old ones
                metadata={
                    "accounts_parsed": list(parse_results.keys()),
                    "total_transactions": total_txs,
                },
            )

        except Exception as e:
            # Protect existing files even on error
            output_info = self.get_output_info()
            output_files = output_info.get_output_files()
            all_paths = [f.path for f in output_files]

            return FlowResult(
                success=False,
                error_message=f"Parse failed: {e}",
                outputs=all_paths,
            )


class BankDataReconcileOutputInfo(OutputInfo):
    """Validates that reconciliation operations exist."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Check if at least one operations file exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*.json"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return all operations JSON files with account counts."""
        if not self.output_dir.exists():
            return []

        files = []
        for json_file in self.output_dir.glob("*.json"):
            # Try to count accounts in file
            try:
                from finances.core.json_utils import read_json

                data = read_json(json_file)
                acct_count = len(data.get("accounts", {}))
                files.append(OutputFile(path=json_file, record_count=acct_count))
            except Exception:
                files.append(OutputFile(path=json_file, record_count=0))

        return files


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

    def get_output_dir(self) -> Path | None:
        """Return output directory path."""
        return self.reconciliation_dir

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Return summary of reconciliation data."""
        if not self.store.exists():
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=0,
                size_bytes=0,
                summary_text="No reconciliation data",
            )

        return NodeDataSummary(
            exists=True,
            last_updated=self.store.last_modified(),
            age_days=self.store.age_days(),
            item_count=self.store.item_count(),
            size_bytes=self.store.size_bytes(),
            summary_text=self.store.summary_text(),
        )

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute reconcile operation."""
        try:
            # Load YNAB transactions from cache
            from datetime import datetime

            from finances.bank_accounts.matching import YnabTransaction
            from finances.core import FinancialDate, Money
            from finances.core.json_utils import read_json

            ynab_cache_dir = self.data_dir / "ynab" / "cache"
            transactions_file = ynab_cache_dir / "transactions.json"

            if not transactions_file.exists():
                return FlowResult(
                    success=False,
                    error_message="YNAB cache not found - run ynab_sync first",
                    outputs=[],
                )

            transactions_data = read_json(transactions_file)

            # Convert to bank_accounts.matching.YnabTransaction format.
            # Use FullYnabTransaction only to parse import_posted_date from import_id;
            # fall back to direct dict access for required fields (id may be absent in
            # test/minimal data, but from_dict requires it).
            ynab_transactions = []
            for tx in transactions_data:
                import_id = tx.get("import_id")
                import_posted_date = None
                if import_id and import_id.startswith("YNAB:"):
                    _DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
                    for part in import_id.split(":")[1:]:
                        if _DATE_RE.match(part):
                            import_posted_date = FinancialDate.from_string(part)
                            break
                ynab_transactions.append(
                    YnabTransaction(
                        date=FinancialDate.from_string(tx["date"]),
                        amount=Money.from_milliunits(tx["amount"]),
                        payee_name=tx.get("payee_name"),
                        memo=tx.get("memo"),
                        account_id=tx.get("account_id"),
                        is_transfer=tx.get("transfer_account_id") is not None,
                        id=tx.get("id"),
                        import_posted_date=import_posted_date,
                    )
                )

            # Build raw YNAB lookup by ID for delete op construction
            raw_ynab_by_id = {tx["id"]: tx for tx in transactions_data if "id" in tx}

            # Call reconcile function (now returns ReconciliationResult objects)
            reconcile_results = reconcile_account_data(
                self.config, self.data_dir / "bank_accounts", ynab_transactions, raw_ynab_by_id
            )

            # Serialize to JSON
            data = {
                "reconciled_at": datetime.now().isoformat(),
                "accounts": {slug: result.to_dict() for slug, result in reconcile_results.items()},
            }

            # Use DataStore to create timestamped file
            output_file = self.store.save(data)

            # Check for divergences from results
            reconciled_count = sum(
                1 for r in reconcile_results.values() if r.reconciliation.last_reconciled_date is not None
            )
            diverged_count = sum(
                1 for r in reconcile_results.values() if r.reconciliation.first_diverged_date is not None
            )

            # Return warning if any accounts diverged
            if diverged_count > 0:
                return FlowResult(
                    success=True,
                    items_processed=len(reconcile_results),
                    new_items=1,
                    outputs=[
                        output_file
                    ],  # Only newly created file; flow engine archives and cleans up old ones
                    requires_review=True,
                    review_instructions=f"{diverged_count} account(s) have balance discrepancies",
                    metadata={
                        "reconciled": reconciled_count,
                        "diverged": diverged_count,
                        "output_file": str(output_file),
                    },
                )

            return FlowResult(
                success=True,
                items_processed=len(reconcile_results),
                new_items=1,
                outputs=[output_file],  # Only newly created file; flow engine archives and cleans up old ones
                metadata={
                    "reconciled": reconciled_count,
                    "diverged": diverged_count,
                    "output_file": str(output_file),
                },
            )

        except Exception as e:
            # Protect existing files even on error
            output_info = self.get_output_info()
            output_files = output_info.get_output_files()
            all_paths = [f.path for f in output_files]

            return FlowResult(
                success=False,
                error_message=f"Reconcile failed: {e}",
                outputs=all_paths,
            )


class BankDataReconcileApplyOutputInfo(OutputInfo):
    """Validates that apply log files exist."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Check if at least one apply log exists."""
        if not self.output_dir.exists():
            return False
        return len(list(self.output_dir.glob("*_apply_log.ndjson"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return all apply log NDJSON files."""
        if not self.output_dir.exists():
            return []
        return [OutputFile(path=f, record_count=1) for f in self.output_dir.glob("*.ndjson")]


class BankDataReconcileApplyFlowNode(FlowNode):
    """
    Interactive flow node for applying reconciliation operations.

    Reads from: data/bank_accounts/reconciliation/{latest}_operations.json
    Writes to:  data/bank_accounts/reconciliation_apply/{timestamp}_apply_log.ndjson
    Depends on: bank_data_reconcile
    """

    def __init__(self, data_dir: Path, config: BankAccountsConfig):
        super().__init__("bank_data_reconcile_apply")
        self._dependencies = {"bank_data_reconcile"}
        self.data_dir = data_dir
        self.config = config
        self.apply_dir = data_dir / "bank_accounts" / "reconciliation_apply"

    def get_output_info(self) -> OutputInfo:
        """Return output validation info."""
        return BankDataReconcileApplyOutputInfo(self.apply_dir)

    def get_output_dir(self) -> Path | None:
        """Return output directory path."""
        return self.apply_dir

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Return summary of pending operations from latest reconciliation file."""
        reconciliation_dir = self.data_dir / "bank_accounts" / "reconciliation"
        ops_files = (
            sorted(reconciliation_dir.glob("*_operations.json")) if reconciliation_dir.exists() else []
        )

        if not ops_files:
            return NodeDataSummary(
                exists=False,
                last_updated=None,
                age_days=None,
                item_count=0,
                size_bytes=0,
                summary_text="No reconciliation data — run bank_data_reconcile first",
            )

        latest = ops_files[-1]
        try:
            from finances.core.json_utils import read_json

            data = read_json(latest)
            accounts_data = data.get("accounts", {})
            creates = sum(
                sum(1 for op in acct.get("operations", []) if op.get("type") == "create_transaction")
                for acct in accounts_data.values()
            )
            flags = sum(
                sum(1 for op in acct.get("operations", []) if op.get("type") == "flag_discrepancy")
                for acct in accounts_data.values()
            )
            deletes = sum(
                sum(1 for op in acct.get("operations", []) if op.get("type") == "delete_ynab_transaction")
                for acct in accounts_data.values()
            )
            from finances.core import FinancialDate

            mtime = latest.stat().st_mtime
            last_modified = datetime.fromtimestamp(mtime)
            age = FinancialDate.today().age_days(
                FinancialDate.from_string(last_modified.strftime("%Y-%m-%d"))
            )
            return NodeDataSummary(
                exists=True,
                last_updated=last_modified,
                age_days=abs(age),
                item_count=creates + flags + deletes,
                size_bytes=latest.stat().st_size,
                summary_text=f"{creates} creates, {flags} flags, {deletes} deletes pending",
            )
        except Exception:
            return NodeDataSummary(
                exists=True,
                last_updated=None,
                age_days=None,
                item_count=0,
                size_bytes=0,
                summary_text="Could not read reconciliation data",
            )

    @property
    def requires_review(self) -> bool:
        """Always requires review — node is inherently interactive."""
        return True

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute interactive apply operation."""
        from finances.bank_accounts.nodes.apply import apply_reconciliation_operations

        # Find latest reconciliation ops file
        reconciliation_dir = self.data_dir / "bank_accounts" / "reconciliation"
        ops_files = (
            sorted(reconciliation_dir.glob("*_operations.json")) if reconciliation_dir.exists() else []
        )

        if not ops_files:
            return FlowResult(
                success=False,
                error_message="No reconciliation operations file found — run bank_data_reconcile first",
                outputs=[],
            )

        ops_file = ops_files[-1]
        timestamp = datetime.now().strftime(_TIMESTAMP_FMT)
        apply_log_path = self.apply_dir / f"{timestamp}_apply_log.ndjson"

        try:
            counts = apply_reconciliation_operations(ops_file, apply_log_path, self.config)

            return FlowResult(
                success=True,
                items_processed=counts["applied"]
                + counts["skipped"]
                + counts["acknowledged"]
                + counts["deleted"],
                new_items=counts["applied"],
                outputs=[apply_log_path],
                requires_review=False,
                metadata={
                    "applied": counts["applied"],
                    "skipped": counts["skipped"],
                    "acknowledged": counts["acknowledged"],
                    "deleted": counts["deleted"],
                    "log_file": str(apply_log_path),
                },
            )
        except Exception as e:
            return FlowResult(
                success=False,
                error_message=f"Apply failed: {e}",
                outputs=[apply_log_path] if apply_log_path.exists() else [],
            )
