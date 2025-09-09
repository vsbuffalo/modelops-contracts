"""Tests for entrypoint formatting and parsing."""

import pytest
from modelops_contracts import (
    EntryPointId,
    DIGEST_PREFIX_LEN,
    ENTRYPOINT_GRAMMAR_VERSION,
    EntrypointFormatError,
    format_entrypoint,
    parse_entrypoint,
    validate_entrypoint_matches_bundle,
    is_entrypoint_for_bundle,
)


def test_format_entrypoint_valid():
    """Test formatting a valid entrypoint."""
    eid = format_entrypoint(
        import_path="pkg.module.Class",
        scenario="baseline",
        oci_digest="sha256:abcdef1234567890fedcba0987654321"
    )
    assert str(eid) == "pkg.module.Class/baseline@abcdef123456"
    
    # Test with different scenario
    eid2 = format_entrypoint(
        import_path="my_app.models.EpiModel",
        scenario="lockdown",
        oci_digest="sha256:1234567890abcdef1234567890abcdef"
    )
    assert str(eid2) == "my_app.models.EpiModel/lockdown@1234567890ab"


def test_format_entrypoint_complex_scenario():
    """Test formatting with complex but valid scenario slugs."""
    # With dots and dashes
    eid = format_entrypoint(
        import_path="pkg.Model",
        scenario="high-growth.v2",
        oci_digest="sha256:deadbeef12345678901234567890abcd"
    )
    assert str(eid) == "pkg.Model/high-growth.v2@deadbeef1234"
    
    # With underscores
    eid2 = format_entrypoint(
        import_path="app.Sim",
        scenario="test_scenario_1",
        oci_digest="sha256:cafebabe12345678901234567890abcd"
    )
    assert str(eid2) == "app.Sim/test_scenario_1@cafebabe1234"


def test_format_entrypoint_invalid_import_path():
    """Test that invalid import paths are rejected."""
    # Missing class name
    with pytest.raises(EntrypointFormatError, match="Invalid import_path"):
        format_entrypoint("pkg", "baseline", "sha256:abcd1234567890")
    
    # Starting with number
    with pytest.raises(EntrypointFormatError, match="Invalid import_path"):
        format_entrypoint("123.module.Class", "baseline", "sha256:abcd1234567890")
    
    # Empty
    with pytest.raises(EntrypointFormatError, match="Invalid import_path"):
        format_entrypoint("", "baseline", "sha256:abcd1234567890")


def test_format_entrypoint_invalid_scenario():
    """Test that invalid scenario slugs are rejected."""
    # Uppercase not allowed
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", "BASELINE", "sha256:abcd1234567890")
    
    # Starting with dash
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", "-baseline", "sha256:abcd1234567890")
    
    # Ending with dash
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", "baseline-", "sha256:abcd1234567890")
    
    # Special characters
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", "base@line", "sha256:abcd1234567890")
    
    # Too long (>64 chars)
    long_scenario = "a" * 65
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        format_entrypoint("pkg.Model", long_scenario, "sha256:abcd1234567890")


def test_format_entrypoint_invalid_digest():
    """Test that invalid OCI digests are rejected."""
    # Missing algo prefix
    with pytest.raises(EntrypointFormatError, match="oci_digest must be algo:hex"):
        format_entrypoint("pkg.Model", "baseline", "abcd1234567890")
    
    # Unsupported algorithm
    with pytest.raises(EntrypointFormatError, match="Unsupported digest algorithm"):
        format_entrypoint("pkg.Model", "baseline", "sha512:abcd1234567890")
    
    # Too short digest
    with pytest.raises(EntrypointFormatError, match="Digest too short"):
        format_entrypoint("pkg.Model", "baseline", "sha256:abcd123")


def test_parse_entrypoint_valid():
    """Test parsing valid entrypoints."""
    import_path, scenario, digest12 = parse_entrypoint(
        EntryPointId("pkg.module.Class/baseline@abcdef123456")
    )
    assert import_path == "pkg.module.Class"
    assert scenario == "baseline"
    assert digest12 == "abcdef123456"
    assert len(digest12) == DIGEST_PREFIX_LEN


def test_parse_entrypoint_invalid_format():
    """Test parsing invalid entrypoint formats."""
    # Missing @
    with pytest.raises(EntrypointFormatError, match="Invalid entrypoint format"):
        parse_entrypoint(EntryPointId("pkg.Model/baseline"))
    
    # Missing /
    with pytest.raises(EntrypointFormatError, match="Invalid entrypoint format"):
        parse_entrypoint(EntryPointId("pkg.Model@abcdef123456"))
    
    # Multiple @ (gives wrong digest length error)
    with pytest.raises(EntrypointFormatError, match="Digest prefix must be"):
        parse_entrypoint(EntryPointId("pkg.Model/baseline@abc@def"))
    
    # Wrong digest length
    with pytest.raises(EntrypointFormatError, match="Digest prefix must be"):
        parse_entrypoint(EntryPointId("pkg.Model/baseline@abc"))
    
    # Invalid import path after parsing
    with pytest.raises(EntrypointFormatError, match="Invalid import_path"):
        parse_entrypoint(EntryPointId("pkg/baseline@abcdef123456"))
    
    # Invalid scenario after parsing
    with pytest.raises(EntrypointFormatError, match="Invalid scenario slug"):
        parse_entrypoint(EntryPointId("pkg.Model/BASE-LINE@abcdef123456"))


def test_round_trip():
    """Test that format -> parse round-trips correctly."""
    test_cases = [
        ("pkg.module.Class", "baseline", "sha256:abcdef1234567890fedcba0987654321"),
        ("my_app.models.Model", "test_1", "sha256:deadbeef12345678901234567890abcd"),
        ("a.b.C", "x", "sha256:1111111111112222222222223333333333"),
        ("very.nested.pkg.structure.ClassName", "complex-scenario.v2", 
         "sha256:fedcba0987654321abcdef1234567890"),
    ]
    
    for import_path, scenario, oci_digest in test_cases:
        eid = format_entrypoint(import_path, scenario, oci_digest)
        parsed_import, parsed_scenario, parsed_digest = parse_entrypoint(eid)
        
        assert parsed_import == import_path
        assert parsed_scenario == scenario
        assert oci_digest.startswith(f"sha256:{parsed_digest}")


def test_validate_entrypoint_matches_bundle():
    """Test validation of entrypoint against bundle reference."""
    eid = EntryPointId("pkg.Model/baseline@abcdef123456")
    bundle_ref = "sha256:abcdef1234567890fedcba0987654321"
    
    # Should not raise
    validate_entrypoint_matches_bundle(eid, bundle_ref)
    
    # Mismatched digest
    with pytest.raises(EntrypointFormatError, match="doesn't match bundle_ref prefix"):
        validate_entrypoint_matches_bundle(eid, "sha256:fedcba0987654321")
    
    # Invalid bundle_ref format
    with pytest.raises(EntrypointFormatError, match="Invalid bundle_ref format"):
        validate_entrypoint_matches_bundle(eid, "not-a-valid-ref")
    
    # Unsupported algorithm in bundle
    with pytest.raises(EntrypointFormatError, match="Unsupported digest algorithm"):
        validate_entrypoint_matches_bundle(eid, "sha512:abcdef1234567890")


def test_is_entrypoint_for_bundle():
    """Test non-throwing validation helper."""
    eid = EntryPointId("pkg.Model/baseline@abcdef123456")
    
    # Matching bundle
    assert is_entrypoint_for_bundle(eid, "sha256:abcdef1234567890fedcba") is True
    
    # Non-matching bundle
    assert is_entrypoint_for_bundle(eid, "sha256:fedcba0987654321") is False
    
    # Invalid formats - should return False, not throw
    assert is_entrypoint_for_bundle(eid, "invalid") is False
    assert is_entrypoint_for_bundle(EntryPointId("invalid"), "sha256:abcd") is False


def test_constants():
    """Test that module constants are defined correctly."""
    assert DIGEST_PREFIX_LEN == 12
    assert ENTRYPOINT_GRAMMAR_VERSION == 1


def test_entrypoint_id_type():
    """Test that EntryPointId behaves as expected."""
    eid = EntryPointId("pkg.Model/baseline@abcdef123456")
    
    # Should be a string
    assert isinstance(eid, str)
    assert str(eid) == "pkg.Model/baseline@abcdef123456"
    
    # Can be created from format_entrypoint
    eid2 = format_entrypoint("pkg.Model", "baseline", "sha256:abcdef1234567890")
    assert isinstance(eid2, str)
    assert str(eid2) == "pkg.Model/baseline@abcdef123456"


def test_edge_cases():
    """Test edge cases and boundary conditions."""
    # Minimum valid scenario (1 char)
    eid = format_entrypoint("pkg.M", "x", "sha256:abcdef1234567890")
    assert str(eid) == "pkg.M/x@abcdef123456"
    
    # Maximum valid scenario (64 chars, must start and end with alnum)
    max_scenario = "a" + "b" * 62 + "c"  # 64 chars total
    eid = format_entrypoint("pkg.M", max_scenario, "sha256:abcdef1234567890")
    assert max_scenario in str(eid)
    
    # Exactly 12 char digest prefix
    eid = format_entrypoint("pkg.M", "test", "sha256:123456789012xxxxxxxxxxxxx")
    assert str(eid) == "pkg.M/test@123456789012"
    
    # Complex but valid import path
    eid = format_entrypoint(
        "_internal.package_123.MyClass_ABC",
        "test",
        "sha256:abcdef1234567890"
    )
    assert "_internal.package_123.MyClass_ABC" in str(eid)