"""Provenance computation for simulation and calibration tracking.

This module provides deterministic hashing and canonicalization functions
for computing provenance roots. The two-root model separates simulation
provenance (which excludes targets) from calibration provenance (which
includes targets), enabling efficient caching.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Literal, Optional, Sequence
import hashlib
import json
import math

from .errors import ContractViolationError


# Version for provenance schema
PROVENANCE_VERSION = 1

# Leaf kinds for provenance tree
LeafKind = Literal["params", "config", "code", "scenario", "seed", "env", "targets", "optimizer"]


@dataclass(frozen=True)
class ProvenanceLeaf:
    """A leaf in the provenance tree.
    
    Each leaf represents a hashed component of the computation.
    """
    kind: LeafKind
    name: str
    digest: str  # BLAKE2b-256 hex digest
    
    def __post_init__(self):
        # Validate digest format
        if not (len(self.digest) == 64 and all(c in "0123456789abcdef" for c in self.digest)):
            raise ContractViolationError(
                f"Leaf digest must be 64-character hex string, got {len(self.digest)} chars"
            )


def canonical_scalar(v: Any) -> bool | int | float | str:
    """Canonicalize scalar value for hashing.
    
    Handles special cases:
    - Rejects non-finite floats (NaN, Inf)
    - Validates supported types
    """
    if isinstance(v, bool):
        return v
    elif isinstance(v, int):
        return v
    elif isinstance(v, float):
        if not math.isfinite(v):
            raise ContractViolationError(f"Non-finite float not allowed: {v}")
        return v
    elif isinstance(v, str):
        return v
    else:
        raise ContractViolationError(f"Unsupported type for canonicalization: {type(v).__name__}")


def normalize_for_json(obj: Any) -> Any:
    """Recursively normalize object for canonical JSON.
    
    - Scalars are canonicalized (including -0.0 → 0.0)
    - Dicts have sorted keys
    - Lists/tuples become lists
    - None is preserved
    """
    from collections.abc import Mapping
    
    if obj is None:
        return None
    elif isinstance(obj, (bool, int, float, str)):
        return canonical_scalar(obj)
    elif isinstance(obj, Mapping):  # Handles dict, MappingProxyType, etc.
        return {k: normalize_for_json(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, (list, tuple)):
        return [normalize_for_json(item) for item in obj]
    else:
        raise ContractViolationError(
            f"Unsupported type in canonical JSON: {type(obj).__name__}"
        )


def canonical_json(obj: Any) -> bytes:
    """Convert object to canonical JSON bytes.
    
    Follows RFC-8785-like canonicalization:
    - Keys are sorted
    - Minimal whitespace (no spaces)
    - UTF-8 encoding
    - Float normalization (-0.0 → 0.0)
    - Rejects NaN/Inf
    """
    normalized = normalize_for_json(obj)
    json_str = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    )
    return json_str.encode("utf-8")


def digest_bytes(data: bytes) -> str:
    """Compute BLAKE2b-256 hash of bytes.
    
    Returns 64-character hex string.
    """
    return hashlib.blake2b(data, digest_size=32).hexdigest()


def hash_leaf_from_json(kind: LeafKind, name: str, obj: Any) -> ProvenanceLeaf:
    """Create a provenance leaf from JSON-serializable object."""
    canonical_bytes = canonical_json(obj)
    digest = digest_bytes(canonical_bytes)
    return ProvenanceLeaf(kind=kind, name=name, digest=digest)


def hash_leaf_from_bytes(kind: LeafKind, name: str, data: bytes) -> ProvenanceLeaf:
    """Create a provenance leaf from raw bytes."""
    digest = digest_bytes(data)
    return ProvenanceLeaf(kind=kind, name=name, digest=digest)


def compute_root(leaves: Sequence[ProvenanceLeaf]) -> str:
    """Compute root hash from provenance leaves.
    
    The root is computed by:
    1. Sorting leaves by (kind, name)
    2. Creating canonical JSON of the sorted list
    3. Hashing the result
    """
    # Sort for determinism
    sorted_leaves = sorted(leaves, key=lambda l: (l.kind, l.name))
    
    # Create canonical representation
    payload = {
        "version": PROVENANCE_VERSION,
        "leaves": [
            {"kind": leaf.kind, "name": leaf.name, "digest": leaf.digest}
            for leaf in sorted_leaves
        ]
    }
    
    return digest_bytes(canonical_json(payload))


def sim_root(
    *,
    bundle_ref: str,
    params: dict[str, Any],
    seed: int,
    entrypoint: str,
    config: Optional[dict[str, Any]] = None,
    env: Optional[dict[str, Any]] = None
) -> str:
    """Compute simulation root hash.
    
    This hash uniquely identifies a simulation run based on its inputs.
    Critically, it EXCLUDES outputs to enable cache reuse.
    
    Args:
        bundle_ref: Full OCI bundle reference (e.g., "sha256:abcd...")
        params: Simulation parameters
        seed: Random seed
        entrypoint: EntryPointId string to extract scenario from
        config: Optional configuration
        env: Optional environment settings
    
    Returns:
        64-character hex string hash
    """
    # Parse scenario from entrypoint
    try:
        from .entrypoint import parse_entrypoint, EntryPointId
        _, scenario_name = parse_entrypoint(EntryPointId(entrypoint))
    except:
        # Fallback for testing or legacy
        scenario_name = "baseline"
    
    leaves = [
        hash_leaf_from_json("code", "bundle", {"ref": bundle_ref}),
        hash_leaf_from_json("params", "parameters", params),
        hash_leaf_from_json("seed", "seed", int(seed)),
        hash_leaf_from_json("scenario", "name", scenario_name),
    ]
    
    if config:
        leaves.append(hash_leaf_from_json("config", "config", config))
    if env:
        leaves.append(hash_leaf_from_json("env", "env", env))
    
    return compute_root(leaves)


def calib_root(
    targets_id: str,
    optimizer_id: str,
    sim_roots: list[str],
    calib_code_id: str,
    env_id: str
) -> str:
    """Compute calibration root hash.
    
    This hash identifies a calibration run. It references simulation roots
    but doesn't cause re-simulation when targets change.
    
    Args:
        targets_id: Identifier for target data
        optimizer_id: Optimizer configuration identifier
        sim_roots: List of simulation root hashes
        calib_code_id: Calibration code identifier
        env_id: Environment identifier
    
    Returns:
        64-character hex string hash
    """
    leaves = [
        hash_leaf_from_bytes("targets", "data", targets_id.encode("utf-8")),
        hash_leaf_from_bytes("optimizer", "config", optimizer_id.encode("utf-8")),
        hash_leaf_from_json("code", "sim_roots", sorted(sim_roots)),
        hash_leaf_from_bytes("code", "calib", calib_code_id.encode("utf-8")),
        hash_leaf_from_bytes("env", "runtime", env_id.encode("utf-8")),
    ]
    
    return compute_root(leaves)


def shard(digest: str, depth: int = 2, width: int = 2) -> str:
    """Convert digest to sharded filesystem path.
    
    Examples:
        shard("abcdef123456...") -> "ab/cd/abcdef123456..."
        shard("abcdef123456...", depth=3, width=2) -> "ab/cd/ef/abcdef123456..."
    
    Args:
        digest: Hex digest string
        depth: Number of shard levels
        width: Characters per shard level
    
    Returns:
        Sharded path string
    """
    if len(digest) < depth * width:
        raise ContractViolationError(
            f"Digest too short for sharding: need at least {depth * width} chars, got {len(digest)}"
        )
    
    parts = []
    for i in range(depth):
        start = i * width
        parts.append(digest[start:start + width])
    parts.append(digest)
    
    return "/".join(parts)


# Re-export make_param_id functionality for backward compatibility
def make_param_id(params: dict) -> str:
    """Generate stable parameter ID (backward compatibility).
    
    This maintains the same behavior as the original in types.py
    but uses the new canonicalization functions.
    """
    # Use the same namespace as before
    canonical_params = normalize_for_json(params)
    namespaced = f"contracts:param:v1|{json.dumps(canonical_params, separators=(',', ':'), ensure_ascii=False)}"
    return digest_bytes(namespaced.encode("utf-8"))


def task_id(
    *,
    sim_root: str,
    entrypoint: str,
    outputs: Optional[tuple[str, ...]]
) -> str:
    """Compute task ID from simulation root and outputs.
    
    The task ID includes the outputs selection, making it unique
    for different materialization requests of the same simulation.
    
    Args:
        sim_root: Simulation root hash
        entrypoint: Full entrypoint string
        outputs: Tuple of output names, or None for all
    
    Returns:
        64-character hex string hash
    """
    # Use "*" to represent "all outputs"
    outputs_key = "*" if outputs is None else ",".join(sorted(outputs))
    
    payload = {
        "sim_root": sim_root,
        "entrypoint": entrypoint,
        "outputs": outputs_key
    }
    
    return digest_bytes(canonical_json(payload))



__all__ = [
    # Types
    "ProvenanceLeaf",
    "LeafKind",
    "PROVENANCE_VERSION",
    # Core functions
    "canonical_json",
    "canonical_scalar",
    "digest_bytes",
    "hash_leaf_from_json",
    "hash_leaf_from_bytes",
    "compute_root",
    # Root computation
    "sim_root",
    "task_id",
    "calib_root",
    # Utilities
    "shard",
    "make_param_id",  # Backward compat
]
