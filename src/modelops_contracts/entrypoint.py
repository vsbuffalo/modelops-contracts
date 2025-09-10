"""Entrypoint formatting and parsing for simulation tasks.

The entrypoint format is part of the wire contract between Calabaria (producer)
and ModelOps (consumer). This module provides the single source of truth for
the entrypoint grammar.

Grammar:
    entrypoint := <import-path> "/" <scenario> "@" <digest12>
    import-path := <module> "." <ClassName> (case-sensitive)
    scenario := [a-z0-9]([a-z0-9-_.]{0,62}[a-z0-9])? (lowercase slug)
    digest12 := first 12 hex chars of the OCI digest

Invariants:
    - entrypoint identifies compiled code + scenario (not outputs)
    - digest12 must be a prefix of the bundle_ref digest (same algo)
    - scenario must be lowercase; import_path is case-sensitive
    - outputs selection is NOT part of the entrypoint
"""

import re
from typing import NewType, Tuple

EntryPointId = NewType("EntryPointId", str)

DIGEST_PREFIX_LEN = 12
ENTRYPOINT_GRAMMAR_VERSION = 1

# Conservative regex patterns for validation
_SCENARIO_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-_.]{0,62}[a-z0-9])?$")
_IMPORT_RE = re.compile(r"^[A-Za-z_][\w.]*\.[A-Za-z_]\w*$")


class EntrypointFormatError(ValueError):
    """Raised when entrypoint format is invalid."""
    pass


def format_entrypoint(import_path: str, scenario: str, oci_digest: str) -> EntryPointId:
    """Format an entrypoint ID from components.
    
    Args:
        import_path: Python import path like 'pkg.module.Class'
        scenario: Scenario slug like 'baseline', 'lockdown' (lowercase)
        oci_digest: Full OCI digest like 'sha256:abcdef...'
    
    Returns:
        Formatted EntryPointId like 'pkg.module.Class/baseline@abcdef123456'
    
    Raises:
        EntrypointFormatError: If inputs are malformed
    """
    if not _IMPORT_RE.match(import_path):
        raise EntrypointFormatError(f"Invalid import_path format: {import_path}")
    if not _SCENARIO_RE.match(scenario):
        raise EntrypointFormatError(f"Invalid scenario slug: {scenario}")
    if ":" not in oci_digest:
        raise EntrypointFormatError("oci_digest must be algo:hex format")
    
    algo, hex_digest = oci_digest.split(":", 1)
    if algo not in ("sha256",):  # Whitelist of supported algorithms
        raise EntrypointFormatError(f"Unsupported digest algorithm: {algo}")
    if len(hex_digest) < DIGEST_PREFIX_LEN:
        raise EntrypointFormatError(
            f"Digest too short, need at least {DIGEST_PREFIX_LEN} chars"
        )
    
    return EntryPointId(f"{import_path}/{scenario}@{hex_digest[:DIGEST_PREFIX_LEN]}")


def parse_entrypoint(eid: EntryPointId) -> Tuple[str, str, str]:
    """Parse an entrypoint ID into components.
    
    Args:
        eid: EntryPointId to parse
    
    Returns:
        Tuple of (import_path, scenario, digest12)
    
    Raises:
        EntrypointFormatError: If entrypoint format is invalid
    """
    try:
        left, digest12 = str(eid).rsplit("@", 1)
        import_path, scenario = left.rsplit("/", 1)
    except ValueError as e:
        raise EntrypointFormatError(f"Invalid entrypoint format: {eid}") from e
    
    if len(digest12) != DIGEST_PREFIX_LEN:
        raise EntrypointFormatError(
            f"Digest prefix must be {DIGEST_PREFIX_LEN} chars, got {len(digest12)}"
        )
    if not _IMPORT_RE.match(import_path):
        raise EntrypointFormatError(f"Invalid import_path format: {import_path}")
    if not _SCENARIO_RE.match(scenario):
        raise EntrypointFormatError(f"Invalid scenario slug: {scenario}")
    
    return import_path, scenario, digest12


def validate_entrypoint_matches_bundle(eid: EntryPointId, bundle_ref: str) -> None:
    """Validate that entrypoint digest matches bundle reference.
    
    Args:
        eid: EntryPointId to validate
        bundle_ref: Bundle reference like 'sha256:abcdef...' or 'local://dev'
    
    Raises:
        EntrypointFormatError: If validation fails
    """
    _, _, digest12 = parse_entrypoint(eid)
    
    if bundle_ref.startswith("sha256:"):
        # Strict validation for real bundles
        try:
            algo, full_hex = bundle_ref.split(":", 1)
        except ValueError as e:
            raise EntrypointFormatError(f"Invalid bundle_ref format: {bundle_ref}") from e
        
        if not full_hex.startswith(digest12):
            raise EntrypointFormatError(
                f"Entrypoint digest '{digest12}' doesn't match bundle_ref prefix '{full_hex[:DIGEST_PREFIX_LEN]}'"
            )
    
    elif bundle_ref.startswith("local://"):
        # TODO(MVP): Implement proper workspace digest validation
        # PLACEHOLDER: For MVP, accept any valid 12-char hex digest
        # Future: Validate against computed workspace digest (git + uv.lock)
        if not re.match(r'^[0-9a-f]{12}$', digest12):
            raise EntrypointFormatError(f"Local digest must be 12 hex chars, got: {digest12}")
        
        # TODO(MVP): Check if digest is all-zeros and enforce cache-write disabled
        # if digest12 == "000000000000" and cache_writes_enabled():
        #     raise EntrypointFormatError("All-zeros digest requires cache writes disabled")
    
    else:
        # Only sha256: and local:// are supported for MVP
        # TODO(MVP): Add support for oci://, s3://, etc.
        raise EntrypointFormatError(f"Unknown bundle_ref scheme: {bundle_ref}")


def is_entrypoint_for_bundle(eid: EntryPointId, bundle_ref: str) -> bool:
    """Check if entrypoint matches bundle without throwing.
    
    Useful for hot paths where exceptions are expensive.
    
    Args:
        eid: EntryPointId to check
        bundle_ref: Bundle reference to match against
    
    Returns:
        True if entrypoint matches bundle, False otherwise
    """
    try:
        validate_entrypoint_matches_bundle(eid, bundle_ref)
        return True
    except EntrypointFormatError:
        return False


__all__ = [
    "EntryPointId",
    "DIGEST_PREFIX_LEN",
    "ENTRYPOINT_GRAMMAR_VERSION",
    "EntrypointFormatError",
    "format_entrypoint",
    "parse_entrypoint",
    "validate_entrypoint_matches_bundle",
    "is_entrypoint_for_bundle",
]