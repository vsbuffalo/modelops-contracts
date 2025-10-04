"""Bundle environment configuration contract.

This defines the contract between modelops (infrastructure provisioner)
and modelops-bundle (artifact manager). Each environment specifies both
registry and storage configuration required for bundle operations.
"""

from pathlib import Path
from typing import Optional, List
from datetime import datetime
import yaml
from pydantic import BaseModel, Field, field_validator


# Constants for standard environment names
DEFAULT_ENVIRONMENT = "dev"  # From Pulumi's default stack naming - may change in future
# Allow any environment name - it's just a label! Users should be able to use prod, staging, test, etc.
ENVIRONMENTS_DIR = Path.home() / ".modelops" / "bundle-env"


class RegistryConfig(BaseModel):
    """OCI registry configuration for bundle artifacts."""

    provider: str  # "docker", "acr", "ecr", "gcr", "ghcr"
    login_server: str  # e.g. "localhost:5555", "myregistry.azurecr.io"
    username: Optional[str] = None
    password: Optional[str] = None  # Should be secret-referenced
    requires_auth: bool = False

    @field_validator('provider')
    def validate_provider(cls, v):
        valid = {'docker', 'acr', 'ecr', 'gcr', 'ghcr'}
        if v not in valid:
            raise ValueError(f"Registry provider must be one of {valid}")
        return v


class StorageConfig(BaseModel):
    """Blob storage configuration for large artifacts."""

    provider: str  # "azure", "s3", "gcs", "azurite", "minio"
    container: str  # Container/bucket name
    connection_string: Optional[str] = None  # For Azure/Azurite
    endpoint: Optional[str] = None  # For S3/Minio
    access_key: Optional[str] = None  # For S3/GCS
    secret_key: Optional[str] = None  # For S3/GCS

    @field_validator('provider')
    def validate_provider(cls, v):
        valid = {'azure', 's3', 'gcs', 'azurite', 'minio'}
        if v not in valid:
            raise ValueError(f"Storage provider must be one of {valid}")
        return v


class BundleEnvironment(BaseModel):
    """Complete environment configuration for bundle operations.

    This is the contract between infrastructure and bundle operations.
    Both registry and storage must be configured for bundle push/pull.
    """

    environment: str  # Any environment name (dev, prod, staging, test, etc.)
    registry: RegistryConfig
    storage: StorageConfig
    timestamp: Optional[str] = None  # When this was generated

    @field_validator('environment')
    def validate_environment(cls, v):
        # Accept any non-empty string as environment name
        # It's just a label - users should be able to use whatever makes sense
        if not v or not v.strip():
            raise ValueError("Environment name cannot be empty")
        return v.strip().lower()

    # Class methods for loading/saving
    @classmethod
    def load(cls, env_name: str = DEFAULT_ENVIRONMENT) -> 'BundleEnvironment':
        """Load bundle environment configuration.

        Args:
            env_name: Environment name (defaults to "dev")

        Returns:
            BundleEnvironment instance

        Raises:
            FileNotFoundError: If environment file doesn't exist
            ValueError: If environment file is invalid
        """
        env_file = ENVIRONMENTS_DIR / f"{env_name}.yaml"

        if not env_file.exists():
            available = cls.list_environments()
            if available:
                raise FileNotFoundError(
                    f"Environment '{env_name}' not found at {env_file}. "
                    f"Available: {', '.join(available)}"
                )
            else:
                raise FileNotFoundError(
                    f"No bundle environments found in {ENVIRONMENTS_DIR}. "
                    f"Run 'mops infra up' to create one."
                )

        with open(env_file) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_yaml(cls, path: Path) -> 'BundleEnvironment':
        """Load from a specific YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_yaml_string(cls, yaml_str: str) -> 'BundleEnvironment':
        """Load from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls(**data)

    def save(self, env_name: Optional[str] = None) -> Path:
        """Save environment config to standard location.

        Args:
            env_name: Override environment name (defaults to self.environment)

        Returns:
            Path to saved file
        """
        env_name = env_name or self.environment
        ENVIRONMENTS_DIR.mkdir(parents=True, exist_ok=True)

        env_file = ENVIRONMENTS_DIR / f"{env_name}.yaml"
        self.to_yaml(env_file)
        return env_file

    def to_yaml(self, path: Path) -> None:
        """Save to a specific YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp if not set
        data = self.model_dump(exclude_none=True)
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow().isoformat()

        with open(path, 'w') as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        # Restrict permissions for security
        import os
        os.chmod(path, 0o600)

    def to_yaml_string(self) -> str:
        """Export to YAML string."""
        data = self.model_dump(exclude_none=True)
        return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)

    @classmethod
    def list_environments(cls) -> List[str]:
        """List all available environment names.

        Returns:
            Sorted list of environment names
        """
        if not ENVIRONMENTS_DIR.exists():
            return []

        envs = []
        for yaml_file in ENVIRONMENTS_DIR.glob("*.yaml"):
            try:
                # Validate it's actually a BundleEnvironment
                cls.from_yaml(yaml_file)
                envs.append(yaml_file.stem)
            except:
                continue  # Skip invalid files

        return sorted(envs)