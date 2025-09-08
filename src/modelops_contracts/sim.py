"""Simulation service protocol for distributed execution."""
from __future__ import annotations
from typing import Protocol, Any, Mapping, Callable, Union, runtime_checkable
from .types import UniqueParameterSet

# Core types for simulation interface
Scalar = bool | int | float | str
TableIPC = bytes  # Arrow IPC or Parquet bytes for tabular data
SimReturn = Mapping[str, TableIPC]  # Named tables; MUST fit in memory
FutureLike = Any  # Opaque future type to avoid executor coupling

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
    
    def submit(self, fn_ref: str, params: dict[str, Scalar], seed: int, *, bundle_ref: str) -> FutureLike:
        """Submit a simulation for execution.
        
        Args:
            fn_ref: Function reference as "pkg.module:function"
            params: Parameter dictionary with scalar values
            seed: Random seed for reproducibility
            bundle_ref: Bundle reference for code/data dependencies
            
        Returns:
            An opaque future-like object
        """
        ...
    
    def submit_batch(self, fn_ref: str, param_sets: list[UniqueParameterSet], 
                     seed: int, *, bundle_ref: str) -> list[FutureLike]:
        """Submit multiple parameter sets (e.g., for optimization).
        
        Uses UniqueParameterSet for tracking with param_id. Derives seeds
        deterministically from the base seed using numpy.random.SeedSequence.
        
        Args:
            fn_ref: Function reference as "pkg.module:function"
            param_sets: List of UniqueParameterSet objects with param_id
            seed: Base seed for deriving per-parameter seeds
            bundle_ref: Bundle reference for code/data dependencies
            
        Returns:
            List of futures, one per parameter set
        """
        ...
    
    def submit_replicates(self, fn_ref: str, params: dict[str, Scalar],
                          seed: int, *, bundle_ref: str, 
                          n_replicates: int) -> list[FutureLike]:
        """Submit multiple replicates of the same parameters.
        
        Implementations should derive replicate seeds deterministically
        from the base seed to ensure reproducibility. Recommended to use
        numpy.random.SeedSequence internally for high-quality seed derivation.
        
        Args:
            fn_ref: Function reference as "pkg.module:function"
            params: Parameter dictionary with scalar values
            seed: Base seed for deriving replicate seeds
            bundle_ref: Bundle reference for code/data dependencies
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
    "SimulationService",
    "SimulationFunction",
    "AggregatorFunction",
    "Scalar",
    "TableIPC",
    "SimReturn",
    "FutureLike",
]
