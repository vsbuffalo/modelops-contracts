"""Model and target registry for provenance tracking.

This module provides the registry system for tracking models and their
dependencies. The registry is the foundation of the provenance system,
allowing explicit declaration of what files affect model behavior.

This is the contract interface - implementations may vary between
modelops-bundle (for authoring) and modelops (for consumption).
"""

import ast
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Protocol, runtime_checkable
import yaml
from pydantic import BaseModel as PydanticBaseModel, Field, model_validator


class ModelEntry(PydanticBaseModel):
    """Unified registry entry for a model - discovery, dependencies, and tracking.

    Combines model capabilities (what it can do) with dependencies (what it needs)
    and digest tracking for invalidation detection.

    Attributes:
        entrypoint: Full entrypoint like "models.sir:StochasticSIR"
        path: Path to the Python file containing the model
        class_name: Name of the model class
        scenarios: Available scenarios/configurations for this model
        parameters: Parameter names this model accepts
        outputs: List of output names this model produces
        data: List of data file dependencies
        data_digests: Mapping of data file paths to their digests
        code: List of code file dependencies
        code_digests: Mapping of code file paths to their digests
        model_digest: Hash of the model file itself
    """
    # Identification
    entrypoint: str  # Primary identifier like "models.sir:StochasticSIR"
    path: Path
    class_name: str

    # Capabilities (from old manifest.ModelEntry)
    scenarios: List[str] = Field(default_factory=list)
    parameters: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)

    # Dependencies with digest tracking
    data: List[Path] = Field(default_factory=list)
    data_digests: Dict[str, str] = Field(default_factory=dict)  # path -> digest

    code: List[Path] = Field(default_factory=list)
    code_digests: Dict[str, str] = Field(default_factory=dict)  # path -> digest

    # Model's own digest
    model_digest: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}

    def compute_digest(self, base_path: Optional[Path] = None) -> Optional[str]:
        """Compute and store the digest of the model file.

        Args:
            base_path: Base directory for resolving relative paths

        Returns:
            The computed digest in format "sha256:xxxx" or None if file doesn't exist
        """
        import hashlib
        base = base_path or Path.cwd()
        model_file = base / self.path if not self.path.is_absolute() else self.path

        if not model_file.exists():
            return None

        sha256 = hashlib.sha256()
        with model_file.open('rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)

        digest = f"sha256:{sha256.hexdigest()}"
        self.model_digest = digest
        return digest

    def compute_dependency_digests(self, base_path: Optional[Path] = None) -> None:
        """Compute and store digests for all dependencies.

        Updates data_digests and code_digests dictionaries with current file digests.

        Args:
            base_path: Base directory for resolving relative paths
        """
        import hashlib
        base = base_path or Path.cwd()

        def compute_file_digest(file_path: Path) -> str:
            """Compute SHA256 digest with prefix."""
            sha256 = hashlib.sha256()
            with file_path.open('rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return f"sha256:{sha256.hexdigest()}"

        # Compute data file digests
        for data_file in self.data:
            abs_path = base / data_file if not data_file.is_absolute() else data_file
            if abs_path.exists():
                # Store with relative path as key
                path_key = str(data_file)
                self.data_digests[path_key] = compute_file_digest(abs_path)

        # Compute code file digests
        for code_file in self.code:
            abs_path = base / code_file if not code_file.is_absolute() else code_file
            if abs_path.exists():
                # Store with relative path as key
                path_key = str(code_file)
                self.code_digests[path_key] = compute_file_digest(abs_path)

    def check_invalidation(self, base_path: Optional[Path] = None) -> List[str]:
        """Check what changed since digests were computed.

        This compares stored digests against current files to identify changes.

        Args:
            base_path: Base directory for resolving relative paths

        Returns:
            List of human-readable change descriptions
        """
        import hashlib
        changes = []
        base = base_path or Path.cwd()

        def compute_file_digest(file_path: Path) -> str:
            """Simple SHA256 hash of file contents."""
            sha256 = hashlib.sha256()
            with file_path.open('rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return f"sha256:{sha256.hexdigest()}"

        # Check model file itself
        if self.path and self.model_digest:
            model_file = base / self.path
            if model_file.exists():
                current = compute_file_digest(model_file)
                if current != self.model_digest:
                    changes.append(f"MODEL {self.path}: content changed")
            else:
                changes.append(f"MODEL {self.path}: file missing")

        # Check data dependencies
        for data_file in self.data:
            stored_digest = self.data_digests.get(str(data_file))
            if stored_digest:
                abs_path = base / data_file
                if abs_path.exists():
                    current = compute_file_digest(abs_path)
                    if current != stored_digest:
                        changes.append(f"DATA {data_file}: content changed")
                else:
                    changes.append(f"DATA {data_file}: file missing")
            else:
                changes.append(f"DATA {data_file}: no digest stored")

        # Check code dependencies
        for code_file in self.code:
            stored_digest = self.code_digests.get(str(code_file))
            if stored_digest:
                abs_path = base / code_file
                if abs_path.exists():
                    current = compute_file_digest(abs_path)
                    if current != stored_digest:
                        changes.append(f"CODE {code_file}: content changed")
                else:
                    changes.append(f"CODE {code_file}: file missing")
            else:
                changes.append(f"CODE {code_file}: no digest stored")

        return changes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "entrypoint": self.entrypoint,
            "path": str(self.path),
            "class_name": self.class_name,
            "scenarios": self.scenarios,
            "parameters": self.parameters,
            "outputs": self.outputs,
            "data": [str(p) for p in self.data],
            "data_digests": self.data_digests,
            "code": [str(p) for p in self.code],
            "code_digests": self.code_digests,
            "model_digest": self.model_digest
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelEntry":
        """Create from dictionary (YAML deserialization)."""
        return cls(
            entrypoint=data["entrypoint"],
            path=Path(data["path"]),
            class_name=data["class_name"],
            scenarios=data.get("scenarios", []),
            parameters=data.get("parameters", []),
            outputs=data.get("outputs", []),
            data=[Path(p) for p in data.get("data", [])],
            data_digests=data.get("data_digests", {}),
            code=[Path(p) for p in data.get("code", [])],
            code_digests=data.get("code_digests", {}),
            model_digest=data.get("model_digest")
        )


class TargetEntry(PydanticBaseModel):
    """Registry entry for a calibration target.

    Attributes:
        path: Path to the Python file containing the target
        model_output: Name of the model output to calibrate against
        observation: Path to observation data file
        target_digest: Token-based hash of the target file
    """
    path: Path
    model_output: str
    observation: Path
    target_digest: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "path": str(self.path),
            "model_output": self.model_output,
            "observation": str(self.observation),
            "target_digest": self.target_digest
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TargetEntry":
        """Create from dictionary (YAML deserialization)."""
        return cls(
            path=Path(data["path"]),
            model_output=data["model_output"],
            observation=Path(data["observation"]),
            target_digest=data.get("target_digest")
        )


@runtime_checkable
class RegistryReader(Protocol):
    """Protocol for reading model registry information.

    This is the minimal interface that modelops needs to read
    registry information from bundles.
    """

    @property
    def models(self) -> Dict[str, ModelEntry]:
        """Get all registered models."""
        ...

    @property
    def targets(self) -> Dict[str, TargetEntry]:
        """Get all registered targets."""
        ...

    def get_all_dependencies(self) -> List[Path]:
        """Get all files referenced in the registry."""
        ...


class BundleRegistry(PydanticBaseModel):
    """Registry of models and targets for provenance tracking.

    This is the base implementation that both modelops-bundle
    and modelops can use. Extended functionality (like compute_digest)
    should be added in the implementing package.
    """
    version: str = "1.0"
    models: Dict[str, ModelEntry] = Field(default_factory=dict)
    targets: Dict[str, TargetEntry] = Field(default_factory=dict)

    def add_model(
        self,
        model_id: str,
        path: Path,
        class_name: str,
        outputs: List[str] = None,
        data: List[Path] = None,
        code: List[Path] = None
    ) -> ModelEntry:
        """Add a model to the registry.

        Automatically generates entrypoint from path and class_name.
        """
        # Generate entrypoint from path
        # Convert path like "src/models/sir.py" to "models.sir:ClassName"
        if path.suffix == '.py':
            # Remove .py extension and convert path to module notation
            module_path = str(path.with_suffix(''))
            # Remove common prefixes like 'src/' if present
            if module_path.startswith('src/'):
                module_path = module_path[4:]
            # Convert / to .
            module_path = module_path.replace('/', '.')
            entrypoint = f"{module_path}:{class_name}"
        else:
            # Fallback for non-Python files
            entrypoint = f"{path.stem}:{class_name}"

        entry = ModelEntry(
            entrypoint=entrypoint,
            path=path,
            class_name=class_name,
            outputs=outputs or [],
            data=data or [],
            code=code or []
        )
        self.models[model_id] = entry
        return entry

    def add_target(
        self,
        target_id: str,
        path: Path,
        model_output: str,
        observation: Path
    ) -> TargetEntry:
        """Add a target to the registry."""
        entry = TargetEntry(
            path=path,
            model_output=model_output,
            observation=observation
        )
        self.targets[target_id] = entry
        return entry

    def validate(self) -> List[str]:
        """Validate registry entries."""
        errors = []

        for model_id, model in self.models.items():
            if not model.path.exists():
                errors.append(f"Model {model_id}: file not found at {model.path}")
            for data_file in model.data:
                if not data_file.exists():
                    errors.append(f"Model {model_id}: data dependency not found at {data_file}")
            for code_file in model.code:
                if not code_file.exists():
                    errors.append(f"Model {model_id}: code dependency not found at {code_file}")

        for target_id, target in self.targets.items():
            if not target.path.exists():
                errors.append(f"Target {target_id}: file not found at {target.path}")
            if not target.observation.exists():
                errors.append(f"Target {target_id}: observation not found at {target.observation}")

        return errors

    def get_all_dependencies(self) -> List[Path]:
        """Get all files referenced in the registry."""
        dependencies = set()

        # Add model files and their dependencies
        for model in self.models.values():
            dependencies.add(model.path)
            dependencies.update(model.data)
            dependencies.update(model.code)

        # Add target files and their observation data
        for target in self.targets.values():
            dependencies.add(target.path)
            dependencies.add(target.observation)

        return sorted(list(dependencies))

    def save(self, path: Path) -> None:
        """Save registry to YAML file.

        Args:
            path: Path to YAML file to write
        """
        with open(path, 'w') as f:
            yaml.safe_dump(self.to_dict(), f, sort_keys=False)

    @classmethod
    def load(cls, path: Path) -> "BundleRegistry":
        """Load registry from YAML file.

        Args:
            path: Path to YAML file to read

        Returns:
            Loaded BundleRegistry instance
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "version": self.version,
            "models": {k: v.to_dict() for k, v in self.models.items()},
            "targets": {k: v.to_dict() for k, v in self.targets.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BundleRegistry":
        """Create from dictionary (YAML deserialization)."""
        registry = cls(version=data.get("version", "1.0"))

        for model_id, model_data in data.get("models", {}).items():
            registry.models[model_id] = ModelEntry.from_dict(model_data)

        for target_id, target_data in data.get("targets", {}).items():
            registry.targets[target_id] = TargetEntry.from_dict(target_data)

        return registry


def discover_model_classes(file_path: Path) -> List[Tuple[str, List[str]]]:
    """Discover classes that inherit from BaseModel in a Python file.

    This function uses AST parsing to find classes without executing code,
    making it safe to use on untrusted files. It looks for classes that:
    - Directly inherit from BaseModel
    - Inherit from calabaria.BaseModel or modelops_calabaria.BaseModel
    - Inherit from other classes in the same file that inherit from BaseModel

    Args:
        file_path: Path to Python file to analyze

    Returns:
        List of (class_name, base_classes) tuples where base_classes
        is a list of base class names as strings

    Example:
        >>> discover_model_classes(Path("models.py"))
        [("StochasticSEIR", ["BaseModel"]),
         ("DeterministicSEIR", ["calabaria.BaseModel"]),
         ("NetworkSEIR", ["StochasticSEIR"])]
    """
    with open(file_path) as f:
        tree = ast.parse(f.read())

    # First pass: find all classes and their bases
    all_classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            base_names = []
            for base in node.bases:
                # Handle direct names (e.g., BaseModel)
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                # Handle attribute access (e.g., calabaria.BaseModel)
                elif isinstance(base, ast.Attribute):
                    parts = []
                    current = base
                    while isinstance(current, ast.Attribute):
                        parts.append(current.attr)
                        current = current.value
                    if isinstance(current, ast.Name):
                        parts.append(current.id)
                    base_names.append('.'.join(reversed(parts)))
            all_classes[node.name] = base_names

    # Second pass: find all BaseModel descendants
    model_classes = []

    def is_basemodel_descendant(class_name: str, visited: set = None) -> bool:
        """Recursively check if a class descends from BaseModel."""
        if visited is None:
            visited = set()

        # Prevent infinite recursion
        if class_name in visited:
            return False
        visited.add(class_name)

        # Check if this class exists in our file
        if class_name not in all_classes:
            # External class - check if it's BaseModel
            return 'BaseModel' in class_name

        # Check direct bases
        for base in all_classes[class_name]:
            if 'BaseModel' in base:
                return True
            # Recursively check parent classes
            if is_basemodel_descendant(base, visited):
                return True

        return False

    # Collect all BaseModel descendants
    for class_name, base_names in all_classes.items():
        if is_basemodel_descendant(class_name):
            model_classes.append((class_name, base_names))

    return model_classes


__all__ = [
    "ModelEntry",
    "TargetEntry",
    "BundleRegistry",
    "RegistryReader",
    "discover_model_classes",
]