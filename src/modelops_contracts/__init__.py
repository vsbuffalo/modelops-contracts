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
from .adaptive import AdaptiveAlgorithm, AlgorithmAdapter
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
    sim_root_from_parts,
    task_id_from_parts,
    calib_root,
    canonical_json,
    digest_bytes,
    shard,
)
from .entrypoint import (
    EntryPointId,
    DIGEST_PREFIX_LEN,
    ENTRYPOINT_GRAMMAR_VERSION,
    EntrypointFormatError,
    format_entrypoint,
    parse_entrypoint,
    validate_entrypoint_matches_bundle,
    is_entrypoint_for_bundle,
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
    "AlgorithmAdapter",  # Backward compat alias
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
    "validate_entrypoint_matches_bundle",
    # Parameter utilities
    "make_param_id",
    # Errors
    "ContractViolationError",
]