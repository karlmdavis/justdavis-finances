"""Typed operation models for the bank reconciliation apply pipeline."""

from dataclasses import dataclass
from typing import Any

from finances.bank_accounts.models import BankTransaction


@dataclass(frozen=True)
class CreateOp:
    """Create a new YNAB transaction from an unmatched bank transaction."""

    account_id: str
    transaction: BankTransaction
    import_id_seq: int = 0
    source: str = "bank"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "create_transaction",
            "source": self.source,
            "transaction": self.transaction.to_dict(),
            "account_id": self.account_id,
            "import_id_seq": self.import_id_seq,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CreateOp":
        return cls(
            account_id=d["account_id"],
            transaction=BankTransaction.from_dict(d["transaction"]),
            import_id_seq=d.get("import_id_seq", 0),
            source=d.get("source", "bank"),
        )


@dataclass(frozen=True)
class FlagOp:
    """Flag a bank transaction as ambiguous (multiple YNAB candidates)."""

    transaction: BankTransaction
    candidates: tuple[dict[str, Any], ...]
    message: str
    source: str = "bank"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "flag_discrepancy",
            "source": self.source,
            "transaction": self.transaction.to_dict(),
            "candidates": list(self.candidates),
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FlagOp":
        return cls(
            transaction=BankTransaction.from_dict(d["transaction"]),
            candidates=tuple(d.get("candidates", [])),
            message=d.get("message", "Multiple possible matches - manual review required"),
            source=d.get("source", "bank"),
        )


@dataclass(frozen=True)
class DeleteOp:
    """Delete an orphaned YNAB transaction within bank coverage."""

    transaction: dict[str, Any]  # Raw YNAB transaction dict from cache

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "delete_ynab_transaction",
            "transaction": self.transaction,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DeleteOp":
        return cls(transaction=d["transaction"])


Op = CreateOp | FlagOp | DeleteOp


def op_from_dict(d: dict[str, Any]) -> Op:
    """Deserialize an operation dict to its typed form."""
    op_type = d["type"]
    if op_type == "create_transaction":
        return CreateOp.from_dict(d)
    elif op_type == "flag_discrepancy":
        return FlagOp.from_dict(d)
    elif op_type == "delete_ynab_transaction":
        return DeleteOp.from_dict(d)
    else:
        raise ValueError(f"Unknown operation type: {op_type!r}")
