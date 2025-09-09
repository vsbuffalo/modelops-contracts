"""Simulation task specification and service protocol."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Sequence, Any, Protocol, Callable, Union, runtime_checkable
from types import MappingProxyType

from .types import UniqueParameterSet
from .artifacts import SimReturn
from .entrypoint import EntryPointId, parse_entrypoint, EntrypointFormatError
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
        request_cache_read: Whether to allow reading from cache (future)
        request_cache_write: Whether to allow writing to cache (future)
    """
    bundle_ref: str
    entrypoint: Union[str, EntryPointId]
    params: UniqueParameterSet
    seed: int
    outputs: Optional[Sequence[str]] = None
    # request_cache_read: bool = True
    # request_cache_write: bool = True
    
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
    
    def sim_root(self) -> str:
        """Compute simulation root hash.
        
        The sim_root uniquely identifies the simulation based on code,
        parameters, seed, and scenario. It EXCLUDES outputs to enable
        cache reuse when different outputs are requested.
        """
        return sim_root_from_parts(
            bundle_ref=self.bundle_ref,
            params=self.params.params,
            seed=self.seed,
            entrypoint=str(self.entrypoint)
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
