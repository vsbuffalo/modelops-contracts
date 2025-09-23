"""Tests for batch and job types."""

import pytest
from modelops_contracts import (
    SimBatch,
    SimJob,
    SimTask,
    UniqueParameterSet,
    ContractViolationError
)


def create_test_task(seed: int = 42, bundle_ref: str = "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789") -> SimTask:
    """Helper to create a valid SimTask for testing."""
    return SimTask.from_components(
        import_path="models.test.Model",
        scenario="baseline",
        bundle_ref=bundle_ref,
        params={"x": 1.0, "y": 2.0},
        seed=seed
    )


class TestSimBatch:
    """Tests for SimBatch validation and functionality."""

    def test_batch_requires_tasks(self):
        """SimBatch must have at least one task."""
        # Valid: has tasks
        batch = SimBatch(
            batch_id="batch-001",
            tasks=[create_test_task()],
            sampling_method="grid"
        )
        assert batch.task_count() == 1

        # Invalid: empty tasks
        with pytest.raises(ContractViolationError, match="at least one SimTask"):
            SimBatch(
                batch_id="batch-001",
                tasks=[],
                sampling_method="grid"
            )

    def test_batch_validates_task_types(self):
        """All items in tasks must be SimTask instances."""
        # Valid tasks
        batch = SimBatch(
            batch_id="batch-001",
            tasks=[create_test_task(i) for i in range(3)],
            sampling_method="sobol"
        )
        assert batch.task_count() == 3

        # Invalid: wrong type
        with pytest.raises(ContractViolationError, match="must be SimTask"):
            SimBatch(
                batch_id="batch-001",
                tasks=[{"not": "a task"}],  # type: ignore
                sampling_method="grid"
            )

    def test_batch_requires_batch_id(self):
        """Batch ID must be non-empty."""
        with pytest.raises(ContractViolationError, match="batch_id must be non-empty"):
            SimBatch(
                batch_id="",
                tasks=[create_test_task()],
                sampling_method="grid"
            )

    def test_batch_requires_sampling_method(self):
        """Sampling method must be specified."""
        with pytest.raises(ContractViolationError, match="sampling_method must be non-empty"):
            SimBatch(
                batch_id="batch-001",
                tasks=[create_test_task()],
                sampling_method=""
            )

    def test_batch_compute_hash(self):
        """Test deterministic batch hash computation."""
        task1 = create_test_task(seed=1)
        task2 = create_test_task(seed=2)

        batch1 = SimBatch(
            batch_id="batch-001",
            tasks=[task1, task2],
            sampling_method="grid"
        )

        batch2 = SimBatch(
            batch_id="batch-002",  # Different ID
            tasks=[task1, task2],  # Same tasks
            sampling_method="sobol"  # Different method
        )

        # Hash should be based on task param_ids, not batch metadata
        assert batch1.compute_batch_hash() == batch2.compute_batch_hash()

        # Different tasks should give different hash
        batch3 = SimBatch(
            batch_id="batch-003",
            tasks=[create_test_task(seed=99)],
            sampling_method="grid"
        )
        assert batch1.compute_batch_hash() != batch3.compute_batch_hash()

    def test_batch_task_count(self):
        """Test task counting."""
        tasks = [create_test_task(i) for i in range(5)]
        batch = SimBatch(
            batch_id="batch-001",
            tasks=tasks,
            sampling_method="grid"
        )
        assert batch.task_count() == 5

    def test_batch_metadata(self):
        """Test batch metadata storage."""
        batch = SimBatch(
            batch_id="batch-001",
            tasks=[create_test_task()],
            sampling_method="sobol",
            metadata={
                "n_samples": 100,
                "scramble": True,
                "custom_field": "value"
            }
        )
        assert batch.metadata["n_samples"] == 100
        assert batch.metadata["scramble"] is True
        assert batch.metadata["custom_field"] == "value"


class TestSimJob:
    """Tests for SimJob validation and functionality."""

    def test_job_requires_batches(self):
        """SimJob must have at least one batch."""
        batch = SimBatch(
            batch_id="batch-001",
            tasks=[create_test_task()],
            sampling_method="grid"
        )

        # Valid: has batches
        job = SimJob(
            job_id="job-001",
            batches=[batch],
            bundle_ref="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        )
        assert len(job.batches) == 1

        # Invalid: empty batches
        with pytest.raises(ContractViolationError, match="at least one SimBatch"):
            SimJob(
                job_id="job-001",
                batches=[],
                bundle_ref="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
            )

    def test_job_validates_batch_types(self):
        """All items in batches must be SimBatch instances."""
        with pytest.raises(ContractViolationError, match="must be SimBatch"):
            SimJob(
                job_id="job-001",
                batches=[{"not": "a batch"}],  # type: ignore
                bundle_ref="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
            )

    def test_job_bundle_ref_consistency(self):
        """All tasks in a job must use the same bundle_ref."""
        task1 = create_test_task(bundle_ref="sha256:" + "a" * 64)
        task2 = create_test_task(bundle_ref="sha256:" + "b" * 64)

        batch1 = SimBatch(
            batch_id="batch-001",
            tasks=[task1],
            sampling_method="grid"
        )
        batch2 = SimBatch(
            batch_id="batch-002",
            tasks=[task2],
            sampling_method="grid"
        )

        # Should fail: different bundle refs
        with pytest.raises(ContractViolationError, match="same bundle"):
            SimJob(
                job_id="job-001",
                batches=[batch1, batch2],
                bundle_ref="sha256:" + "a" * 64
            )

        # Should also fail if job bundle_ref doesn't match
        batch3 = SimBatch(
            batch_id="batch-003",
            tasks=[task1, task1],  # Both use same digest
            sampling_method="grid"
        )
        with pytest.raises(ContractViolationError, match="doesn't match"):
            SimJob(
                job_id="job-001",
                batches=[batch3],
                bundle_ref="sha256:" + "c" * 64  # Doesn't match task bundle_ref
            )

    def test_job_priority_range(self):
        """Priority should be in reasonable range."""
        batch = SimBatch(
            batch_id="batch-001",
            tasks=[create_test_task()],
            sampling_method="grid"
        )

        # Valid priorities
        for priority in [-1000, 0, 100, 1000]:
            job = SimJob(
                job_id="job-001",
                batches=[batch],
                bundle_ref="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                priority=priority
            )
            assert job.priority == priority

        # Invalid: too high
        with pytest.raises(ContractViolationError, match="out of reasonable range"):
            SimJob(
                job_id="job-001",
                batches=[batch],
                bundle_ref="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                priority=9999
            )

        # Invalid: too low
        with pytest.raises(ContractViolationError, match="out of reasonable range"):
            SimJob(
                job_id="job-001",
                batches=[batch],
                bundle_ref="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                priority=-9999
            )

    def test_job_total_task_count(self):
        """Test aggregating task count across batches."""
        batch1 = SimBatch(
            batch_id="batch-001",
            tasks=[create_test_task(i) for i in range(3)],
            sampling_method="grid"
        )
        batch2 = SimBatch(
            batch_id="batch-002",
            tasks=[create_test_task(i) for i in range(5)],
            sampling_method="sobol"
        )

        job = SimJob(
            job_id="job-001",
            batches=[batch1, batch2],
            bundle_ref="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        )

        assert job.total_task_count() == 8

    def test_job_get_all_tasks(self):
        """Test getting flat list of all tasks."""
        tasks1 = [create_test_task(i) for i in range(2)]
        tasks2 = [create_test_task(i + 10) for i in range(3)]

        batch1 = SimBatch(
            batch_id="batch-001",
            tasks=tasks1,
            sampling_method="grid"
        )
        batch2 = SimBatch(
            batch_id="batch-002",
            tasks=tasks2,
            sampling_method="sobol"
        )

        job = SimJob(
            job_id="job-001",
            batches=[batch1, batch2],
            bundle_ref="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        )

        all_tasks = job.get_all_tasks()
        assert len(all_tasks) == 5
        assert all_tasks[:2] == tasks1
        assert all_tasks[2:] == tasks2

    def test_job_compute_hash(self):
        """Test deterministic job hash computation."""
        # Use consistent bundle_ref for tasks
        batch1 = SimBatch(
            batch_id="batch-001",
            tasks=[create_test_task(1, bundle_ref="sha256:" + "a" * 64)],
            sampling_method="grid"
        )
        batch2 = SimBatch(
            batch_id="batch-002",
            tasks=[create_test_task(2, bundle_ref="sha256:" + "a" * 64)],
            sampling_method="grid"
        )

        job1 = SimJob(
            job_id="job-001",
            batches=[batch1, batch2],
            bundle_ref="sha256:" + "a" * 64
        )

        job2 = SimJob(
            job_id="job-002",  # Different ID
            batches=[batch1, batch2],  # Same batches
            bundle_ref="sha256:" + "a" * 64  # Same bundle
        )

        # Same content should give same hash
        assert job1.compute_job_hash() == job2.compute_job_hash()

        # Different bundle should give different hash
        batch3 = SimBatch(
            batch_id="batch-003",
            tasks=[create_test_task(3, bundle_ref="sha256:" + "b" * 64)],
            sampling_method="grid"
        )
        job3 = SimJob(
            job_id="job-001",
            batches=[batch3],
            bundle_ref="sha256:" + "b" * 64  # Different bundle
        )
        assert job1.compute_job_hash() != job3.compute_job_hash()

    def test_job_resource_requirements(self):
        """Test optional resource requirements."""
        batch = SimBatch(
            batch_id="batch-001",
            tasks=[create_test_task()],
            sampling_method="grid"
        )

        job = SimJob(
            job_id="job-001",
            batches=[batch],
            bundle_ref="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            resource_requirements={
                "memory": "4GB",
                "cpus": 2,
                "gpu": False
            }
        )

        assert job.resource_requirements["memory"] == "4GB"
        assert job.resource_requirements["cpus"] == 2
        assert job.resource_requirements["gpu"] is False