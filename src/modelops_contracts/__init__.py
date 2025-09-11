"""ModelOps contracts - stable interface between infrastructure and science."""

from .version import CONTRACTS_VERSION
from .types import (
    Scalar,
    TrialStatus,
    UniqueParameterSet,
    SeedInfo,
    TrialResult,
    make_param_id,
    MAX_DIAG_BYTES,
)
from .adaptive import AdaptiveAlgorithm
from .simulation import (
    SimTask,
    SimulationService,
    SimulationFunction,
    AggregatorFunction,
    Scalar,
    TableIPC,
    FutureLike,
)
from .artifacts import TableArtifact, SimReturn, INLINE_CAP
from .provenance import (
    ProvenanceLeaf,
    sim_root,
    task_id,
    calib_root,
    canonical_json,
    digest_bytes,
    shard,
)
from .entrypoint import (
    EntryPointId,
    ENTRYPOINT_GRAMMAR_VERSION,
    EntrypointFormatError,
    format_entrypoint,
    parse_entrypoint,
)
from .errors import ContractViolationError

__version__ = CONTRACTS_VERSION

__all__ = [
    # Version
    "CONTRACTS_VERSION",
    # Core task specification (ESSENTIAL - not internal!)
    "SimTask",
    "UniqueParameterSet",
    "SeedInfo",
    # Protocols
    "SimulationService",
    "AdaptiveAlgorithm",
    # Results and status
    "TrialStatus",
    "TrialResult",
    "SimReturn",
    "TableArtifact",
    "INLINE_CAP",
    "MAX_DIAG_BYTES",
    # Entrypoint utilities
    "format_entrypoint",
    "parse_entrypoint",
    # Parameter utilities
    "make_param_id",
    # Errors
    "ContractViolationError",
]