"""Central registry for bank export format handlers."""

from .apple_card_csv import AppleCardCsvHandler
from .apple_card_ofx import AppleCardOfxHandler
from .apple_savings_csv import AppleSavingsCsvHandler
from .apple_savings_ofx import AppleSavingsOfxHandler
from .base import BankExportFormatHandler
from .chase_checking_csv import ChaseCheckingCsvHandler
from .chase_credit_csv import ChaseCreditCsvHandler
from .chase_credit_qif import ChaseCreditQifHandler


class FormatHandlerRegistry:
    """Central registry for all bank export format handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, type[BankExportFormatHandler]] = {}

    def register(self, handler_class: type[BankExportFormatHandler]) -> None:
        """
        Register a format handler.

        Args:
            handler_class: Handler class to register (not instance)
        """
        self._handlers[handler_class.FORMAT_NAME] = handler_class

    def get(self, format_name: str) -> BankExportFormatHandler:
        """
        Get handler instance by format name.

        Args:
            format_name: Name of the format handler to retrieve

        Returns:
            New instance of the requested handler

        Raises:
            KeyError: If format_name is not registered
        """
        if format_name not in self._handlers:
            raise KeyError(f"Unknown format handler: {format_name}")

        handler_class = self._handlers[format_name]
        return handler_class()

    def list_formats(self) -> list[str]:
        """
        List all registered format names.

        Returns:
            List of registered format names
        """
        return list(self._handlers.keys())


def create_format_handler_registry() -> "FormatHandlerRegistry":
    """Create and populate format handler registry with all available handlers."""
    registry = FormatHandlerRegistry()
    registry.register(AppleCardCsvHandler)
    registry.register(AppleCardOfxHandler)
    registry.register(AppleSavingsCsvHandler)
    registry.register(AppleSavingsOfxHandler)
    registry.register(ChaseCheckingCsvHandler)
    registry.register(ChaseCreditCsvHandler)
    registry.register(ChaseCreditQifHandler)
    return registry
