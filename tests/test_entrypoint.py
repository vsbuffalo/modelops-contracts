"""Tests for entrypoint formatting and parsing."""

import pytest
from modelops_contracts import (
    EntryPointId,
    ENTRYPOINT_GRAMMAR_VERSION,
    EntrypointFormatError,
    format_entrypoint,
    parse_entrypoint,
)


def test_format_entrypoint_valid():
    """Test formatting a valid entrypoint."""
    eid = format_entrypoint(
        import_path="pkg.module.Class",
        scenario="baseline"
    )
    assert str(eid) == "pkg.module.Class/baseline"
    
    # Test with different scenario
    eid2 = format_entrypoint(
        import_path="my_app.models.EpiModel",
        scenario="lockdown"
    )
    assert str(eid2) == "my_app.models.EpiModel/lockdown"


def test_format_entrypoint_complex_scenario():
    """Test formatting with complex but valid scenario slugs."""
    # With dots and dashes
    eid = format_entrypoint(
        import_path="pkg.Model",
        scenario="high-growth.v2"
    )
    assert str(eid) == "pkg.Model/high-growth.v2"
    
    # With underscores
    eid2 = format_entrypoint(
        import_path="app.Sim",
        scenario="test_scenario_1"
    )
    assert str(eid2) == "app.Sim/test_scenario_1"


def test_format_entrypoint_invalid_import_path():
    """Test that invalid import paths are rejected."""
    # Missing class name
    with pytest.raises(EntrypointFormatError, match="Invalid import_path"):
        format_entrypoint("pkg", "baseline")
    
    # Starting with number
    with pytest.raises(EntrypointFormatError, match="Invalid import_path"):
        format_entrypoint("123.module.Class", "baseline")
    
    # Empty
    with pytest.raises(EntrypointFormatError, match="Invalid import_path"):
        format_entrypoint("", "baseline")


def test_format_entrypoint_invalid_scenario():
    """Test that invalid scenario slugs are rejected."""
    # Uppercase not allowed
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", "BASELINE")
    
    # Starting with dash
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", "-baseline")
    
    # Ending with dash
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", "baseline-")
    
    # Special characters
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", "base@line")
    
    # Too long (>64 chars)
    long_scenario = "a" * 65
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", long_scenario)


def test_parse_entrypoint_valid():
    """Test parsing valid entrypoints."""
    import_path, scenario = parse_entrypoint(
        EntryPointId("pkg.module.Class/baseline")
    )
    assert import_path == "pkg.module.Class"
    assert scenario == "baseline"


def test_parse_entrypoint_invalid_format():
    """Test parsing invalid entrypoint formats."""
    # Missing /
    with pytest.raises(EntrypointFormatError, match="Invalid entrypoint format"):
        parse_entrypoint(EntryPointId("pkg.Model"))
    
    # Invalid import path after parsing
    with pytest.raises(EntrypointFormatError, match="Invalid import_path"):
        parse_entrypoint(EntryPointId("pkg/baseline"))
    
    # Invalid scenario after parsing
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        parse_entrypoint(EntryPointId("pkg.Model/BASE-LINE"))


def test_round_trip():
    """Test that format -> parse round-trips correctly."""
    test_cases = [
        ("pkg.module.Class", "baseline"),
        ("my_app.models.Model", "test_1"),
        ("a.b.C", "x"),
        ("very.nested.pkg.structure.ClassName", "complex-scenario.v2"),
    ]
    
    for import_path, scenario in test_cases:
        eid = format_entrypoint(import_path, scenario)
        parsed_import, parsed_scenario = parse_entrypoint(eid)
        
        assert parsed_import == import_path
        assert parsed_scenario == scenario


def test_constants():
    """Test that module constants are defined correctly."""
    assert ENTRYPOINT_GRAMMAR_VERSION == 2  # Version 2: No digest


def test_entrypoint_id_type():
    """Test that EntryPointId behaves as expected."""
    eid = EntryPointId("pkg.Model/baseline")
    
    # Should be a string
    assert isinstance(eid, str)
    assert str(eid) == "pkg.Model/baseline"
    
    # Can be created from format_entrypoint
    eid2 = format_entrypoint("pkg.Model", "baseline")
    assert isinstance(eid2, str)
    assert str(eid2) == "pkg.Model/baseline"


def test_edge_cases():
    """Test edge cases and boundary conditions."""
    # Minimum valid scenario (1 char)
    eid = format_entrypoint("pkg.M", "x")
    assert str(eid) == "pkg.M/x"
    
    # Maximum valid scenario (64 chars, must start and end with alnum)
    max_scenario = "a" + "b" * 62 + "c"  # 64 chars total
    eid = format_entrypoint("pkg.M", max_scenario)
    assert max_scenario in str(eid)
    
    # Complex but valid import path
    eid = format_entrypoint(
        "_internal.package_123.MyClass_ABC",
        "test"
    )
    assert "_internal.package_123.MyClass_ABC" in str(eid)