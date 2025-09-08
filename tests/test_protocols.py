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
    FutureLike,
)


def test_simulation_service_protocol():
    """Test that SimulationService protocol works as expected."""
    
    # Create a minimal implementation
    class MockSimService:
        def submit(self, fn_ref: str, params: dict[str, Scalar], seed: int, *, bundle_ref: str) -> FutureLike:
            return f"future_{fn_ref}_{seed}"
        
        def submit_batch(self, fn_ref: str, params_list: list[dict[str, Scalar]], 
                         seeds: list[int], *, bundle_ref: str) -> list[FutureLike]:
            return [f"future_{fn_ref}_{seed}" for seed in seeds]
        
        def submit_replicates(self, fn_ref: str, params: dict[str, Scalar],
                              seed: int, *, bundle_ref: str, 
                              n_replicates: int) -> list[FutureLike]:
            return [f"future_{fn_ref}_{seed}_{i}" for i in range(n_replicates)]
        
        def gather(self, futures: list[FutureLike]) -> list[SimReturn]:
            # Return empty results in same order as futures
            return [{} for _ in futures]
        
        def gather_and_aggregate(self, futures: list[FutureLike],
                                 aggregator) -> SimReturn:
            results = self.gather(futures)
            return aggregator(results)
    
    # Should satisfy the protocol
    service = MockSimService()
    assert isinstance(service, SimulationService)
    
    # Test basic usage
    future = service.submit("pkg.mod:func", {"x": 1.0}, 42, bundle_ref="bundle:v1")
    assert future == "future_pkg.mod:func_42"
    
    results = service.gather([future, future])
    assert len(results) == 2
    assert all(isinstance(r, dict) for r in results)


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
    
    # SimReturn is a mapping of string to bytes
    sim_return: SimReturn = {
        "infected": b"table1_data",
        "deaths": b"table2_data"
    }
    assert isinstance(sim_return, dict)
    assert all(isinstance(k, str) for k in sim_return.keys())
    assert all(isinstance(v, bytes) for v in sim_return.values())
    
    # FutureLike is Any - accepts anything
    future: FutureLike = "any_object"
    assert future == "any_object"
    future = 42
    assert future == 42


def test_protocol_ordering_guarantee():
    """Test that gather preserves order as documented."""
    
    class OrderPreservingService:
        def submit(self, fn_ref: str, params: dict[str, Scalar], seed: int, *, bundle_ref: str) -> FutureLike:
            return (fn_ref, seed)
        
        def gather(self, futures: list[FutureLike]) -> list[SimReturn]:
            # Must return in same order
            return [{f"result_{i}": b"data"} for i, _ in enumerate(futures)]
    
    service = OrderPreservingService()
    futures = [
        service.submit("fn1", {}, 1, bundle_ref="b"),
        service.submit("fn2", {}, 2, bundle_ref="b"),
        service.submit("fn3", {}, 3, bundle_ref="b"),
    ]
    
    results = service.gather(futures)
    assert len(results) == 3
    assert "result_0" in results[0]
    assert "result_1" in results[1]
    assert "result_2" in results[2]
