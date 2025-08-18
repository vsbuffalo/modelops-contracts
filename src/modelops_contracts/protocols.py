"""Algorithm adapter protocol."""

from typing import Protocol
from .types import UniqueParameterSet, TrialResult


class AlgorithmAdapter(Protocol):
    """Protocol for optimization algorithms."""
    
    def ask(self, n: int) -> list[UniqueParameterSet]:
        """Request n parameter sets to evaluate."""
        ...
    
    def tell(self, results: list[TrialResult]) -> None:
        """Report evaluation results back to algorithm."""
        ...
    
    def finished(self) -> bool:
        """Check if optimization is complete."""
        ...


__all__ = ["AlgorithmAdapter"]