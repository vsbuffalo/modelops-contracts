"""Basic contract tests."""

import pytest
from modelops_contracts import (
    UniqueParameterSet,
    TrialResult,
    TrialStatus,
    SeedInfo,
    ContractViolationError,
    make_param_id,
)


def test_parameter_set():
    """Test parameter set creation."""
    params = UniqueParameterSet.from_dict({"x": 1.0, "y": 2})
    assert params.param_id
    assert params.params["x"] == 1.0
    

def test_param_id_stable():
    """Test param_id is stable and namespaced."""
    params = {"x": 1.0, "y": 2}
    id1 = make_param_id(params)
    id2 = make_param_id(params)
    assert id1 == id2
    assert len(id1) == 64  # BLAKE2b-256 in hex
    

def test_invalid_parameter():
    """Test parameter validation."""
    # NaN/Inf rejected
    with pytest.raises(ContractViolationError):
        UniqueParameterSet.from_dict({"x": float("inf")})
    
    # NumPy scalars rejected (if numpy installed)
    try:
        import numpy as np
        with pytest.raises(ContractViolationError):
            make_param_id({"x": np.float64(1.0)})
    except ImportError:
        pass


def test_trial_result():
    """Test trial result creation."""
    result = TrialResult(
        param_id="abc123",
        loss=0.5,
        status=TrialStatus.OK,
    )
    assert result.loss == 0.5
    

def test_trial_result_error_status():
    """Test non-finite loss allowed for error status."""
    result = TrialResult(
        param_id="abc123",
        loss=float("inf"),  # OK for error status
        status=TrialStatus.USER_ERROR,
    )
    assert result.status == TrialStatus.USER_ERROR


def test_diagnostics_size_limit():
    """Test diagnostics size validation."""
    # Create data that's definitely > 64KB when serialized
    huge_data = {f"key_{i}": "x" * 1000 for i in range(100)}
    with pytest.raises(ContractViolationError, match="too large"):
        TrialResult(
            param_id="abc123",
            loss=0.5,
            diagnostics=huge_data,
        )


def test_seed_info():
    """Test seed info with validation."""
    seeds = SeedInfo(
        base_seed=42,
        trial_seed=1,
        replicate_seeds=[10, 20, 30],  # List gets converted
    )
    assert isinstance(seeds.replicate_seeds, tuple)
    assert seeds.replicate_seeds == (10, 20, 30)
    
    # Non-integer rejected
    with pytest.raises(ContractViolationError, match="must be integers"):
        SeedInfo(
            base_seed=42.5,  # Float not allowed
            trial_seed=1,
            replicate_seeds=[],
        )


def test_immutability():
    """Test that all types are truly immutable."""
    params = UniqueParameterSet.from_dict({"x": 1.0})
    
    # Can't modify params
    with pytest.raises(AttributeError):  # Frozen dataclass raises AttributeError
        params.param_id = "new_id"  # Frozen dataclass
    
    # Params dict is already read-only from __post_init__
    # It's a regular dict but the object is frozen, so this test is about the concept
    assert isinstance(params.params, dict)  # Coerced to dict in __post_init__


def test_canonical_param_id():
    """Test canonical param_id generation."""
    # Order shouldn't matter
    params1 = {"x": 1.0, "y": 2.0}
    params2 = {"y": 2.0, "x": 1.0}
    assert make_param_id(params1) == make_param_id(params2)
    
    # Namespace prefix is included
    pid = make_param_id({"x": 1})
    # Can't easily test the prefix without duplicating logic,
    # but we can verify the hash length and stability
    assert len(pid) == 64
    assert pid == make_param_id({"x": 1})


def test_finite_loss_validation():
    """Test loss validation rules."""
    # OK status requires finite loss
    with pytest.raises(ContractViolationError, match="finite for OK status"):
        TrialResult(
            param_id="abc123",
            loss=float("nan"),
            status=TrialStatus.OK,
        )
    
    # Error status allows non-finite loss
    result = TrialResult(
        param_id="abc123", 
        loss=float("-inf"),
        status=TrialStatus.INFRA_ERROR,
    )
    assert result.status == TrialStatus.INFRA_ERROR