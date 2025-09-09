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
    # Core types
    "CONTRACTS_VERSION",
    "Scalar",
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
    "FutureLike",
    # Task and artifact types
    "SimTask",
    "TableArtifact",
    "SimReturn",
    "INLINE_CAP",
    # Provenance
    "ProvenanceLeaf",
    "sim_root",
    "sim_root_from_parts",
    "task_id_from_parts",
    "calib_root",
    "canonical_json",
    "digest_bytes",
    "shard",
    # Entrypoint
    "EntryPointId",
    "DIGEST_PREFIX_LEN",
    "ENTRYPOINT_GRAMMAR_VERSION",
    "EntrypointFormatError",
    "format_entrypoint",
    "parse_entrypoint",
    "validate_entrypoint_matches_bundle",
    "is_entrypoint_for_bundle",
    # Errors
    "ContractViolationError",
]