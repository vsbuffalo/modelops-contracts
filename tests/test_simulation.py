"""Tests for simulation task specification."""

import pytest
from types import MappingProxyType
from modelops_contracts import (
    SimTask,
    UniqueParameterSet,
    ContractViolationError,
    EntryPointId,
)


def test_sim_task_creation():
    """Test basic SimTask creation."""
    params = UniqueParameterSet(
        param_id="abc123",
        params={"learning_rate": 0.01, "batch_size": 32}
    )
    
    task = SimTask(
        bundle_ref="sha256:abcdef1234567890fedcba0987654321",
        entrypoint="model.main.Simulate/baseline@abcdef123456",
        params=params,
        seed=42
    )
    
    assert task.bundle_ref == "sha256:abcdef1234567890fedcba0987654321"
    assert str(task.entrypoint) == "model.main.Simulate/baseline@abcdef123456"
    assert isinstance(task.entrypoint, str)  # It's an EntryPointId (which is a str)
    assert task.params.param_id == "abc123"
    assert task.seed == 42
    assert task.outputs is None


def test_sim_task_with_optional_fields():
    """Test SimTask with all optional fields."""
    params = UniqueParameterSet(
        param_id="def456",
        params={"alpha": 0.5}
    )
    
    task = SimTask(
        bundle_ref="sha256:fedcba6543210987654321098765432109",
        entrypoint="sim.core.Run/high_growth@fedcba654321",
        params=params,
        seed=1337,
        outputs=["population", "gdp"],
    )
    
    assert task.outputs == ("gdp", "population")  # Sorted alphabetically


def test_sim_task_immutability():
    """Test that SimTask is properly frozen."""
    params = UniqueParameterSet(
        param_id="ghi789",
        params={"beta": 2.0}
    )
    
    task = SimTask(
        bundle_ref="sha256:123abc4567890123456789012345678901",
        entrypoint="app.Main/baseline@123abc456789",
        params=params,
        seed=99
    )
    
    # Should not be able to modify attributes
    with pytest.raises(AttributeError):
        task.seed = 100
    
    with pytest.raises(AttributeError):
        task.bundle_ref = "sha256:different"




def test_sim_task_validation_errors():
    """Test validation of required fields."""
    params = UniqueParameterSet(
        param_id="mno345",
        params={"delta": 1.5}
    )
    
    # Empty bundle_ref
    with pytest.raises(ContractViolationError, match="bundle_ref must be non-empty"):
        SimTask(
            bundle_ref="",
            entrypoint="main.Run/baseline@abc123456789",
            params=params,
            seed=42
        )
    
    # Empty entrypoint
    with pytest.raises(ContractViolationError, match="entrypoint must be non-empty"):
        SimTask(
            bundle_ref="sha256:abc123456789012345678901234567890",
            entrypoint="",
            params=params,
            seed=42
        )
    
    # Invalid entrypoint format
    with pytest.raises(ContractViolationError, match="Invalid entrypoint format"):
        SimTask(
            bundle_ref="sha256:abc1234567890",
            entrypoint="not:valid:format",
            params=params,
            seed=42
        )
    
    # Wrong type for params
    with pytest.raises(ContractViolationError, match="params must be UniqueParameterSet"):
        SimTask(
            bundle_ref="sha256:abc123456789012345678901234567890",
            entrypoint="main.Run/baseline@abc123456789",
            params={"raw": "dict"},  # Not a UniqueParameterSet
            seed=42
        )
    
    # Wrong type for seed
    with pytest.raises(ContractViolationError, match="seed must be int"):
        SimTask(
            bundle_ref="sha256:abc123456789012345678901234567890",
            entrypoint="main.Run/baseline@abc123456789",
            params=params,
            seed="42"  # String instead of int
        )
    
    # Seed out of range
    with pytest.raises(ContractViolationError, match="seed .* out of uint64 range"):
        SimTask(
            bundle_ref="sha256:abc123456789012345678901234567890",
            entrypoint="main.Run/baseline@abc123456789",
            params=params,
            seed=-1
        )
    
    with pytest.raises(ContractViolationError, match="seed .* out of uint64 range"):
        SimTask(
            bundle_ref="sha256:abc123456789012345678901234567890",
            entrypoint="main.Run/baseline@abc123456789",
            params=params,
            seed=2**64  # Too large
        )


def test_sim_task_outputs_conversion():
    """Test that outputs list is converted to tuple."""
    params = UniqueParameterSet(
        param_id="pqr678",
        params={"epsilon": 0.001}
    )
    
    # With list
    task = SimTask(
        bundle_ref="sha256:qwerty123456789012345678901234567890",
        entrypoint="sim.Run/baseline@qwerty123456",  # 12 chars to match DIGEST_PREFIX_LEN
        params=params,
        seed=777,
        outputs=["metric1", "metric2", "metric3"]
    )
    
    assert isinstance(task.outputs, tuple)
    assert task.outputs == ("metric1", "metric2", "metric3")  # Already alphabetically sorted
    
    # With tuple (should remain tuple)
    task2 = SimTask(
        bundle_ref="sha256:asdfgh123456789012345678901234567890",
        entrypoint="sim.Run/baseline@asdfgh123456",  # Fixed to match bundle_ref
        params=params,
        seed=888,
        outputs=("result1", "result2")
    )
    
    assert isinstance(task2.outputs, tuple)
    assert task2.outputs == ("result1", "result2")  # Already alphabetically sorted


def test_sim_task_id_generation():
    """Test task_id() method generates consistent IDs."""
    params = UniqueParameterSet(
        param_id="stu901",
        params={"zeta": 3.14}
    )
    
    task1 = SimTask(
        bundle_ref="sha256:identical123456789012345678901234567890",
        entrypoint="same.Function/base@identical123",
        params=params,
        seed=100,
        outputs=["out1", "out2"]
    )
    
    # Same inputs should give same ID
    task2 = SimTask(
        bundle_ref="sha256:identical123456789012345678901234567890",
        entrypoint="same.Function/base@identical123",
        params=params,
        seed=100,
        outputs=["out1", "out2"]
    )
    
    assert task1.task_id() == task2.task_id()
    
    # Different seed should give different ID
    task3 = SimTask(
        bundle_ref="sha256:identical123456789012345678901234567890",
        entrypoint="same.Function/base@identical123",
        params=params,
        seed=101,  # Different seed
        outputs=["out1", "out2"]
    )
    
    assert task1.task_id() != task3.task_id()
    
    # ID should be hex string of correct length
    task_id = task1.task_id()
    assert len(task_id) == 64
    assert all(c in "0123456789abcdef" for c in task_id)


def test_sim_task_equality():
    """Test that SimTask supports equality comparison."""
    params = UniqueParameterSet(
        param_id="vwx234",
        params={"theta": 0.7}
    )
    
    task1 = SimTask(
        bundle_ref="sha256:hashme123456789012345678901234567890",
        entrypoint="app.Start/baseline@hashme123456",
        params=params,
        seed=2048
    )
    
    task2 = SimTask(
        bundle_ref="sha256:hashme123456789012345678901234567890",
        entrypoint="app.Start/baseline@hashme123456",
        params=params,
        seed=2048
    )
    
    task3 = SimTask(
        bundle_ref="sha256:different123456789012345678901234567890",
        entrypoint="app.Start/baseline@different123",
        params=params,
        seed=2048
    )
    
    # Same values should be equal
    assert task1 == task2
    
    # Different values should not be equal
    assert task1 != task3


def test_from_components_basic():
    """Test creating SimTask using from_components factory."""
    task = SimTask.from_components(
        import_path="my_model.simulations.SEIR",
        scenario="baseline",
        bundle_ref="sha256:abc123def456789012345678901234567890",
        params={"R0": 2.5, "incubation_days": 5},
        seed=42
    )
    
    assert task.bundle_ref == "sha256:abc123def456789012345678901234567890"
    assert str(task.entrypoint) == "my_model.simulations.SEIR/baseline@abc123def456"
    assert task.params.params["R0"] == 2.5
    assert task.params.params["incubation_days"] == 5
    assert task.seed == 42
    assert task.outputs is None
    assert task.config is None
    assert task.env is None


def test_from_components_with_outputs():
    """Test from_components with outputs sorting."""
    task = SimTask.from_components(
        import_path="covid.models.Main",
        scenario="lockdown",
        bundle_ref="sha256:fedcba098765432109876543210987654321",
        params={"beta": 0.5},
        seed=100,
        outputs=["hospitalizations", "deaths", "infections"]  # Unsorted
    )
    
    # Outputs should be sorted alphabetically
    assert task.outputs == ("deaths", "hospitalizations", "infections")


def test_from_components_with_config_env():
    """Test from_components with config and env."""
    config = {"max_iterations": 1000, "tolerance": 0.001}
    env = {"PYTHON_VERSION": "3.11", "NUM_THREADS": "4"}
    
    task = SimTask.from_components(
        import_path="sim.Engine",
        scenario="test",
        bundle_ref="sha256:123abc456def789012345678901234567890",
        params={"x": 1.0},
        seed=777,
        config=config,
        env=env
    )
    
    assert task.config is not None
    assert task.env is not None
    
    # Should be frozen as MappingProxyType
    from types import MappingProxyType
    assert isinstance(task.config, MappingProxyType)
    assert isinstance(task.env, MappingProxyType)
    
    # Values should be preserved
    assert task.config["max_iterations"] == 1000
    assert task.env["PYTHON_VERSION"] == "3.11"
    
    # Should be immutable
    with pytest.raises(TypeError):
        task.config["new_key"] = "value"
    with pytest.raises(TypeError):
        task.env["new_key"] = "value"


def test_from_components_generates_param_id():
    """Test that from_components generates param_id automatically."""
    params = {"alpha": 0.5, "beta": 1.0}
    
    task = SimTask.from_components(
        import_path="test.Model",
        scenario="baseline",
        bundle_ref="sha256:aaa111bbb222ccc333ddd444eee555fff666777",
        params=params,
        seed=42
    )
    
    # Should have a param_id
    assert task.params.param_id
    assert len(task.params.param_id) == 64  # SHA256 hex digest
    
    # Same params should give same param_id
    task2 = SimTask.from_components(
        import_path="test.Model",
        scenario="baseline",
        bundle_ref="sha256:aaa111bbb222ccc333ddd444eee555fff666777",
        params=params,
        seed=42
    )
    assert task.params.param_id == task2.params.param_id


def test_from_components_sim_root_includes_config():
    """Test that sim_root includes config when present."""
    task_without_config = SimTask.from_components(
        import_path="model.Sim",
        scenario="base",
        bundle_ref="sha256:abc123456789012345678901234567890123456",
        params={"p": 1},
        seed=10
    )
    
    task_with_config = SimTask.from_components(
        import_path="model.Sim",
        scenario="base",
        bundle_ref="sha256:abc123456789012345678901234567890123456",
        params={"p": 1},
        seed=10,
        config={"option": "value"}
    )
    
    # sim_root should be different when config is present
    assert task_without_config.sim_root() != task_with_config.sim_root()
    
    # task_id should also be different (since it includes sim_root)
    assert task_without_config.task_id() != task_with_config.task_id()


def test_from_entrypoint_basic():
    """Test creating SimTask using from_entrypoint factory."""
    task = SimTask.from_entrypoint(
        entrypoint="my_model.simulations.SEIR/baseline@abc123def456",
        bundle_ref="sha256:abc123def456789012345678901234567890",
        params={"R0": 2.5, "incubation_days": 5},
        seed=42
    )
    
    assert task.bundle_ref == "sha256:abc123def456789012345678901234567890"
    assert str(task.entrypoint) == "my_model.simulations.SEIR/baseline@abc123def456"
    assert task.params.params["R0"] == 2.5
    assert task.params.params["incubation_days"] == 5
    assert task.seed == 42
    assert task.outputs is None


def test_from_entrypoint_validates_bundle():
    """Test that from_entrypoint validates bundle match."""
    # Valid case - digest matches
    task = SimTask.from_entrypoint(
        entrypoint="test.Model/scenario@fedcba098765",
        bundle_ref="sha256:fedcba098765432109876543210987654321",
        params={"x": 1},
        seed=10
    )
    assert task is not None
    
    # Invalid case - digest doesn't match
    with pytest.raises(ContractViolationError, match="doesn't match bundle_ref"):
        SimTask.from_entrypoint(
            entrypoint="test.Model/scenario@abc123456789",
            bundle_ref="sha256:fedcba098765432109876543210987654321",  # Different digest!
            params={"x": 1},
            seed=10
        )


def test_simtask_validation_in_post_init():
    """Test that __post_init__ validates entrypoint/bundle match."""
    # Direct constructor should also validate
    with pytest.raises(ContractViolationError, match="doesn't match bundle_ref"):
        SimTask(
            bundle_ref="sha256:wrongdigest12345678901234567890123456",
            entrypoint="test.Model/base@abc123456789",  # Doesn't match!
            params=UniqueParameterSet.from_dict({"p": 1}),
            seed=42
        )


def test_from_components_roundtrip():
    """Test roundtrip: from_components → entrypoint → from_entrypoint."""
    # Create with from_components
    task1 = SimTask.from_components(
        import_path="roundtrip.test.Model",
        scenario="baseline",
        bundle_ref="sha256:abc123def456789012345678901234567890",
        params={"alpha": 0.5, "beta": 1.0},
        seed=100,
        outputs=["metric1", "metric2"],
        config={"iterations": 1000}
    )
    
    # Extract the entrypoint
    entrypoint_str = str(task1.entrypoint)
    
    # Create again with from_entrypoint
    task2 = SimTask.from_entrypoint(
        entrypoint=entrypoint_str,
        bundle_ref="sha256:abc123def456789012345678901234567890",
        params={"alpha": 0.5, "beta": 1.0},
        seed=100,
        outputs=["metric1", "metric2"],
        config={"iterations": 1000}
    )
    
    # Should have same values
    assert task1.entrypoint == task2.entrypoint
    assert task1.bundle_ref == task2.bundle_ref
    assert task1.params.param_id == task2.params.param_id
    assert task1.seed == task2.seed
    assert task1.outputs == task2.outputs
    assert dict(task1.config) == dict(task2.config)
    
    # Should have same hashes
    assert task1.sim_root() == task2.sim_root()
    assert task1.task_id() == task2.task_id()


def test_seed_uint64_bounds():
    """Test that seed is validated to be within uint64 bounds."""
    # Valid seeds
    for seed in [0, 1, 42, 2**32, 2**64 - 1]:
        task = SimTask.from_components(
            import_path="test.Model",
            scenario="test",
            bundle_ref="sha256:abc123456789012345678901234567890123",
            params={},
            seed=seed
        )
        assert task.seed == seed
    
    # Invalid seeds
    for seed in [-1, -100, 2**64, 2**64 + 1]:
        with pytest.raises(ContractViolationError, match="seed .* out of uint64 range"):
            SimTask.from_components(
                import_path="test.Model",
                scenario="test",
                bundle_ref="sha256:abc123456789012345678901234567890123",
                params={},
                seed=seed
            )


def test_outputs_always_sorted():
    """Test that outputs are always sorted regardless of input order."""
    # Test different orderings all produce same result
    orderings = [
        ["zebra", "apple", "mango"],
        ["mango", "zebra", "apple"],
        ["apple", "mango", "zebra"],
    ]
    
    tasks = []
    for outputs in orderings:
        task = SimTask.from_components(
            import_path="test.Sort",
            scenario="test",
            bundle_ref="sha256:def456abc123789012345678901234567890",
            params={"x": 1},
            seed=10,
            outputs=outputs
        )
        tasks.append(task)
    
    # All should have same sorted outputs
    expected = ("apple", "mango", "zebra")
    for task in tasks:
        assert task.outputs == expected
    
    # And same task_id (since outputs are deterministic)
    task_ids = [t.task_id() for t in tasks]
    assert len(set(task_ids)) == 1  # All same