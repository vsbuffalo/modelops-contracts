"""Tests for artifact types."""

import pytest
from modelops_contracts import TableArtifact, SimReturn, INLINE_CAP, ContractViolationError


def test_table_artifact_inline():
    """Test TableArtifact with inline data."""
    data = b"test arrow data"
    checksum = "a" * 64  # Valid hex string
    
    artifact = TableArtifact(
        size=len(data),
        inline=data,
        checksum=checksum
    )
    
    assert artifact.content_type == "application/vnd.apache.arrow.stream"
    assert artifact.size == len(data)
    assert artifact.inline == data
    assert artifact.ref is None
    assert artifact.checksum == checksum


def test_table_artifact_reference():
    """Test TableArtifact with reference to CAS."""
    ref_path = "ab/cd/abcdef123456"
    checksum = "b" * 64
    
    artifact = TableArtifact(
        size=1024 * 1024,  # 1MB
        ref=ref_path,
        checksum=checksum
    )
    
    assert artifact.size == 1024 * 1024
    assert artifact.inline is None
    assert artifact.ref == ref_path
    assert artifact.checksum == checksum


def test_table_artifact_inline_size_limit():
    """Test that inline artifacts respect size limit."""
    # At the limit should work
    data = b"x" * INLINE_CAP
    artifact = TableArtifact(
        size=INLINE_CAP,
        inline=data,
        checksum="c" * 64
    )
    assert artifact.size == INLINE_CAP
    
    # Over the limit should fail
    with pytest.raises(ContractViolationError, match=f"inline artifacts must be <= {INLINE_CAP} bytes"):
        TableArtifact(
            size=INLINE_CAP + 1,
            inline=b"x" * (INLINE_CAP + 1),
            checksum="d" * 64
        )


def test_table_artifact_validation():
    """Test TableArtifact validation."""
    # Negative size
    with pytest.raises(ContractViolationError, match="size must be non-negative"):
        TableArtifact(
            size=-1,
            inline=b"data",
            checksum="e" * 64
        )
    
    # Both inline and ref
    with pytest.raises(ContractViolationError, match="Must provide exactly one of inline or ref"):
        TableArtifact(
            size=100,
            inline=b"data",
            ref="path/to/file",
            checksum="f" * 64
        )
    
    # Neither inline nor ref
    with pytest.raises(ContractViolationError, match="Must provide exactly one of inline or ref"):
        TableArtifact(
            size=100,
            checksum="0" * 64
        )
    
    # Inline size mismatch
    with pytest.raises(ContractViolationError, match="inline bytes length .* doesn't match size"):
        TableArtifact(
            size=100,
            inline=b"short",
            checksum="1" * 64
        )
    
    # Empty ref
    with pytest.raises(ContractViolationError, match="ref must be non-empty when provided"):
        TableArtifact(
            size=100,
            ref="",
            checksum="2" * 64
        )
    
    # Missing checksum
    with pytest.raises(ContractViolationError, match="checksum is required"):
        TableArtifact(
            size=100,
            inline=b"x" * 100,
            checksum=""
        )
    
    # Invalid checksum format (not hex)
    with pytest.raises(ContractViolationError, match="checksum must be 64-character hex string"):
        TableArtifact(
            size=100,
            inline=b"x" * 100,
            checksum="invalid_checksum"
        )
    
    # Invalid checksum length
    with pytest.raises(ContractViolationError, match="checksum must be 64-character hex string"):
        TableArtifact(
            size=100,
            inline=b"x" * 100,
            checksum="abc123"  # Too short
        )


def test_table_artifact_frozen():
    """Test that TableArtifact is immutable."""
    artifact = TableArtifact(
        size=100,
        inline=b"x" * 100,
        checksum="3" * 64
    )
    
    with pytest.raises(AttributeError):
        artifact.size = 200
    
    with pytest.raises(AttributeError):
        artifact.inline = b"new data"


def test_sim_return_basic():
    """Test basic SimReturn creation."""
    data1 = b"output1_data" * 4
    output1 = TableArtifact(
        size=len(data1),
        inline=data1,
        checksum="4" * 64
    )
    
    output2 = TableArtifact(
        size=2000000,
        ref="outputs/large_table",
        checksum="5" * 64
    )
    
    result = SimReturn(
        task_id="task_abc123",
        outputs={"population": output1, "gdp": output2}
    )

    assert result.task_id == "task_abc123"
    assert len(result.outputs) == 2
    assert result.outputs["population"] == output1
    assert result.outputs["gdp"] == output2
    assert result.logs_ref is None
    assert result.metrics is None
    assert result.cached is False


def test_sim_return_with_optional_fields():
    """Test SimReturn with all optional fields."""
    output = TableArtifact(
        size=100,
        inline=b"x" * 100,
        checksum="7" * 64
    )
    
    metrics = {"runtime_seconds": 42.5, "memory_mb": 1024.0}
    
    result = SimReturn(
        task_id="task_xyz789",
        outputs={"result": output},
        logs_ref="logs/sim_xyz789.log",
        metrics=metrics,
        cached=True
    )
    
    assert result.logs_ref == "logs/sim_xyz789.log"
    assert result.metrics == metrics
    assert result.cached is True


def test_sim_return_validation():
    """Test SimReturn validation."""
    output = TableArtifact(
        size=100,
        inline=b"x" * 100,
        checksum="9" * 64
    )
    
    # Empty task_id
    with pytest.raises(ContractViolationError, match="task_id must be non-empty"):
        SimReturn(
            task_id="",
            outputs={"out": output}
        )
    
    # Empty outputs
    with pytest.raises(ContractViolationError, match="outputs must contain at least one artifact"):
        SimReturn(
            task_id="task_id",
            outputs={}
        )
    
    # Wrong type in outputs
    with pytest.raises(ContractViolationError, match="Output .* must be TableArtifact"):
        SimReturn(
            task_id="task_id",
            outputs={"bad": "not an artifact"}
        )


def test_sim_return_frozen():
    """Test that SimReturn is immutable."""
    output = TableArtifact(
        size=100,
        inline=b"x" * 100,
        checksum="d" * 64
    )
    
    result = SimReturn(
        task_id="immutable_task",
        outputs={"data": output}
    )
    
    with pytest.raises(AttributeError):
        result.task_id = "new_id"
    
    with pytest.raises(AttributeError):
        result.cached = True


def test_sim_return_multiple_outputs():
    """Test SimReturn with multiple outputs of different types."""
    # Small inline output
    small_data = b"small" * 200
    small_output = TableArtifact(
        size=len(small_data),
        inline=small_data,
        checksum="f" * 64
    )
    
    # Large reference output
    large_output = TableArtifact(
        size=10 * 1024 * 1024,  # 10MB
        ref="outputs/large/file.arrow",
        checksum="0" * 64
    )
    
    # Another inline output
    medium_data = b"medium" * 8333  # ~50KB
    medium_output = TableArtifact(
        size=len(medium_data),
        inline=medium_data,
        checksum="1" * 64
    )
    
    result = SimReturn(
        task_id="multi_output_task",
        outputs={
            "small_table": small_output,
            "large_table": large_output,
            "medium_table": medium_output
        }
    )
    
    assert len(result.outputs) == 3
    assert isinstance(result.outputs["small_table"], TableArtifact)
    assert isinstance(result.outputs["large_table"], TableArtifact)
    assert isinstance(result.outputs["medium_table"], TableArtifact)
    
    # Verify the right storage method was used
    assert result.outputs["small_table"].inline is not None
    assert result.outputs["large_table"].ref is not None
    assert result.outputs["medium_table"].inline is not None