"""ModelOps contracts - stable interface between infrastructure and science."""

from .version import CONTRACTS_VERSION
from .types import (
    Scalar,
    TrialStatus,
    UniqueParameterSet,
    SeedInfo,
    TrialResult,
    MAX_DIAG_BYTES,
)
from .param_hashing import make_param_id, digest_bytes
from .adaptive import AdaptiveAlgorithm
from .simulation import (
    SimTask,
    TableIPC,
)
from .artifacts import TableArtifact, SimReturn, ErrorInfo, INLINE_CAP
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
from .manifest import ModelEntry, BundleManifest
from .batch import SimBatch
from .jobs import Job, SimJob, CalibrationJob, TargetSpec
from .study import ParameterSet, SimulationStudy, CalibrationSpec
from .bundle_environment import (
    BundleEnvironment,
    RegistryConfig,
    StorageConfig,
    DEFAULT_ENVIRONMENT,
    VALID_ENVIRONMENTS,
    ENVIRONMENTS_DIR,
)
from .auth import (
    Credential,
    AuthProvider,
)
from .environment import EnvironmentDigest

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
    # Parameter utilities
    "make_param_id",
    "digest_bytes",
    # Errors
    "ContractViolationError",
    # Ports (for hexagonal architecture)
    "Future",
    "SimulationService",
    "ExecutionEnvironment",
    "BundleRepository",
    "CAS",
    "WireFunction",
    # Manifest types for discovery
    "ModelEntry",
    "BundleManifest",
    # Batch execution types
    "SimBatch",
    # Job types (discriminated union)
    "Job",
    "SimJob",
    "CalibrationJob",
    "TargetSpec",
    # Study types (parameter-space exploration)
    "ParameterSet",
    "SimulationStudy",
    "CalibrationSpec",
    # Bundle environment configuration
    "BundleEnvironment",
    "RegistryConfig",
    "StorageConfig",
    "DEFAULT_ENVIRONMENT",
    "VALID_ENVIRONMENTS",
    "ENVIRONMENTS_DIR",
    # Authentication protocol
    "Credential",
    "AuthProvider",
    # Environment tracking
    "EnvironmentDigest",
]