"""Core contract types."""

import math
import json
import hashlib
import enum
from dataclasses import dataclass, field
from typing import Mapping, Any
from collections.abc import Mapping as MappingABC
from types import MappingProxyType

from .errors import ContractViolationError

# Type definitions
Scalar = bool | int | float | str

# Constants
MAX_DIAG_BYTES = 65536  # 64KB limit for diagnostics to prevent unbounded growth


class TrialStatus(enum.Enum):
    """Status of a trial evaluation (MVP subset).
    
    Future additions may include:
    - PRUNED: for early stopping by algorithms
    - INFEASIBLE: for constraint violations
    - PENDING/LEASED: for non-terminal states
    """
    COMPLETED = "completed"  # Successfully evaluated
    FAILED = "failed"        # Generic failure
    TIMEOUT = "timeout"      # Exceeded time limit


def _canon_scalar(v: Any) -> Scalar:
    """Canonicalize scalar value, rejecting unsupported types."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ContractViolationError(f"Non-finite float in params: {v}")
        return v
    if isinstance(v, str):
        return v
    raise ContractViolationError(f"Non-scalar param type: {type(v).__name__}")


def make_param_id(params: dict) -> str:
    """Generate stable parameter ID.
    
    Uses provenance module for consistency.
    """
    from .provenance import make_param_id as _make_param_id
    return _make_param_id(params)


def _approx_size(obj: Mapping[str, Any]) -> int:
    """Approximate JSON size of object."""
    try:
        return len(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
    except Exception:
        raise ContractViolationError("diagnostics must be JSON-serializable")


@dataclass(frozen=True)
class UniqueParameterSet:
    """Immutable parameter set with stable ID."""
    params: Mapping[str, Scalar]
    param_id: str
    
    def __post_init__(self):
        if not self.param_id:
            raise ContractViolationError("param_id must be non-empty")
        
        # Freeze params: copy to dict (to normalize) then wrap with mapping proxy
        frozen = MappingProxyType(dict(self.params))
        object.__setattr__(self, "params", frozen)
        
        # Validate parameter types and values
        for key, value in frozen.items():
            if not isinstance(value, (float, int, str, bool)):
                raise ContractViolationError(
                    f"Parameter {key} has invalid type {type(value).__name__}"
                )
            if isinstance(value, float) and not math.isfinite(value):
                raise ContractViolationError(
                    f"Parameter {key} has non-finite value: {value}"
                )
    
    @classmethod
    def from_dict(cls, params: dict) -> 'UniqueParameterSet':
        """Create with auto-generated param_id."""
        return cls(params=params, param_id=make_param_id(params))


@dataclass(frozen=True)
class SeedInfo:
    """Seed configuration for reproducibility."""
    base_seed: int
    trial_seed: int
    replicate_seeds: tuple[int, ...]
    
    def __post_init__(self):
        # Convert list to tuple if needed
        if isinstance(self.replicate_seeds, list):
            object.__setattr__(self, 'replicate_seeds', tuple(self.replicate_seeds))
        
        # Validate all seeds are integers
        all_seeds = [self.base_seed, self.trial_seed] + list(self.replicate_seeds)
        for seed in all_seeds:
            if not isinstance(seed, int):
                raise ContractViolationError(f"Seeds must be integers, got {type(seed).__name__}")
            if not (0 <= seed <= 2**64 - 1):
                raise ContractViolationError(f"Seed {seed} out of uint64 range")


@dataclass(frozen=True)
class TrialResult:
    """Result of evaluating a parameter set."""
    param_id: str
    loss: float
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    status: TrialStatus = TrialStatus.COMPLETED
    
    def __post_init__(self):
        if not self.param_id:
            raise ContractViolationError("param_id must be non-empty")
        
        # Finite loss only required for COMPLETED status
        if self.status == TrialStatus.COMPLETED and not math.isfinite(self.loss):
            raise ContractViolationError(f"Loss must be finite for COMPLETED status, got: {self.loss}")
        
        # Ensure diagnostics is dict-like
        if not isinstance(self.diagnostics, MappingABC):
            object.__setattr__(self, 'diagnostics', dict(self.diagnostics))
        
        # Validate diagnostics size and serializability
        if _approx_size(dict(self.diagnostics)) > MAX_DIAG_BYTES:
            raise ContractViolationError(f"diagnostics too large (>{MAX_DIAG_BYTES} bytes)")


__all__ = [
    "TrialStatus",
    "UniqueParameterSet", 
    "SeedInfo",
    "TrialResult",
    "make_param_id",
    "MAX_DIAG_BYTES",
]
