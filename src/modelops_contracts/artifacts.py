"""Output artifacts from simulation execution."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Mapping

from .errors import ContractViolationError


# Size threshold for inline vs reference storage
INLINE_CAP = 524288  # 512KB


@dataclass(frozen=True)
class TableArtifact:
    """Extracted table output from simulation.
    
    For MVP, all artifacts are Arrow IPC format tables.
    Large tables are stored in CAS (content-addressed storage),
    small ones are inlined in the response.
    
    Attributes:
        content_type: MIME type, always Arrow IPC for MVP
        size: Size in bytes of the artifact
        inline: The actual bytes if size <= INLINE_CAP
        ref: CAS path reference if size > INLINE_CAP
        checksum: BLAKE2b-256 hash of the content
    
    Invariants:
        - Exactly one of inline or ref must be present
        - checksum is always required for integrity
    """
    content_type: str = "application/vnd.apache.arrow.stream"
    size: int = 0
    inline: Optional[bytes] = None
    ref: Optional[str] = None
    checksum: str = ""
    
    def __post_init__(self):
        # Validate size
        if self.size < 0:
            raise ContractViolationError(f"size must be non-negative, got {self.size}")
        
        # Validate exactly one of inline or ref
        if (self.inline is None) == (self.ref is None):
            raise ContractViolationError(
                "Must provide exactly one of inline or ref"
            )
        
        # Validate inline size consistency
        if self.inline is not None:
            if len(self.inline) != self.size:
                raise ContractViolationError(
                    f"inline bytes length ({len(self.inline)}) doesn't match size ({self.size})"
                )
            if self.size > INLINE_CAP:
                raise ContractViolationError(
                    f"inline artifacts must be <= {INLINE_CAP} bytes, got {self.size}"
                )
        
        # Validate ref is non-empty if present
        if self.ref is not None and not self.ref:
            raise ContractViolationError("ref must be non-empty when provided")
        
        # Validate checksum is present
        if not self.checksum:
            raise ContractViolationError("checksum is required")
        
        # Validate checksum format (hex string of BLAKE2b-256)
        if not (len(self.checksum) == 64 and all(c in "0123456789abcdef" for c in self.checksum)):
            raise ContractViolationError(
                "checksum must be 64-character hex string (BLAKE2b-256)"
            )


@dataclass(frozen=True)
class ErrorInfo:
    """Semantic error information for quick inspection.
    
    Minimal structured error metadata for understanding failures
    without needing to fetch/decode full error artifacts.
    """
    error_type: str          # e.g., "ModuleNotFoundError", "ValueError"
    message: str             # Brief error description
    retryable: bool = False  # Whether retry might succeed


@dataclass(frozen=True)
class SimReturn:
    """Results from completed simulation task.
    
    Contains the extracted table outputs and metadata from
    a simulation run. The sim_root provides provenance tracking.
    
    Attributes:
        task_id: ID of the SimTask that produced this result
        sim_root: Provenance hash for reproducibility verification
        outputs: Map of extractor names to table artifacts
        error: Optional semantic error information
        error_details: Optional full error payload (traceback, logs, etc.)
        logs_ref: Optional CAS path to execution logs
        metrics: Optional execution metrics (runtime, memory, etc.)
        cached: Whether this result came from cache
    """
    task_id: str
    sim_root: str
    outputs: Mapping[str, TableArtifact]
    error: Optional[ErrorInfo] = None              # Semantic error info
    error_details: Optional[TableArtifact] = None  # Full traceback/logs
    logs_ref: Optional[str] = None
    metrics: Optional[Mapping[str, float]] = None
    cached: bool = False
    
    def __post_init__(self):
        # Validate required fields
        if not self.task_id:
            raise ContractViolationError("task_id must be non-empty")
        if not self.sim_root:
            raise ContractViolationError("sim_root must be non-empty")
        
        # Validate sim_root format (hex string)
        if not (len(self.sim_root) == 64 and all(c in "0123456789abcdef" for c in self.sim_root)):
            raise ContractViolationError(
                "sim_root must be 64-character hex string (hash)"
            )
        
        # Validate outputs: must be non-empty unless there's an error
        if not self.outputs and not self.error:
            raise ContractViolationError("outputs must contain at least one artifact (unless error is present)")
        
        # If error is present, validate error_details is also present
        if self.error and not self.error_details:
            raise ContractViolationError("error_details must be provided when error is present")
        
        # Validate all outputs are TableArtifacts
        for name, artifact in self.outputs.items():
            if not isinstance(artifact, TableArtifact):
                raise ContractViolationError(
                    f"Output '{name}' must be TableArtifact, got {type(artifact).__name__}"
                )


__all__ = ["TableArtifact", "SimReturn", "INLINE_CAP"]