"""Simulation task specification and service protocol."""

from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Optional, Sequence, Any, Mapping, Union, List, Dict
from types import MappingProxyType
import hashlib
import math

from .types import UniqueParameterSet
from .entrypoint import (
    EntryPointId, 
    parse_entrypoint, 
    EntrypointFormatError, 
    format_entrypoint
)
from .provenance import sim_root, task_id
from .errors import ContractViolationError
from .artifacts import SimReturn, TableArtifact

# Core types for simulation interface
from .types import Scalar
TableIPC = bytes  # Arrow IPC or Parquet bytes for tabular data


@dataclass(frozen=True)
class SimTask:
    """Specification for a single deterministic simulation task.
    
    A task is a unit of work that produces exactly one simulation
    output given the inputs. Each task should be reproducible - 
    the same inputs always produce the same outputs.
    
    Attributes:
        bundle_ref: OCI digest or bundle identifier for code version
        entrypoint: EntryPointId like 'pkg.module.Class/baseline@abcdef123456'
        params: Parameter set with stable ID
        seed: Random seed for reproducibility
        outputs: Optional list of specific extractors to run (None = all)
        config: Optional runtime configuration patches
        env: Optional environment settings
    """
    bundle_ref: str
    entrypoint: Union[str, EntryPointId]
    params: UniqueParameterSet
    seed: int
    outputs: Optional[Sequence[str]] = None
    config: Optional[Mapping[str, Any]] = None
    env: Optional[Mapping[str, Any]] = None
    
    def __post_init__(self):
        # Validate required fields
        if not self.bundle_ref:
            raise ContractViolationError("bundle_ref must be non-empty")
        if not self.entrypoint:
            raise ContractViolationError("entrypoint must be non-empty")
        
        # Validate entrypoint format if it's a string
        if isinstance(self.entrypoint, str):
            try:
                # Validate it can be parsed
                parse_entrypoint(EntryPointId(self.entrypoint))
                # Convert to EntryPointId
                object.__setattr__(self, "entrypoint", EntryPointId(self.entrypoint))
            except EntrypointFormatError as e:
                raise ContractViolationError(f"Invalid entrypoint format: {e}") from e
        
        if not isinstance(self.params, UniqueParameterSet):
            raise ContractViolationError(
                f"params must be UniqueParameterSet, got {type(self.params).__name__}"
            )
        if not isinstance(self.seed, int):
            raise ContractViolationError(f"seed must be int, got {type(self.seed).__name__}")
        if not (0 <= self.seed <= 2**64 - 1):
            raise ContractViolationError(f"seed {self.seed} out of uint64 range")
        
        # Normalize outputs to sorted tuple for determinism
        if self.outputs is not None:
            object.__setattr__(self, "outputs", tuple(sorted(self.outputs)))
        
        # Freeze config and env as MappingProxyType for immutability
        if self.config is not None:
            frozen_config = MappingProxyType(dict(self.config))
            object.__setattr__(self, "config", frozen_config)
        
        if self.env is not None:
            frozen_env = MappingProxyType(dict(self.env))
            object.__setattr__(self, "env", frozen_env)
    
    def sim_root(self) -> str:
        """Compute simulation root hash.
        
        The sim_root uniquely identifies the simulation based on code,
        parameters, seed, scenario, config, and env. It EXCLUDES outputs 
        to enable cache reuse when different outputs are requested.
        """
        return sim_root(
            bundle_ref=self.bundle_ref,
            params=dict(self.params.params),  # Convert MappingProxy to dict
            seed=self.seed,
            entrypoint=str(self.entrypoint),
            config=dict(self.config) if self.config else None,
            env=dict(self.env) if self.env else None
        )
    
    def task_id(self) -> str:
        """Compute task ID for this specific materialization.
        
        The task_id includes both the simulation identity (sim_root)
        and the specific outputs requested, making it unique for
        each materialization request.
        """
        return task_id(
            sim_root=self.sim_root(),
            entrypoint=str(self.entrypoint),
            outputs=self.outputs
        )
    
    @classmethod
    def from_components(
        cls,
        *,
        import_path: str,
        scenario: str,
        bundle_ref: str,
        params: dict[str, Any],
        seed: int,
        outputs: Optional[Sequence[str]] = None,
        config: Optional[dict[str, Any]] = None,
        env: Optional[dict[str, Any]] = None,
    ) -> "SimTask":
        """Create SimTask from individual components.
        
        This factory method is the preferred way to create SimTask instances
        programmatically. It handles the complexity of formatting the entrypoint
        string and ensures all fields are properly validated and normalized.
        
        Why use this instead of the constructor:
        - Automatically formats the entrypoint from import_path and scenario
        - Computes param_id from params dict automatically
        - Sorts outputs for deterministic behavior
        - Cleaner API for test code and programmatic task creation
        
        The raw constructor still exists for cases where you already have a
        pre-formatted entrypoint (e.g., from YAML/JSON configuration), but
        this method is preferred for creating tasks in code.
        
        Args:
            import_path: Python import path to simulation class (e.g., 'my_model.simulations.SEIR')
            scenario: Scenario name, must be lowercase slug (e.g., 'baseline', 'high_growth')
            bundle_ref: Full OCI bundle reference (e.g., 'sha256:abcdef...') or 'local://dev' for local development
            params: Parameter dictionary that will be used to create UniqueParameterSet
            seed: Random seed for reproducibility (0 to 2^64-1)
            outputs: Optional list of specific outputs to extract (None = all outputs)
            config: Optional runtime configuration patches that affect simulation
            env: Optional environment settings
            
        Returns:
            New SimTask instance with properly formatted entrypoint and normalized fields
            
        Example:
            >>> task = SimTask.from_components(
            ...     import_path="covid.models.SEIR",
            ...     scenario="lockdown",
            ...     bundle_ref="sha256:abc123...",
            ...     params={"R0": 2.5, "incubation_days": 5},
            ...     seed=42,
            ...     outputs=["infections", "deaths"]
            ... )
        """
        # Format the entrypoint from components
        entrypoint = format_entrypoint(import_path, scenario)
        
        # Create with auto-generated param_id
        return cls(
            bundle_ref=bundle_ref,
            entrypoint=entrypoint,
            params=UniqueParameterSet.from_dict(params),
            seed=seed,
            outputs=tuple(sorted(outputs)) if outputs else None,
            config=config,
            env=env,
        )
    


@dataclass(frozen=True)
class ReplicateSet:
    """Group of simulation tasks with same parameters but different seeds.
    
    This represents a set of replicates that should be executed together
    and then aggregated to compute loss against targets.
    """
    base_task: SimTask
    n_replicates: int
    seed_offset: int = 0  # Starting seed for replicates
    
    def tasks(self) -> List[SimTask]:
        """Generate individual SimTask instances for each replicate."""
        return [
            replace(self.base_task, seed=self.base_task.seed + self.seed_offset + i)
            for i in range(self.n_replicates)
        ]
    
    def replicate_keys(self) -> List[str]:
        """Generate Dask keys for tracking replicates."""
        param_id = self.base_task.params.param_id
        return [
            f"sim_{param_id[:8]}_{i}"
            for i in range(self.n_replicates)
        ]


@dataclass(frozen=True)
class AggregationTask:
    """Task for aggregating simulation results and computing loss.
    
    This runs the target evaluation entrypoint on a set of SimReturns,
    typically to compute loss against empirical data.
    """
    bundle_ref: str
    target_entrypoint: Union[str, EntryPointId]  # e.g., 'targets.covid/deaths'
    sim_returns: List[SimReturn]  # Results to aggregate
    target_data: Optional[Dict[str, Any]] = None  # Optional empirical data
    
    def __post_init__(self):
        if not self.bundle_ref:
            raise ContractViolationError("bundle_ref must be non-empty")
        if not self.target_entrypoint:
            raise ContractViolationError("target_entrypoint must be non-empty")
        if not self.sim_returns:
            raise ContractViolationError("sim_returns must be non-empty")
        
        # Validate entrypoint format if it's a string
        if isinstance(self.target_entrypoint, str):
            try:
                parse_entrypoint(EntryPointId(self.target_entrypoint))
                object.__setattr__(self, "target_entrypoint", EntryPointId(self.target_entrypoint))
            except EntrypointFormatError as e:
                raise ContractViolationError(f"Invalid target_entrypoint: {e}") from e
    
    def aggregation_id(self) -> str:
        """Compute unique ID for this aggregation task."""
        # Hash based on target, number of results, and param_id
        param_ids = [r.sim_root for r in self.sim_returns]
        content = f"{self.target_entrypoint}:{','.join(sorted(param_ids))}"
        return hashlib.blake2b(content.encode(), digest_size=32).hexdigest()[:16]


@dataclass(frozen=True) 
class AggregationReturn:
    """Result from target evaluation/aggregation.
    
    Similar to SimReturn but for aggregated results and loss computation.
    """
    aggregation_id: str
    loss: float  # Primary loss value for optimization
    diagnostics: Dict[str, Any]  # Additional metrics/info
    outputs: Dict[str, TableArtifact]  # Optional aggregated outputs
    n_replicates: int  # Number of replicates aggregated
    
    def __post_init__(self):
        if not math.isfinite(self.loss):
            raise ContractViolationError(f"loss must be finite, got {self.loss}")
        if self.n_replicates <= 0:
            raise ContractViolationError(f"n_replicates must be positive")


__all__ = [
    # Core types
    "Scalar",
    "TableIPC",
    # Task specification
    "SimTask",
    "ReplicateSet",
    "AggregationTask",
    "AggregationReturn",
]
