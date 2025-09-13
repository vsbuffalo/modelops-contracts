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
    TableIPC,
)
from .artifacts import TableArtifact, SimReturn, ErrorInfo, INLINE_CAP
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
from .ports import (
    Future,
    SimulationService,
    ExecutionEnvironment,
    BundleRepository,
    CAS,
    WireFunction,
)

__version__ = CONTRACTS_VERSION

__all__ = [
    # Version
    "CONTRACTS_VERSION",
    # Core task specification (ESSENTIAL - not internal!)
    "SimTask",
    "UniqueParameterSet",
    "SeedInfo",
    # Type aliases
    "Scalar",
    "TableIPC",
    # Protocols
    "AdaptiveAlgorithm",
    # Results and status
    "TrialStatus",
    "TrialResult",
    "SimReturn",
    "ErrorInfo",
    "TableArtifact",
    "INLINE_CAP",
    "MAX_DIAG_BYTES",
    # Entrypoint utilities
    "EntryPointId",
    "ENTRYPOINT_GRAMMAR_VERSION",
    "EntrypointFormatError",
    "format_entrypoint",
    "parse_entrypoint",
    # Provenance utilities
    "ProvenanceLeaf",
    "sim_root",
    "task_id",
    "calib_root",
    "canonical_json",
    "digest_bytes",
    "shard",
    # Parameter utilities
    "make_param_id",
    # Errors
    "ContractViolationError",
    # Ports (for hexagonal architecture)
    "Future",
    "SimulationService",
    "ExecutionEnvironment",
    "BundleRepository",
    "CAS",
    "WireFunction",
]