"""Tests for protocol interfaces."""

from modelops_contracts import (
    SimulationService,
    AdaptiveAlgorithm,
    UniqueParameterSet,
    TrialResult,
    TrialStatus,
    Scalar,
    TableIPC,
    SimReturn,
    TableArtifact,
    FutureLike,
    SimTask,
)


def test_simulation_service_protocol():
    """Test that SimulationService protocol works as expected."""
    
    # Create a minimal implementation
    class MockSimService:
        def submit(self, task: SimTask) -> FutureLike:
            return f"future_{str(task.entrypoint)}_{task.seed}"
        
        def submit_batch(self, tasks: list[SimTask]) -> list[FutureLike]:
            return [f"future_{str(t.entrypoint)}_{t.seed}" for t in tasks]
        
        def submit_replicates(self, base_task: SimTask, n_replicates: int) -> list[FutureLike]:
            return [f"future_{str(base_task.entrypoint)}_{base_task.seed}_{i}" for i in range(n_replicates)]
        
        def gather(self, futures: list[FutureLike]) -> list[SimReturn]:
            # Return mock SimReturn objects
            mock_data = b"mock_data" * 10
            output = TableArtifact(
                size=len(mock_data),
                inline=mock_data,
                checksum="a" * 64
            )
            return [
                SimReturn(
                    task_id=f"task_{i}",
                    sim_root="b" * 64,
                    outputs={"result": output}
                )
                for i, _ in enumerate(futures)
            ]
        
        def gather_and_aggregate(self, futures: list[FutureLike],
                                 aggregator) -> SimReturn:
            results = self.gather(futures)
            if callable(aggregator):
                return aggregator(results)
            # If string ref, just return first result as mock
            return results[0] if results else SimReturn(
                task_id="aggregated",
                sim_root="c" * 64,
                outputs={"aggregated": TableArtifact(
                    size=len(b"aggregated_data" * 3),
                    inline=b"aggregated_data" * 3,
                    checksum="d" * 64
                )}
            )
    
    # Should satisfy the protocol
    service = MockSimService()
    assert isinstance(service, SimulationService)
    
    # Test basic usage
    task = SimTask(
        bundle_ref="sha256:abcdef1234567890123456789012345678",
        entrypoint="pkg.mod.Func/baseline@abcdef123456",
        params=UniqueParameterSet.from_dict({"x": 1.0}),
        seed=42
    )
    future = service.submit(task)
    assert future == "future_pkg.mod.Func/baseline@abcdef123456_42"
    
    results = service.gather([future, future])
    assert len(results) == 2
    assert all(isinstance(r, SimReturn) for r in results)


def test_adaptive_algorithm_protocol():
    """Test that AdaptiveAlgorithm protocol works as expected."""
    
    # Create a minimal implementation
    class MockAlgorithm:
        def __init__(self):
            self.n_asks = 0
            self.results = []
        
        def ask(self, n: int) -> list[UniqueParameterSet]:
            self.n_asks += 1
            if self.n_asks > 2:
                return []  # No more work
            return [UniqueParameterSet.from_dict({"x": float(i)}) for i in range(n)]
        
        def tell(self, results: list[TrialResult]) -> None:
            self.results.extend(results)
        
        def finished(self) -> bool:
            return self.n_asks > 2
    
    # Should satisfy the protocol
    algo = MockAlgorithm()
    assert isinstance(algo, AdaptiveAlgorithm)
    
    # Test ask-tell loop
    batch = algo.ask(3)
    assert len(batch) == 3
    assert all(isinstance(p, UniqueParameterSet) for p in batch)
    
    results = [
        TrialResult(
            param_id=p.param_id,
            loss=0.5,
            status=TrialStatus.COMPLETED
        )
        for p in batch
    ]
    algo.tell(results)
    assert len(algo.results) == 3
    
    # After 2 asks, should be finished
    batch2 = algo.ask(1)
    assert len(batch2) == 1  # Second ask still returns results
    
    # Third ask returns empty and finished
    batch3 = algo.ask(1)
    assert batch3 == []
    assert algo.finished()


def test_sim_types():
    """Test that simulation types work correctly."""
    
    # Scalar should accept basic types
    scalar_values: list[Scalar] = [True, 42, 3.14, "text"]
    for val in scalar_values:
        assert isinstance(val, (bool, int, float, str))
    
    # TableIPC is just bytes
    table_data: TableIPC = b"arrow_ipc_data"
    assert isinstance(table_data, bytes)
    
    # SimReturn is now a proper dataclass
    data1 = b"table1_data" * 8
    output1 = TableArtifact(
        size=len(data1),
        inline=data1,
        checksum="e" * 64
    )
    data2 = b"table2_data" * 16
    output2 = TableArtifact(
        size=len(data2),
        inline=data2,
        checksum="f" * 64
    )
    sim_return = SimReturn(
        task_id="test_task",
        sim_root="0" * 64,
        outputs={
            "infected": output1,
            "deaths": output2
        }
    )
    assert isinstance(sim_return, SimReturn)
    assert sim_return.task_id == "test_task"
    assert len(sim_return.outputs) == 2
    assert all(isinstance(v, TableArtifact) for v in sim_return.outputs.values())
    
    # FutureLike is Any - accepts anything
    future: FutureLike = "any_object"
    assert future == "any_object"
    future = 42
    assert future == 42


def test_protocol_ordering_guarantee():
    """Test that gather preserves order as documented."""
    
    class OrderPreservingService:
        def submit(self, task: SimTask) -> FutureLike:
            return (str(task.entrypoint), task.seed)
        
        def gather(self, futures: list[FutureLike]) -> list[SimReturn]:
            # Must return in same order
            return [
                SimReturn(
                    task_id=f"task_{i}",
                    sim_root="1" * 64,
                    outputs={f"result_{i}": TableArtifact(
                        size=4,
                        inline=b"data",
                        checksum="2" * 64
                    )}
                )
                for i, _ in enumerate(futures)
            ]
    
    service = OrderPreservingService()
    tasks = [
        SimTask(
            bundle_ref="sha256:b123456789012345678901234567890123",
            entrypoint=f"pkg.Fn{i}/baseline@b12345678901",
            params=UniqueParameterSet.from_dict({}),
            seed=i
        )
        for i in range(1, 4)
    ]
    futures = [service.submit(task) for task in tasks]
    
    results = service.gather(futures)
    assert len(results) == 3
    assert "result_0" in results[0].outputs
    assert "result_1" in results[1].outputs
    assert "result_2" in results[2].outputs
