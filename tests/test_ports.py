"""Tests for port protocols."""

from typing import Optional, List, Dict, Any, Tuple, Mapping
from pathlib import Path

from modelops_contracts import (
    Future,
    SimulationService,
    ExecutionEnvironment,
    BundleRepository,
    CAS,
    WireFunction,
    SimTask,
    SimReturn,
    EntryPointId,
    UniqueParameterSet,
)


def test_future_protocol():
    """Test that Future protocol can be implemented."""
    
    class MockFuture:
        def __init__(self, value):
            self._value = value
            self._exception = None
        
        def result(self, timeout: Optional[float] = None):
            if self._exception:
                raise self._exception
            return self._value
        
        def done(self) -> bool:
            return True
        
        def cancel(self) -> bool:
            return False
        
        def exception(self) -> Optional[Exception]:
            return self._exception
    
    # Should be a valid Future implementation
    future: Future[str] = MockFuture("test")
    assert future.result() == "test"
    assert future.done() is True
    assert future.cancel() is False
    assert future.exception() is None


def test_simulation_service_protocol():
    """Test that SimulationService protocol can be implemented."""
    
    class MockSimulationService:
        def submit(self, task: SimTask) -> Future[SimReturn]:
            from modelops_contracts import TableArtifact
            class SimpleFuture:
                def result(self, timeout=None):
                    return SimReturn(
                        task_id=task.task_id(),
                        sim_root=task.sim_root(),
                        outputs={"test": TableArtifact(
                    size=4,
                    inline=b"data",
                    checksum="a" * 64  # Valid 64-char hex
                )}
                    )
                def done(self): return True
                def cancel(self): return False
                def exception(self): return None
            return SimpleFuture()
        
        def gather(self, futures: List[Future[SimReturn]]) -> List[SimReturn]:
            return [f.result() for f in futures]
        
        def submit_batch(self, tasks: List[SimTask]) -> List[Future[SimReturn]]:
            return [self.submit(t) for t in tasks]
    
    # Should be a valid SimulationService implementation
    service: SimulationService = MockSimulationService()
    
    task = SimTask(
        bundle_ref="sha256:abc",
        entrypoint="test.Model/baseline",
        params=UniqueParameterSet.from_dict({"x": 1}),
        seed=42
    )
    
    future = service.submit(task)
    assert future.result().task_id == task.task_id()


def test_execution_environment_protocol():
    """Test that ExecutionEnvironment protocol can be implemented."""
    
    class MockExecutionEnvironment:
        def run(self, task: SimTask) -> SimReturn:
            from modelops_contracts import TableArtifact
            return SimReturn(
                task_id=task.task_id(),
                sim_root=task.sim_root(),
                outputs={"test": TableArtifact(
                    size=4,
                    inline=b"data",
                    checksum="a" * 64  # Valid 64-char hex
                )}
            )
        
        def health_check(self) -> Dict[str, Any]:
            return {"status": "healthy", "type": "mock"}
        
        def shutdown(self) -> None:
            pass  # Clean shutdown
    
    # Should be a valid ExecutionEnvironment implementation
    env: ExecutionEnvironment = MockExecutionEnvironment()
    
    task = SimTask(
        bundle_ref="sha256:abc",
        entrypoint="test.Model/baseline",
        params=UniqueParameterSet.from_dict({"x": 1}),
        seed=42
    )
    
    result = env.run(task)
    assert result.task_id == task.task_id()
    
    health = env.health_check()
    assert health["status"] == "healthy"
    
    env.shutdown()  # Should not raise


def test_bundle_repository_protocol():
    """Test that BundleRepository protocol can be implemented."""
    
    class MockBundleRepository:
        def ensure_local(self, bundle_ref: str) -> Tuple[str, Path]:
            digest = bundle_ref.split(":")[-1] if ":" in bundle_ref else bundle_ref
            return digest, Path(f"/tmp/bundles/{digest}")
        
        def exists(self, bundle_ref: str) -> bool:
            return True
    
    # Should be a valid BundleRepository implementation
    repo: BundleRepository = MockBundleRepository()
    
    digest, path = repo.ensure_local("sha256:abc123")
    assert digest == "abc123"
    assert str(path) == "/tmp/bundles/abc123"
    assert repo.exists("sha256:abc123") is True


def test_cas_protocol():
    """Test that CAS protocol can be implemented."""
    
    class MockCAS:
        def __init__(self):
            self._store = {}
        
        def put(self, data: bytes, checksum_hex: str) -> str:
            ref = f"cas://{checksum_hex}"
            self._store[ref] = data
            return ref
        
        def get(self, ref: str) -> bytes:
            if ref not in self._store:
                raise KeyError(f"Not found: {ref}")
            return self._store[ref]
        
        def exists(self, ref: str) -> bool:
            return ref in self._store
    
    # Should be a valid CAS implementation
    cas: CAS = MockCAS()
    
    data = b"test data"
    ref = cas.put(data, "abc123")
    assert ref == "cas://abc123"
    assert cas.get(ref) == data
    assert cas.exists(ref) is True
    assert cas.exists("cas://nonexistent") is False


def test_wire_function_protocol():
    """Test that WireFunction protocol can be implemented."""
    
    class MockWireFunction:
        def __call__(
            self,
            entrypoint: EntryPointId,
            params: Mapping[str, Any],
            seed: int
        ) -> Dict[str, bytes]:
            # Simulate returning Arrow IPC bytes
            return {
                "output1": b"arrow_data_1",
                "output2": b"arrow_data_2"
            }
    
    # Should be a valid WireFunction implementation
    wire_fn: WireFunction = MockWireFunction()
    
    outputs = wire_fn(
        EntryPointId("test.Model/baseline"),
        {"x": 1.0, "y": 2.0},
        42
    )
    
    assert outputs["output1"] == b"arrow_data_1"
    assert outputs["output2"] == b"arrow_data_2"


def test_protocol_runtime_checkability():
    """Test that protocols can be checked at runtime."""
    from modelops_contracts import TableArtifact
    
    # Our protocols should work with isinstance checks if needed
    class ConcreteEnv:
        def run(self, task): 
            return SimReturn(
                task_id="a" * 64,  # Valid 64-char hex
                sim_root="b" * 64,  # Valid 64-char hex  
                outputs={"test": TableArtifact(
                    size=4,
                    inline=b"data",
                    checksum="a" * 64  # Valid 64-char hex
                )}
            )
        def health_check(self): return {}
        def shutdown(self): pass
    
    # Can't use isinstance with non-runtime_checkable protocols
    # But they work fine for static typing
    env: ExecutionEnvironment = ConcreteEnv()
    assert env.health_check() == {}