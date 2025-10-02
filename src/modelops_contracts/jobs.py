"""Job types for simulation and calibration workloads.

This module defines the discriminated union of job types that can be
executed by ModelOps infrastructure. All jobs share common fields
(job_id, bundle_ref) but have different execution patterns.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .simulation import SimTask
from .artifacts import SimReturn


@dataclass(frozen=True)
class TargetSpec:
    """Specification for calibration targets.

    Defines what empirical data to match and how to compute loss.
    """
    data: Dict[str, Any]  # Target data tables
    loss_function: str  # Name of loss function to use
    weights: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Job(ABC):
    """Base class for all job types.

    All jobs have a unique ID and reference a code bundle.
    The job_type property is used for polymorphic dispatch.
    """
    job_id: str
    bundle_ref: str

    @property
    @abstractmethod
    def job_type(self) -> str:
        """Discriminator for serialization and dispatch."""
        pass

    def to_blob_key(self) -> str:
        """Generate blob storage key for this job."""
        return f"jobs/{self.job_type}/{self.job_id}.json"

    def validate(self) -> None:
        """Validate job configuration.

        Raises:
            ValueError: If job configuration is invalid
        """
        if not self.job_id:
            raise ValueError("job_id must be non-empty")

        if not self.bundle_ref:
            raise ValueError("bundle_ref must be non-empty")

        # Validate bundle_ref format (sha256:64-hex-chars)
        if not self.bundle_ref.startswith("sha256:") or len(self.bundle_ref) != 71:
            raise ValueError(
                f"bundle_ref must be sha256:64-hex-chars, got: {self.bundle_ref}"
            )


@dataclass(frozen=True)
class SimJob(Job):
    """Simulation job with pre-determined tasks.

    A SimJob contains simulation tasks that are executed
    in parallel. All tasks are known upfront.
    """
    tasks: List[SimTask]
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    resource_requirements: Optional[Dict[str, Any]] = None

    @property
    def job_type(self) -> str:
        return "simulation"

    def task_count(self) -> int:
        """Get total number of tasks."""
        return len(self.tasks)

    def get_task_groups(self) -> Dict[str, List[SimTask]]:
        """Group tasks by parameter set for aggregation.

        Returns:
            Dictionary mapping param_id to list of tasks (replicates)
        """
        groups = {}
        for task in self.tasks:
            param_id = task.params.param_id
            if param_id not in groups:
                groups[param_id] = []
            groups[param_id].append(task)
        return groups

    def validate(self) -> None:
        """Validate SimJob configuration."""
        super().validate()

        if not self.tasks:
            raise ValueError("SimJob must have at least one task")

        # Ensure all tasks use same bundle
        for task in self.tasks:
            if task.bundle_ref != self.bundle_ref:
                raise ValueError(
                    f"All tasks must use job bundle_ref {self.bundle_ref}, "
                    f"but task has {task.bundle_ref}"
                )


@dataclass(frozen=True)
class CalibrationJob(Job):
    """Calibration job with adaptive parameter search.

    A CalibrationJob runs an optimization algorithm that iteratively
    generates parameters, evaluates them via simulation, and updates
    based on the results. Uses the ask/tell protocol.
    """
    algorithm: str  # "optuna", "abc-smc", etc.
    target_spec: TargetSpec
    max_iterations: int
    convergence_criteria: Dict[str, float] = field(default_factory=dict)
    algorithm_config: Dict[str, Any] = field(default_factory=dict)

    @property
    def job_type(self) -> str:
        return "calibration"

    def validate(self) -> None:
        """Validate CalibrationJob configuration."""
        super().validate()

        if not self.algorithm:
            raise ValueError("algorithm must be specified")

        if self.max_iterations <= 0:
            raise ValueError(f"max_iterations must be positive, got {self.max_iterations}")

        if not self.target_spec:
            raise ValueError("target_spec must be provided")


# Type alias for any job type
AnyJob = SimJob | CalibrationJob


__all__ = [
    "Job",
    "SimJob",
    "CalibrationJob",
    "TargetSpec",
    "AnyJob",
]