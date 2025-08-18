"""Contract exceptions."""


class ContractViolationError(Exception):
    """Raised when contract invariants are violated."""
    pass


__all__ = ["ContractViolationError"]