"""Tests for provenance computation."""

import pytest
import json
import math
from modelops_contracts import (
    ProvenanceLeaf,
    sim_root,
    calib_root,
    canonical_json,
    digest_bytes,
    shard,
    ContractViolationError,
)
from modelops_contracts.provenance import (
    canonical_scalar,
    normalize_for_json,
    hash_leaf_from_json,
    hash_leaf_from_bytes,
    compute_root,
    make_param_id,
)


def test_canonical_scalar():
    """Test scalar canonicalization."""
    # Booleans
    assert canonical_scalar(True) is True
    assert canonical_scalar(False) is False
    
    # Integers
    assert canonical_scalar(42) == 42
    assert canonical_scalar(-1) == -1
    assert canonical_scalar(0) == 0
    
    # Floats
    assert canonical_scalar(3.14) == 3.14
    assert canonical_scalar(-2.5) == -2.5
    
    # Floats (no negative zero normalization)
    assert canonical_scalar(-0.0) == -0.0
    assert canonical_scalar(0.0) == 0.0
    
    # Strings
    assert canonical_scalar("hello") == "hello"
    assert canonical_scalar("") == ""
    
    # Non-finite floats should raise
    with pytest.raises(ContractViolationError, match="Non-finite float"):
        canonical_scalar(float('nan'))
    
    with pytest.raises(ContractViolationError, match="Non-finite float"):
        canonical_scalar(float('inf'))
    
    with pytest.raises(ContractViolationError, match="Non-finite float"):
        canonical_scalar(float('-inf'))
    
    # Unsupported types
    with pytest.raises(ContractViolationError, match="Unsupported type"):
        canonical_scalar([1, 2, 3])
    
    with pytest.raises(ContractViolationError, match="Unsupported type"):
        canonical_scalar(None)


def test_normalize_for_json():
    """Test recursive normalization for JSON."""
    # Simple values
    assert normalize_for_json(None) is None
    assert normalize_for_json(True) is True
    assert normalize_for_json(42) == 42
    assert normalize_for_json("text") == "text"
    
    # Floats in nested structures (no negative zero normalization)
    data = {
        "a": -0.0,
        "b": [1, -0.0, 3],
        "c": {"x": -0.0, "y": 0.0}
    }
    normalized = normalize_for_json(data)
    assert normalized["a"] == -0.0
    assert normalized["b"][1] == -0.0
    assert normalized["c"]["x"] == -0.0
    assert normalized["c"]["y"] == 0.0
    
    # Dict keys are sorted
    unordered = {"z": 1, "a": 2, "m": 3}
    normalized = normalize_for_json(unordered)
    assert list(normalized.keys()) == ["a", "m", "z"]
    
    # Tuples become lists
    assert normalize_for_json((1, 2, 3)) == [1, 2, 3]
    
    # Nested normalization (no negative zero normalization)
    complex_data = {
        "params": {"beta": -0.0, "alpha": 1.5},
        "values": [1, 2, -0.0, 4],
        "nested": {
            "deep": {
                "value": -0.0
            }
        }
    }
    result = normalize_for_json(complex_data)
    assert result["params"]["beta"] == -0.0
    assert result["values"][2] == -0.0
    assert result["nested"]["deep"]["value"] == -0.0


def test_canonical_json():
    """Test canonical JSON generation."""
    # Simple object
    obj = {"b": 2, "a": 1}
    canonical = canonical_json(obj)
    assert canonical == b'{"a":1,"b":2}'
    
    # With negative zero (no longer normalized)
    obj = {"value": -0.0}
    canonical = canonical_json(obj)
    assert canonical == b'{"value":-0.0}'
    
    # Complex nested structure
    obj = {
        "z": {"nested": True},
        "a": [1, 2, 3],
        "m": "string"
    }
    canonical = canonical_json(obj)
    expected = b'{"a":[1,2,3],"m":"string","z":{"nested":true}}'
    assert canonical == expected
    
    # UTF-8 encoding
    obj = {"emoji": "🔬", "text": "résumé"}
    canonical = canonical_json(obj)
    assert b'\xf0\x9f\x94\xac' in canonical  # UTF-8 encoded emoji
    assert b'r\xc3\xa9sum\xc3\xa9' in canonical  # UTF-8 encoded accents


def test_digest_bytes():
    """Test BLAKE2b-256 hashing."""
    # Known test vector
    data = b"hello world"
    digest = digest_bytes(data)
    assert len(digest) == 64  # Hex string
    assert all(c in "0123456789abcdef" for c in digest)
    
    # Empty data
    empty_digest = digest_bytes(b"")
    assert len(empty_digest) == 64
    
    # Deterministic
    assert digest_bytes(b"test") == digest_bytes(b"test")
    assert digest_bytes(b"test1") != digest_bytes(b"test2")


def test_provenance_leaf():
    """Test ProvenanceLeaf validation."""
    # Valid leaf
    leaf = ProvenanceLeaf(
        kind="params",
        name="base",
        digest="a" * 64
    )
    assert leaf.kind == "params"
    assert leaf.name == "base"
    assert leaf.digest == "a" * 64
    
    # Invalid digest (wrong length)
    with pytest.raises(ContractViolationError, match="64-character hex string"):
        ProvenanceLeaf(
            kind="params",
            name="test",
            digest="short"
        )
    
    # Invalid digest (non-hex)
    with pytest.raises(ContractViolationError, match="64-character hex string"):
        ProvenanceLeaf(
            kind="params",
            name="test",
            digest="x" * 64
        )


def test_hash_leaf_from_json():
    """Test creating leaf from JSON object."""
    params = {"learning_rate": 0.01, "batch_size": 32}
    leaf = hash_leaf_from_json("params", "base", params)
    
    assert leaf.kind == "params"
    assert leaf.name == "base"
    assert len(leaf.digest) == 64
    
    # Same input gives same digest
    leaf2 = hash_leaf_from_json("params", "base", params)
    assert leaf.digest == leaf2.digest
    
    # Different input gives different digest
    params2 = {"learning_rate": 0.02, "batch_size": 32}
    leaf3 = hash_leaf_from_json("params", "base", params2)
    assert leaf.digest != leaf3.digest


def test_hash_leaf_from_bytes():
    """Test creating leaf from raw bytes."""
    data = b"binary data"
    leaf = hash_leaf_from_bytes("code", "sim", data)
    
    assert leaf.kind == "code"
    assert leaf.name == "sim"
    assert len(leaf.digest) == 64
    
    # Same bytes give same digest
    leaf2 = hash_leaf_from_bytes("code", "sim", data)
    assert leaf.digest == leaf2.digest


def test_compute_root():
    """Test root hash computation from leaves."""
    leaves = [
        hash_leaf_from_json("params", "base", {"a": 1}),
        hash_leaf_from_json("config", "patch", {"b": 2}),
        hash_leaf_from_bytes("code", "sim", b"code123"),
    ]
    
    root = compute_root(leaves)
    assert len(root) == 64
    assert all(c in "0123456789abcdef" for c in root)
    
    # Order shouldn't matter (sorted internally)
    leaves_reordered = [leaves[2], leaves[0], leaves[1]]
    root2 = compute_root(leaves_reordered)
    assert root == root2
    
    # Different leaves give different root
    leaves_modified = leaves[:-1] + [
        hash_leaf_from_bytes("code", "sim", b"different")
    ]
    root3 = compute_root(leaves_modified)
    assert root != root3


def test_sim_root():
    """Test simulation root computation."""
    params = {"alpha": 0.5, "beta": 1.0}
    config = {"max_iter": 1000}
    seed = 42
    bundle_ref = "sha256:abc123456789012345678901234567890"
    entrypoint = "model.Main/baseline"
    env = {"python": "3.11"}
    
    root = sim_root(
        bundle_ref=bundle_ref,
        params=params,
        seed=seed,
        entrypoint=entrypoint,
        config=config,
        env=env
    )
    
    assert len(root) == 64
    assert all(c in "0123456789abcdef" for c in root)
    
    # Same inputs give same root
    root2 = sim_root(
        bundle_ref=bundle_ref,
        params=params,
        seed=seed,
        entrypoint=entrypoint,
        config=config,
        env=env
    )
    assert root == root2
    
    # Different seed gives different root
    root3 = sim_root(
        bundle_ref=bundle_ref,
        params=params,
        seed=43,  # Different
        entrypoint=entrypoint,
        config=config,
        env=env
    )
    assert root != root3
    
    # Different scenario (in entrypoint) gives different root
    root4 = sim_root(
        bundle_ref=bundle_ref,
        params=params,
        seed=seed,
        entrypoint="model.Main/high_growth",  # Different scenario
        config=config,
        env=env
    )
    assert root != root4


def test_calib_root():
    """Test calibration root computation."""
    targets_id = "targets:v1:abc"
    optimizer_id = "optim:adam:config1"
    sim_roots = [
        "a" * 64,
        "b" * 64,
        "c" * 64
    ]
    calib_code_id = "calibrator:v2"
    env_id = "python:3.11"
    
    root = calib_root(
        targets_id=targets_id,
        optimizer_id=optimizer_id,
        sim_roots=sim_roots,
        calib_code_id=calib_code_id,
        env_id=env_id
    )
    
    assert len(root) == 64
    assert all(c in "0123456789abcdef" for c in root)
    
    # Order of sim_roots shouldn't matter (sorted internally)
    sim_roots_reordered = [sim_roots[2], sim_roots[0], sim_roots[1]]
    root2 = calib_root(
        targets_id=targets_id,
        optimizer_id=optimizer_id,
        sim_roots=sim_roots_reordered,
        calib_code_id=calib_code_id,
        env_id=env_id
    )
    assert root == root2
    
    # Different targets give different root
    root3 = calib_root(
        targets_id="targets:v2:def",  # Different
        optimizer_id=optimizer_id,
        sim_roots=sim_roots,
        calib_code_id=calib_code_id,
        env_id=env_id
    )
    assert root != root3


def test_shard():
    """Test digest sharding for filesystem storage."""
    digest = "abcdef1234567890" + "0" * 48
    
    # Default sharding (depth=2, width=2)
    sharded = shard(digest)
    assert sharded == f"ab/cd/{digest}"
    
    # Custom depth and width
    sharded = shard(digest, depth=3, width=2)
    assert sharded == f"ab/cd/ef/{digest}"
    
    sharded = shard(digest, depth=2, width=3)
    assert sharded == f"abc/def/{digest}"
    
    sharded = shard(digest, depth=1, width=4)
    assert sharded == f"abcd/{digest}"
    
    # Too short digest
    with pytest.raises(ContractViolationError, match="Digest too short for sharding"):
        shard("abc", depth=2, width=2)


def test_make_param_id():
    """Test backward-compatible parameter ID generation."""
    params = {
        "learning_rate": 0.01,
        "batch_size": 32,
        "dropout": 0.5
    }
    
    param_id = make_param_id(params)
    assert len(param_id) == 64
    assert all(c in "0123456789abcdef" for c in param_id)
    
    # Same params give same ID
    param_id2 = make_param_id(params)
    assert param_id == param_id2
    
    # Different params give different ID
    params2 = {**params, "learning_rate": 0.02}
    param_id3 = make_param_id(params2)
    assert param_id != param_id3
    
    # Order shouldn't matter (canonical JSON sorts keys)
    params_reordered = {
        "dropout": 0.5,
        "batch_size": 32,
        "learning_rate": 0.01
    }
    param_id4 = make_param_id(params_reordered)
    assert param_id == param_id4
    
    # Handles negative zero (no longer normalized to be the same)
    params_with_neg_zero = {"value": -0.0}
    params_with_pos_zero = {"value": 0.0}
    # These are now different since we don't normalize -0.0 to 0.0
    assert make_param_id(params_with_neg_zero) != make_param_id(params_with_pos_zero)