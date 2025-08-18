"""
ModelOps Bundles artifacts and data models.

This module defines the core contract types for bundle references and resolved bundles
used throughout the ModelOps ecosystem. Implementation-specific types like PointerFile
and MaterializeResult live in modelops_bundles.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Final, Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator


# ---- Media Type constants (public) ----
BUNDLE_MANIFEST: Final[str] = "application/vnd.modelops.bundle.manifest+json"
LAYER_INDEX: Final[str] = "application/vnd.modelops.layer+json"
EXTERNAL_REF: Final[str] = "application/vnd.modelops.external-ref+json"
OCI_MANIFEST: Final[str] = "application/vnd.oci.image.manifest.v1+json"
OCI_EMPTY_CFG: Final[str] = "application/vnd.oci.empty.v1+json"

# Optional: export a Literal for downstream typing (non-breaking)
MediaType = Literal[
    "application/vnd.modelops.bundle.manifest+json",
    "application/vnd.modelops.layer+json",
    "application/vnd.modelops.external-ref+json",
    "application/vnd.oci.image.manifest.v1+json",
]


# ---- Contracts ----

class BundleRef(BaseModel):
    """
    Reference to a bundle.

    Exactly one of:
      - local_path
      - digest
      - (name AND version)
    
    Resolution precedence: local_path > digest > name+version
    Names are auto-normalized to lowercase for consistency.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Optional[str] = Field(None, description="Bundle name (e.g., 'epi-sir')")
    version: Optional[str] = Field(None, description="Version tag or 'latest'")
    digest: Optional[str] = Field(
        None,
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="Content digest (sha256:...)",
    )
    local_path: Optional[str] = Field(None, description="Local filesystem path")
    role: Optional[str] = Field(None, description="Default role hint for materialization")

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, v: Optional[str]) -> Optional[str]:
        """Auto-normalize bundle names to lowercase."""
        if v is None:
            return v
        lowered = v.lower()
        if not re.fullmatch(r"[a-z0-9-/]+", lowered):
            raise ValueError(
                "name must contain only lowercase letters, digits, hyphens, and slashes"
            )
        return lowered

    @model_validator(mode="after")
    def _validate_ref(self) -> "BundleRef":
        # Mutual exclusivity
        choices = [
            bool(self.local_path),
            bool(self.digest),
            bool(self.name and self.version),
        ]
        if sum(choices) != 1:
            raise ValueError(
                "Must provide exactly one of: local_path, digest, or name+version"
            )
        return self

    def __str__(self) -> str:
        if self.digest:
            return f"BundleRef(digest={self.digest[:12]}...)"
        if self.local_path:
            return f"BundleRef(local_path={self.local_path})"
        if self.name and self.version:
            return f"BundleRef({self.name}:{self.version})"
        return "BundleRef(empty)"


class ResolvedBundle(BaseModel):
    """
    Result of bundle resolution with content addresses.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: BundleRef = Field(description="Original bundle reference")
    manifest_digest: str = Field(
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="Content digest of the resolved manifest",
    )
    media_type: str = Field(
        default=BUNDLE_MANIFEST,
        description="Manifest media type",
    )
    roles: Dict[str, List[str]] = Field(
        description="Role name to layer names mapping"
    )
    layers: List[str] = Field(
        description="All layer IDs in bundle"
    )
    external_index_present: bool = Field(
        description="True if bundle contains external storage references"
    )
    total_size: int = Field(
        ge=0,
        description="Total bundle size in bytes"
    )
    cache_dir: Optional[str] = Field(
        None,
        description="Local cache directory where ORAS content is stored"
    )

    @field_validator("roles")
    @classmethod
    def _validate_roles(cls, v: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Validate role and layer names follow naming conventions."""
        name_rx = re.compile(r"[a-z0-9-/]+")
        for role, layers in v.items():
            if not role or not name_rx.fullmatch(role):
                raise ValueError(f"Invalid role name '{role}'")
            if not layers:
                raise ValueError(f"Role '{role}' must reference at least one layer")
            for layer in layers:
                if not layer or not name_rx.fullmatch(layer):
                    raise ValueError(f"Invalid layer name '{layer}' in role '{role}'")
        return v

    @field_validator("layers")
    @classmethod
    def _validate_layers(cls, v: List[str]) -> List[str]:
        """Validate layer names follow naming conventions."""
        name_rx = re.compile(r"[a-z0-9-/]+")
        for layer in v:
            if not layer or not name_rx.fullmatch(layer):
                raise ValueError(f"Invalid layer name '{layer}'")
        return v

    # Ergonomic helper (optional; pure read)
    def get_role_layers(self, role: str) -> List[str]:
        try:
            return self.roles[role]
        except KeyError:
            available = ", ".join(sorted(self.roles))
            raise KeyError(f"Role '{role}' not found. Available roles: {available}")


__all__ = [
    "BundleRef",
    "ResolvedBundle",
    "BUNDLE_MANIFEST",
    "LAYER_INDEX",
    "EXTERNAL_REF",
    "OCI_MANIFEST",
    "OCI_EMPTY_CFG",
    "MediaType",
]