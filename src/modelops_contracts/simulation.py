"""Simulation task specification and service protocol."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Sequence, Any, Protocol, Callable, Union, runtime_checkable, Mapping
from types import MappingProxyType

from .types import UniqueParameterSet
from .artifacts import SimReturn
from .entrypoint import (
    EntryPointId, 
    parse_entrypoint, 
    EntrypointFormatError, 
    format_entrypoint,
    validate_entrypoint_matches_bundle
)
from .provenance import sim_root_from_parts, task_id_from_parts
from .errors import ContractViolationError

# Core types for simulation interface
Scalar = bool | int | float | str
TableIPC = bytes  # Arrow IPC or Parquet bytes for tabular data
FutureLike = Any  # Opaque future type to avoid executor coupling


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
        
        # Validate entrypoint matches bundle_ref
        try:
            validate_entrypoint_matches_bundle(self.entrypoint, self.bundle_ref)
        except EntrypointFormatError as e:
            raise ContractViolationError(str(e)) from e
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
        return sim_root_from_parts(
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
        return task_id_from_parts(
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
        - Validates entrypoint matches bundle_ref
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
        if bundle_ref.startswith("local://"):
            # TODO(MVP): Compute proper workspace digest from git + uv.lock
            # PLACEHOLDER: Use all-zeros digest for local development
            # Future: workspace_digest = compute_workspace_digest()
            workspace_digest = "000000000000"
            entrypoint = EntryPointId(f"{import_path}/{scenario}@{workspace_digest}")
        else:
            # Use standard formatting for real bundles
            entrypoint = format_entrypoint(import_path, scenario, bundle_ref)
        
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
    
    @classmethod
    def from_entrypoint(
        cls,
        *,
        entrypoint: Union[str, EntryPointId],
        bundle_ref: str,
        params: Mapping[str, Any],
        seed: int,
        outputs: Optional[Sequence[str]] = None,
        config: Optional[Mapping[str, Any]] = None,
        env: Optional[Mapping[str, Any]] = None,
    ) -> "SimTask":
        """Create SimTask when you already have a formatted EntryPointId.
        
        This factory is useful when deserializing tasks from configuration files,
        databases, or other systems where the entrypoint is already formatted.
        It still validates that the entrypoint matches the bundle_ref to ensure
        consistency.
        
        Args:
            entrypoint: Pre-formatted EntryPointId string like 'pkg.Class/scenario@digest12'
            bundle_ref: Full OCI bundle reference (must match entrypoint digest)
            params: Parameter dictionary that will be used to create UniqueParameterSet
            seed: Random seed for reproducibility (0 to 2^64-1)
            outputs: Optional list of specific outputs to extract (None = all outputs)
            config: Optional runtime configuration patches
            env: Optional environment settings
            
        Returns:
            New SimTask instance with validated entrypoint
            
        Raises:
            ContractViolationError: If entrypoint doesn't match bundle_ref
            
        Example:
            >>> task = SimTask.from_entrypoint(
            ...     entrypoint="covid.models.SEIR/baseline@abc123def456",
            ...     bundle_ref="sha256:abc123def456789...",
            ...     params={"R0": 2.5},
            ...     seed=42
            ... )
        """
        # Ensure it's an EntryPointId (NewType is just a string at runtime)
        entrypoint = EntryPointId(str(entrypoint))
        
        # Validation will happen in __post_init__
        return cls(
            bundle_ref=bundle_ref,
            entrypoint=entrypoint,
            params=UniqueParameterSet.from_dict(dict(params)),
            seed=seed,
            outputs=tuple(sorted(outputs)) if outputs else None,
            config=dict(config) if config else None,
            env=dict(env) if env else None,
        )


# Function protocols for typed contracts
class SimulationFunction(Protocol):
    """Type signature for simulation functions.
    
    Matches Calabaria's BaseModel.simulate() signature.
    """
    def __call__(self, params: dict[str, Scalar], seed: int) -> SimReturn: ...

class AggregatorFunction(Protocol):
    """Type signature for aggregator functions.
    
    Used for operations like computing mean, median, or quantiles across
    multiple simulation replicates.
    """
    def __call__(self, results: list[SimReturn]) -> SimReturn: ...


@runtime_checkable
class SimulationService(Protocol):
    """Protocol for simulation execution services.
    
    Implementations may use Dask, Ray, multiprocessing, or threads.
    Large outputs should be written to object store by user code;
    SimReturn is for small tabular results only.
    """
    
    def submit(self, task: SimTask) -> FutureLike:
        """Submit a simulation task for execution.
        
        Args:
            task: SimTask specification containing all execution parameters
            
        Returns:
            An opaque future-like object
        """
        ...
    
    def submit_batch(self, tasks: list[SimTask]) -> list[FutureLike]:
        """Submit multiple simulation tasks (e.g., for optimization).
        
        Each task has its own UniqueParameterSet for tracking with param_id.
        Seeds can be derived deterministically or specified per task.
        
        Args:
            tasks: List of SimTask specifications
            
        Returns:
            List of futures, one per task
        """
        ...
    
    def submit_replicates(self, base_task: SimTask, n_replicates: int) -> list[FutureLike]:
        """Submit multiple replicates of the same task.
        
        Implementations should derive replicate seeds deterministically
        from the base task's seed to ensure reproducibility. Recommended to use
        numpy.random.SeedSequence internally for high-quality seed derivation.
        
        Args:
            base_task: Base SimTask to replicate
            n_replicates: Number of replicates to run
            
        Returns:
            List of futures, one per replicate
        """
        ...
    
    def gather(self, futures: list[FutureLike]) -> list[SimReturn]:
        """Gather results from submitted simulations.
        
        Returns results in the same order as the input futures.
        
        Returns:
            List of simulation results (named table dictionaries)
        """
        ...
    
    def gather_and_aggregate(self, futures: list[FutureLike],
                             aggregator: Union[str, AggregatorFunction]) -> SimReturn:
        """Gather results and aggregate them.
        
        The aggregator can run on the cluster (e.g., Dask) or locally depending
        on implementation. This enables efficient reduction operations.
        
        Args:
            futures: List of futures to gather
            aggregator: Either:
                - String reference like "module:function" for distributed execution
                - AggregatorFunction callable for local execution
            
        Returns:
            Aggregated result
        """
        ...


__all__ = [
    # Core types
    "Scalar",
    "TableIPC",
    "FutureLike",
    # Task specification
    "SimTask",
    # Service protocol
    "SimulationService",
    "SimulationFunction",
    "AggregatorFunction",
]
