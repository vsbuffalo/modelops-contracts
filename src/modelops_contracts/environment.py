"""Environment tracking for reproducible computation.

This module provides the EnvironmentDigest for tracking execution environments
to ensure reproducibility. The digest captures Python version, platform,
dependencies, and optionally container information.

The environment digest is a critical part of provenance tracking, ensuring
that cached results are only reused when the execution environment matches.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional
import json
import sys
import platform

from .param_hashing import digest_bytes


@dataclass(frozen=True)
class EnvironmentDigest:
    """Track all environment factors affecting reproducibility.

    This digest ensures that simulation results are only reused when
    the execution environment matches. Changes to Python version,
    key dependencies, or platform trigger cache invalidation.

    Attributes:
        python_version: Full Python version string (e.g., "3.11.5")
        platform: Platform identifier (e.g., "linux-x86_64", "darwin-arm64")
        dependencies: Dictionary mapping package names to versions
        container_image: Optional OCI image digest for containerized environments
        cuda_version: Optional CUDA version for GPU workloads
        rng_algorithm: NumPy RNG algorithm name (default: "PCG64")
        thread_count: Number of threads for deterministic execution (default: 1)
    """
    python_version: str
    platform: str
    dependencies: Dict[str, str] = field(default_factory=dict)
    container_image: Optional[str] = None
    cuda_version: Optional[str] = None
    rng_algorithm: str = "PCG64"
    thread_count: int = 1

    def compute_digest(self) -> str:
        """Generate stable digest of environment.

        Returns a deterministic hash that changes when any environment
        factor changes, triggering appropriate cache invalidation.

        Returns:
            64-character hex string digest
        """
        # Create canonical representation
        env_dict = {
            "python": self.python_version,
            "platform": self.platform,
            "deps": sorted(self.dependencies.items()),  # Sort for determinism
            "container": self.container_image,
            "cuda": self.cuda_version,
            "rng": self.rng_algorithm,
            "threads": self.thread_count
        }

        # Use canonical JSON serialization
        canonical = json.dumps(
            env_dict,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False
        )

        # Namespace to avoid collisions
        namespaced = f"contracts:env:v1|{canonical}"
        return digest_bytes(namespaced.encode("utf-8"))

    @classmethod
    def capture_current(cls) -> EnvironmentDigest:
        """Capture the current Python environment.

        This is a convenience method for simple cases. Production usage
        should explicitly specify all dependencies for full reproducibility.

        Returns:
            EnvironmentDigest for current environment
        """
        # Get Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # Get platform
        machine = platform.machine()  # e.g., "x86_64", "arm64"
        system = platform.system().lower()  # e.g., "linux", "darwin", "windows"
        platform_str = f"{system}-{machine}"

        # Basic environment (caller should add dependencies)
        return cls(
            python_version=python_version,
            platform=platform_str,
            dependencies={}  # Caller should populate with actual deps
        )

    def with_dependencies(self, packages: Dict[str, str]) -> EnvironmentDigest:
        """Create new digest with updated dependencies.

        Args:
            packages: Dictionary of package name to version

        Returns:
            New EnvironmentDigest with updated dependencies
        """
        return EnvironmentDigest(
            python_version=self.python_version,
            platform=self.platform,
            dependencies={**self.dependencies, **packages},
            container_image=self.container_image,
            cuda_version=self.cuda_version,
            rng_algorithm=self.rng_algorithm,
            thread_count=self.thread_count
        )

    def to_json(self) -> Dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "python_version": self.python_version,
            "platform": self.platform,
            "dependencies": self.dependencies,
            "container_image": self.container_image,
            "cuda_version": self.cuda_version,
            "rng_algorithm": self.rng_algorithm,
            "thread_count": self.thread_count,
            "digest": self.compute_digest()
        }


__all__ = [
    "EnvironmentDigest",
]