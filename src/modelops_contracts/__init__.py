"""ModelOps contracts - stable interface between infrastructure and science."""

from .version import CONTRACTS_VERSION
from .types import (
    TrialStatus,
    UniqueParameterSet,
    SeedInfo,
    TrialResult,
    make_param_id,
)
from .protocols import AlgorithmAdapter
from .errors import ContractViolationError
from .artifacts import (
    BundleRef,
    ResolvedBundle,
    BUNDLE_MANIFEST,
    LAYER_INDEX,
    EXTERNAL_REF,
    OCI_MANIFEST,
    OCI_EMPTY_CFG,
    MediaType,
)

__version__ = CONTRACTS_VERSION

__all__ = [
    "CONTRACTS_VERSION",
    "TrialStatus",
    "UniqueParameterSet",
    "SeedInfo", 
    "TrialResult",
    "make_param_id",
    "AlgorithmAdapter",
    "ContractViolationError",
    "BundleRef",
    "ResolvedBundle",
    "BUNDLE_MANIFEST",
    "LAYER_INDEX",
    "EXTERNAL_REF",
    "OCI_MANIFEST",
    "OCI_EMPTY_CFG",
    "MediaType",
]
