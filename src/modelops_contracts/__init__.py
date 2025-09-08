"""ModelOps contracts - stable interface between infrastructure and science."""

from .version import CONTRACTS_VERSION
from .types import (
    TrialStatus,
    UniqueParameterSet,
    SeedInfo,
    TrialResult,
    make_param_id,
    MAX_DIAG_BYTES,
)
from .adaptive import AdaptiveAlgorithm, AlgorithmAdapter
from .sim import (
    SimulationService,
    SimulationFunction,
    AggregatorFunction,
    Scalar,
    TableIPC,
    SimReturn,
    FutureLike,
)
from .errors import ContractViolationError

__version__ = CONTRACTS_VERSION

__all__ = [
    # Core types
    "CONTRACTS_VERSION",
    "TrialStatus",
    "UniqueParameterSet",
    "SeedInfo", 
    "TrialResult",
    "make_param_id",
    "MAX_DIAG_BYTES",
    # Protocols
    "AdaptiveAlgorithm",
    "AlgorithmAdapter",  # Backward compat alias
    "SimulationService",
    "SimulationFunction",
    "AggregatorFunction",
    # Sim types
    "Scalar",
    "TableIPC",
    "SimReturn",
    "FutureLike",
    # Errors
    "ContractViolationError",
]