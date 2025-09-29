"""Authentication protocol for registry and storage operations.

This defines the contract between infrastructure providers (modelops)
and artifact management (modelops-bundle) for authentication.
"""

from typing import Protocol, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class Credential:
    """Ready-to-use credential for registry or storage operations.

    Attributes:
        username: Username for basic auth or empty for token auth
        secret: The actual credential (token/password/SAS/connection string)
        expires_at: Optional Unix timestamp when credential expires
    """
    username: str
    secret: str
    expires_at: Optional[float] = None  # Unix epoch seconds


class AuthProvider(Protocol):
    """Protocol for obtaining credentials for external storage.

    Implementations handle cloud-specific authentication flows:
    - Azure: CLI token exchange, managed identity
    - AWS: CLI credentials, IRSA (future)
    - GCP: gcloud auth, workload identity (future)
    """

    def get_registry_credential(self, registry: str) -> Credential:
        """Get credential for OCI registry operations.

        Args:
            registry: Registry endpoint (e.g., "myacr.azurecr.io")

        Returns:
            Credential ready for registry authentication
        """
        ...

    def get_storage_credential(self, account: str, container: str) -> Credential:
        """Get credential for blob storage operations.

        Args:
            account: Storage account name
            container: Container/bucket name

        Returns:
            Credential ready for storage operations
        """
        ...