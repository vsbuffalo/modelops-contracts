"""Port definitions for hexagonal architecture.

These protocols define the boundaries between the core domain and adapters,
enabling dependency inversion and testability. All infrastructure details
are hidden behind these abstractions.

The ports follow the Hexagonal Architecture pattern:
- Primary/Driving ports: How the outside world drives the application
- Secondary/Driven ports: How the application drives external systems
"""

from typing import Protocol, Generic, TypeVar, Optional, List, Dict, Any, Tuple, Mapping
from pathlib import Path

from .simulation import SimTask
from .artifacts import SimReturn
from .entrypoint import EntryPointId
from .types import Scalar

T = TypeVar('T')


# Primary/Driving Ports (Inbound)

class Future(Protocol, Generic[T]):
    """Type-safe future abstraction for async results.
    
    Abstracts over different async implementations (Dask, asyncio, etc).
    """
    
    def result(self, timeout: Optional[float] = None) -> T:
        """Block and return the result, raising any exceptions."""
        ...
    
    def done(self) -> bool:
        """Check if the future has completed."""
        ...
    
    def cancel(self) -> bool:
        """Attempt to cancel the operation."""
        ...
    
    def exception(self) -> Optional[Exception]:
        """Return the exception if the future failed, None otherwise."""
        ...


class SimulationService(Protocol):
    """Primary port - how clients drive the simulation system.
    
    This is the main entry point for submitting and managing simulations.
    Implementations might use Dask, Ray, multiprocessing, or threads.
    """
    
    def submit(self, task: SimTask) -> Future[SimReturn]:
        """Submit a single simulation task for execution.
        
        Args:
            task: SimTask specification containing all execution parameters
            
        Returns:
            A Future that will contain the SimReturn result
        """
        ...
    
    def gather(self, futures: List[Future[SimReturn]]) -> List[SimReturn]:
        """Gather results from multiple futures.
        
        Blocks until all futures complete and returns results in order.
        
        Args:
            futures: List of futures to gather
            
        Returns:
            List of simulation results in the same order as futures
        """
        ...
    
    def submit_batch(self, tasks: List[SimTask]) -> List[Future[SimReturn]]:
        """Submit multiple simulation tasks efficiently.
        
        Args:
            tasks: List of SimTask specifications
            
        Returns:
            List of futures, one per task
        """
        ...


# Secondary/Driven Ports (Outbound)

class ExecutionEnvironment(Protocol):
    """Port for executing simulations in isolated environments.
    
    Implementations handle the actual simulation execution, which might be:
    - In-process (for testing)
    - Subprocess with isolation
    - Container-based
    - Remote execution
    """
    
    def run(self, task: SimTask) -> SimReturn:
        """Execute a simulation task in the environment.
        
        Args:
            task: The simulation task to execute
            
        Returns:
            SimReturn with outputs and metadata
            
        Raises:
            Various exceptions on execution failure
        """
        ...
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of execution environment.
        
        Returns:
            Dictionary with health status information
        """
        ...
    
    def shutdown(self) -> None:
        """Clean shutdown of resources.
        
        Called during teardown to properly close warm processes,
        connections, or other resources. Critical for WorkerPlugin
        lifecycle management.
        """
        ...


class BundleRepository(Protocol):
    """Port for fetching and staging simulation bundles.
    
    Abstracts bundle storage which might be:
    - modelops-bundle (our modelops solution)
    - another OCI registry
    - S3/Azure blob storage
    - Local filesystem
    - Git repositories
    """
    
    def ensure_local(self, bundle_ref: str) -> Tuple[str, Path]:
        """Fetch bundle and ensure it's available locally.
        
        Args:
            bundle_ref: Bundle reference (e.g., 'sha256:abc...', 'oci://...')
            
        Returns:
            Tuple of (canonical_digest, local_path) where:
            - canonical_digest: The canonical content hash
            - local_path: Path to the extracted bundle directory
            
        Raises:
            Various exceptions on fetch failure
        """
        ...
    
    def exists(self, bundle_ref: str) -> bool:
        """Check if a bundle exists in the repository.
        
        Args:
            bundle_ref: Bundle reference to check
            
        Returns:
            True if bundle exists, False otherwise
        """
        ...


class CAS(Protocol):
    """Content-addressable storage for large artifacts.
    
    Used for storing simulation outputs that exceed inline limits.
    Implementations might use:
    - S3
    - Azure Blob Storage
    - Local filesystem
    - In-memory (for testing)
    """
    
    def put(self, data: bytes, checksum_hex: str) -> str:
        """Store data in CAS.
        
        Args:
            data: Raw bytes to store
            checksum_hex: Expected SHA256 hex digest for verification
            
        Returns:
            Reference string for retrieving the data
            
        Raises:
            ChecksumError if data doesn't match expected checksum
        """
        ...
    
    def get(self, ref: str) -> bytes:
        """Retrieve data from CAS.
        
        Args:
            ref: Reference returned from put()
            
        Returns:
            Raw bytes data
            
        Raises:
            KeyError if reference not found
        """
        ...
    
    def exists(self, ref: str) -> bool:
        """Check if a reference exists in CAS.
        
        Args:
            ref: Reference to check
            
        Returns:
            True if exists, False otherwise
        """
        ...


class WireFunction(Protocol):
    """Contract for simulation execution inside isolated environment.
    
    This is the low-level execution contract that Calabaria bundles
    must implement. It's called by the isolated worker process.
    """
    
    def __call__(
        self,
        entrypoint: EntryPointId,
        params: Mapping[str, Scalar],
        seed: int
    ) -> Dict[str, bytes]:
        """Execute simulation and return raw outputs.
        
        Args:
            entrypoint: Entrypoint identifying code and scenario
            params: Parameter values for simulation
            seed: Random seed for reproducibility
            
        Returns:
            Dictionary mapping output names to raw bytes (Arrow IPC or Parquet)
            
        Raises:
            Various exceptions on execution failure
        """
        ...


__all__ = [
    # Type abstractions
    "Future",
    # Primary ports
    "SimulationService",
    # Secondary ports
    "ExecutionEnvironment",
    "BundleRepository", 
    "CAS",
    "WireFunction",
]
