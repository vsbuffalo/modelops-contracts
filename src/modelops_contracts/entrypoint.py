"""Entrypoint handling for simulation tasks.

Entrypoints identify simulation code by:
1. Python import path (e.g., 'covid.models.SEIR')
2. Scenario name (e.g., 'baseline', 'lockdown')

Format: '{import_path}/{scenario}'
Example: 'covid.models.SEIR/baseline'

The bundle_ref separately tracks the code version.
"""

import re
from typing import NewType

EntryPointId = NewType("EntryPointId", str)

# Constants
ENTRYPOINT_GRAMMAR_VERSION = 2  # Version 2: No digest in entrypoint

# Conservative regex patterns for validation
_SCENARIO_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-_.]{0,62}[a-z0-9])?$")
_IMPORT_RE = re.compile(r"^[A-Za-z_][\w.]*\.[A-Za-z_]\w*$")


class EntrypointFormatError(ValueError):
    """Raised when entrypoint format is invalid."""
    pass


def format_entrypoint(import_path: str, scenario: str) -> EntryPointId:
    """Format an entrypoint ID from components.
    
    Args:
        import_path: Python import path (e.g., 'my_model.simulations.SEIR')
        scenario: Scenario name (e.g., 'baseline', 'lockdown')
        
    Returns:
        Formatted EntryPointId like 'my_model.simulations.SEIR/baseline'
        
    Raises:
        EntrypointFormatError: If inputs are invalid
    """
    if not _IMPORT_RE.match(import_path):
        raise EntrypointFormatError(f"Invalid import_path format: {import_path}")
    if not _SCENARIO_RE.match(scenario):
        raise EntrypointFormatError(f"Invalid scenario slug: {scenario}")
    
    return EntryPointId(f"{import_path}/{scenario}")


def parse_entrypoint(eid: EntryPointId) -> tuple[str, str]:
    """Parse an entrypoint ID into components.

    Handles two formats:
    - Model format: "module.path/scenario" (e.g., "models.seir/baseline")
    - Python import format: "module.path:object" (e.g., "targets.prevalence:prevalence_target")

    Args:
        eid: EntryPointId to parse

    Returns:
        Tuple of (first_part, second_part) where:
        - For models: (import_path, scenario)
        - For Python imports: (module_path, object_name)

    Raises:
        EntrypointFormatError: If format is invalid
    """
    s = str(eid)

    # Check which format we have
    if "/" in s and ":" not in s:
        # Model format: module/scenario
        try:
            import_path, scenario = s.rsplit("/", 1)
        except ValueError as e:
            raise EntrypointFormatError(f"Invalid model entrypoint format: {eid}") from e

        if not _IMPORT_RE.match(import_path):
            raise EntrypointFormatError(f"Invalid import_path format: {import_path}")
        if not _SCENARIO_RE.match(scenario):
            raise EntrypointFormatError(f"Invalid scenario slug: {scenario}")

        return import_path, scenario

    elif ":" in s and "/" not in s:
        # Python import format: module:object
        try:
            module_path, object_name = s.rsplit(":", 1)
        except ValueError as e:
            raise EntrypointFormatError(f"Invalid Python import format: {eid}") from e

        if not _IMPORT_RE.match(module_path):
            raise EntrypointFormatError(f"Invalid module path format: {module_path}")
        # Object names follow Python identifier rules (letters, numbers, underscores)
        if not object_name.replace("_", "").isalnum():
            raise EntrypointFormatError(f"Invalid Python object name: {object_name}")

        return module_path, object_name

    elif "/" in s and ":" in s:
        # Ambiguous format
        raise EntrypointFormatError(
            f"Ambiguous entrypoint format (contains both / and :): {eid}"
        )
    else:
        # No separator found
        raise EntrypointFormatError(
            f"Invalid entrypoint format (must contain either / or :): {eid}"
        )


__all__ = [
    "EntryPointId",
    "ENTRYPOINT_GRAMMAR_VERSION",
    "EntrypointFormatError",
    "format_entrypoint",
    "parse_entrypoint",
]