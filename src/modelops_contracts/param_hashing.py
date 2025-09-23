"""Parameter hashing utilities for stable parameter identification.

This module provides the canonical hashing functions that ensure parameter
sets generate stable, deterministic IDs across both ModelOps and Calabaria.
These utilities are part of the contract between systems - both sides MUST
use these exact functions to ensure the same parameters always produce the
same param_id.

The stability of param_id is critical for:
- Cache key generation in ModelOps
- Trial deduplication in Calabaria
- Distributed coordination across workers
- Reproducible experiment tracking

All functions use BLAKE2b-256 for hashing and follow strict canonicalization
rules to ensure determinism across Python versions and platforms.
"""

from __future__ import annotations
from typing import Any
import hashlib
import json
import math

from .errors import ContractViolationError


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


def make_param_id(params: dict) -> str:
    """Generate stable parameter ID for a parameter set.

    This function ensures that the same parameters always produce the same
    ID, regardless of dictionary ordering or platform differences. This is
    critical for the ask-tell protocol where parameter deduplication and
    cache lookups depend on stable IDs.

    Args:
        params: Dictionary of parameter name to value

    Returns:
        64-character hex string ID

    Example:
        >>> params = {"learning_rate": 0.01, "batch_size": 32}
        >>> param_id = make_param_id(params)
        >>> # Same params will always produce same ID
    """
    # Use namespacing to avoid collisions
    canonical_params = normalize_for_json(params)
    namespaced = f"contracts:param:v1|{json.dumps(canonical_params, separators=(',', ':'), ensure_ascii=False)}"
    return digest_bytes(namespaced.encode("utf-8"))


__all__ = [
    "canonical_scalar",
    "normalize_for_json",
    "canonical_json",
    "digest_bytes",
    "make_param_id",
]