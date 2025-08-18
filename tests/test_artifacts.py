"""
Tests for artifacts module - BundleRef, ResolvedBundle, and media type constants.

Goal: guarantee the datamodels are valid, frozen, and serialize deterministically.
"""
import json
import pytest
from pydantic import ValidationError

from modelops_contracts.artifacts import (
    BundleRef,
    ResolvedBundle,
    BUNDLE_MANIFEST,
    LAYER_INDEX,
    EXTERNAL_REF,
    OCI_MANIFEST,
    OCI_EMPTY_CFG,
)


# =============================================================================
# 1. Construction & Validation
# =============================================================================

def test_bundle_ref_exactly_one():
    """Test that BundleRef requires exactly one identification method."""
    # Valid: name + version
    ref1 = BundleRef(name="epi-sir", version="1.0.0")
    assert ref1.name == "epi-sir"
    assert ref1.version == "1.0.0"
    
    # Valid: digest only
    digest = "sha256:" + "a" * 64
    ref2 = BundleRef(digest=digest)
    assert ref2.digest == digest
    
    # Valid: local_path only
    ref3 = BundleRef(local_path="/tmp/bundle")
    assert ref3.local_path == "/tmp/bundle"
    
    # Invalid: none provided
    with pytest.raises(ValidationError, match="Must provide exactly one"):
        BundleRef()
    
    # Invalid: two methods
    with pytest.raises(ValidationError, match="Must provide exactly one"):
        BundleRef(name="x", version="1.0", digest=digest)
    
    # Invalid: three methods
    with pytest.raises(ValidationError, match="Must provide exactly one"):
        BundleRef(name="x", version="1.0", digest=digest, local_path="/tmp")
    
    # Invalid: name without version
    with pytest.raises(ValidationError, match="Must provide exactly one"):
        BundleRef(name="x")
    
    # Invalid: version without name
    with pytest.raises(ValidationError, match="Must provide exactly one"):
        BundleRef(version="1.0")


def test_bundle_ref_name_normalization():
    """Test that bundle names are auto-normalized to lowercase."""
    # Auto-normalization to lowercase
    ref1 = BundleRef(name="EPI-SIR", version="1.0")
    assert ref1.name == "epi-sir"
    
    ref2 = BundleRef(name="Test-Bundle", version="latest")
    assert ref2.name == "test-bundle"
    
    ref3 = BundleRef(name="UPPERCASE", version="v1")
    assert ref3.name == "uppercase"
    
    # Already lowercase stays the same
    ref4 = BundleRef(name="already-lowercase", version="1.0")
    assert ref4.name == "already-lowercase"


def test_bundle_ref_name_validation():
    """Test that invalid bundle names are rejected."""
    # Invalid: underscore
    with pytest.raises(ValidationError, match="lowercase letters, digits, hyphens"):
        BundleRef(name="test_bundle", version="1.0")
    
    # Invalid: spaces
    with pytest.raises(ValidationError, match="lowercase letters, digits, hyphens"):
        BundleRef(name="test bundle", version="1.0")
    
    # Invalid: special characters
    with pytest.raises(ValidationError, match="lowercase letters, digits, hyphens"):
        BundleRef(name="test@bundle", version="1.0")
    
    # Valid: slashes and hyphens
    ref = BundleRef(name="org/sub-project", version="1.0")
    assert ref.name == "org/sub-project"


def test_bundle_ref_digest_validation():
    """Test digest format validation."""
    # Valid digest
    valid_digest = "sha256:" + "0123456789abcdef" * 4
    ref = BundleRef(digest=valid_digest)
    assert ref.digest == valid_digest
    
    # Invalid: wrong prefix
    with pytest.raises(ValidationError, match="String should match pattern"):
        BundleRef(digest="sha512:" + "a" * 64)
    
    # Invalid: wrong length
    with pytest.raises(ValidationError, match="String should match pattern"):
        BundleRef(digest="sha256:" + "a" * 63)
    
    # Invalid: non-hex characters
    with pytest.raises(ValidationError, match="String should match pattern"):
        BundleRef(digest="sha256:" + "g" * 64)


def test_resolved_bundle_required_fields():
    """Test ResolvedBundle required fields and validation."""
    ref = BundleRef(name="test", version="1.0")
    digest = "sha256:" + "b" * 64
    
    # Valid construction
    rb = ResolvedBundle(
        ref=ref,
        manifest_digest=digest,
        roles={"sim": ["code"]},
        layers=["code"],
        external_index_present=False,
        total_size=1024
    )
    assert rb.ref == ref
    assert rb.manifest_digest == digest
    assert rb.media_type == BUNDLE_MANIFEST  # default value
    
    # Invalid: negative size
    with pytest.raises(ValidationError, match="greater than or equal"):
        ResolvedBundle(
            ref=ref,
            manifest_digest=digest,
            roles={"sim": ["code"]},
            layers=["code"],
            external_index_present=False,
            total_size=-1
        )


def test_resolved_bundle_role_validation():
    """Test role and layer name validation."""
    ref = BundleRef(name="test", version="1.0")
    digest = "sha256:" + "c" * 64
    
    # Valid roles and layers
    rb = ResolvedBundle(
        ref=ref,
        manifest_digest=digest,
        roles={"sim": ["code", "config"], "fit": ["code", "config", "fitdata"]},
        layers=["code", "config", "fitdata"],
        external_index_present=False,
        total_size=2048
    )
    assert "sim" in rb.roles
    assert "fit" in rb.roles
    
    # Invalid: empty role name
    with pytest.raises(ValidationError, match="Invalid role name"):
        ResolvedBundle(
            ref=ref,
            manifest_digest=digest,
            roles={"": ["code"]},
            layers=["code"],
            external_index_present=False,
            total_size=1024
        )
    
    # Invalid: role with invalid characters
    with pytest.raises(ValidationError, match="Invalid role name"):
        ResolvedBundle(
            ref=ref,
            manifest_digest=digest,
            roles={"sim_role": ["code"]},
            layers=["code"],
            external_index_present=False,
            total_size=1024
        )
    
    # Invalid: empty layer list
    with pytest.raises(ValidationError, match="must reference at least one layer"):
        ResolvedBundle(
            ref=ref,
            manifest_digest=digest,
            roles={"sim": []},
            layers=["code"],
            external_index_present=False,
            total_size=1024
        )
    
    # Invalid: layer with invalid characters
    with pytest.raises(ValidationError, match="Invalid layer name"):
        ResolvedBundle(
            ref=ref,
            manifest_digest=digest,
            roles={"sim": ["code", "bad_layer"]},
            layers=["code", "bad_layer"],
            external_index_present=False,
            total_size=1024
        )


# =============================================================================
# 2. Frozenness / Immutability
# =============================================================================

def test_bundle_ref_frozen():
    """Test that BundleRef is immutable."""
    ref = BundleRef(name="test", version="1.0")
    
    # Cannot modify fields
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        ref.name = "modified"
    
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        ref.version = "2.0"
    
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        ref.role = "new-role"


def test_resolved_bundle_frozen():
    """Test that ResolvedBundle is immutable."""
    ref = BundleRef(name="test", version="1.0")
    rb = ResolvedBundle(
        ref=ref,
        manifest_digest="sha256:" + "d" * 64,
        roles={"sim": ["code"]},
        layers=["code"],
        external_index_present=False,
        total_size=512
    )
    
    # Cannot modify fields
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        rb.total_size = 999
    
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        rb.external_index_present = True
    
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        rb.manifest_digest = "sha256:" + "e" * 64


# =============================================================================
# 3. Helpers
# =============================================================================

def test_get_role_layers():
    """Test the get_role_layers helper method."""
    ref = BundleRef(name="test", version="1.0")
    rb = ResolvedBundle(
        ref=ref,
        manifest_digest="sha256:" + "f" * 64,
        roles={
            "sim": ["code", "config"],
            "fit": ["code", "config", "fitdata"],
            "viz": ["output"]
        },
        layers=["code", "config", "fitdata", "output"],
        external_index_present=False,
        total_size=4096
    )
    
    # Valid role lookups
    assert rb.get_role_layers("sim") == ["code", "config"]
    assert rb.get_role_layers("fit") == ["code", "config", "fitdata"]
    assert rb.get_role_layers("viz") == ["output"]
    
    # Invalid role lookup
    with pytest.raises(KeyError) as exc_info:
        rb.get_role_layers("invalid")
    
    # Check the error message contains available roles
    error_msg = str(exc_info.value)
    assert "invalid" in error_msg
    assert "Available roles" in error_msg


def test_bundle_ref_string_repr():
    """Test BundleRef string representation."""
    # Name + version
    ref1 = BundleRef(name="epi-sir", version="1.2.3")
    assert str(ref1) == "BundleRef(epi-sir:1.2.3)"
    
    # Digest (truncated)
    digest = "sha256:" + "a" * 64
    ref2 = BundleRef(digest=digest)
    assert str(ref2).startswith("BundleRef(digest=sha256:")
    assert "..." in str(ref2)
    
    # Local path
    ref3 = BundleRef(local_path="/tmp/bundle")
    assert str(ref3) == "BundleRef(local_path=/tmp/bundle)"


# =============================================================================
# 4. Serialization Stability
# =============================================================================

def test_bundle_ref_roundtrip():
    """Test BundleRef JSON serialization round-trip."""
    ref = BundleRef(name="test-bundle", version="1.0.0", role="sim")
    
    # Serialize to JSON
    json_str = ref.model_dump_json()
    
    # Deserialize back
    ref2 = BundleRef.model_validate_json(json_str)
    
    # Should be equal
    assert ref2 == ref
    assert ref2.name == "test-bundle"
    assert ref2.version == "1.0.0"
    assert ref2.role == "sim"


def test_resolved_bundle_roundtrip():
    """Test ResolvedBundle JSON serialization round-trip."""
    ref = BundleRef(name="epi-sir", version="1.0.0")
    rb = ResolvedBundle(
        ref=ref,
        manifest_digest="sha256:" + "b" * 64,
        roles={"sim": ["code", "config"]},
        layers=["code", "config"],
        external_index_present=True,
        total_size=1234,
        cache_dir="/tmp/cache"
    )
    
    # Serialize to JSON
    json_str = rb.model_dump_json()
    
    # Deserialize back
    rb2 = ResolvedBundle.model_validate_json(json_str)
    
    # Should be equal
    assert rb2 == rb
    assert rb2.manifest_digest == rb.manifest_digest
    assert rb2.media_type == BUNDLE_MANIFEST
    assert rb2.roles == rb.roles
    assert rb2.total_size == 1234


def test_resolved_bundle_json_structure():
    """Test that ResolvedBundle produces expected JSON structure."""
    ref = BundleRef(name="test", version="1.0")
    rb = ResolvedBundle(
        ref=ref,
        manifest_digest="sha256:" + "0" * 64,
        roles={"sim": ["code"]},
        layers=["code"],
        external_index_present=False,
        total_size=100
    )
    
    # Get JSON as dict for inspection
    data = rb.model_dump()
    
    # Check expected keys are present (explicit field verification)
    expected_keys = {
        "ref", "manifest_digest", "media_type", "roles", "layers",
        "external_index_present", "total_size", "cache_dir"
    }
    assert set(data.keys()) == expected_keys
    
    # Check nested ref structure
    assert "name" in data["ref"]
    assert "version" in data["ref"]
    assert data["ref"]["name"] == "test"
    assert data["ref"]["version"] == "1.0"
    
    # Check default values
    assert data["media_type"] == BUNDLE_MANIFEST
    assert data["cache_dir"] is None  # Optional field


# =============================================================================
# 5. Constants Exposure & Package Root
# =============================================================================

def test_media_type_constants():
    """Test that media type constants are properly exposed and have correct values."""
    # Check the constants exist and have expected format
    assert BUNDLE_MANIFEST == "application/vnd.modelops.bundle.manifest+json"
    assert LAYER_INDEX == "application/vnd.modelops.layer+json"
    assert EXTERNAL_REF == "application/vnd.modelops.external-ref+json"
    assert OCI_MANIFEST == "application/vnd.oci.image.manifest.v1+json"
    assert OCI_EMPTY_CFG == "application/vnd.oci.empty.v1+json"
    
    # Verify they're strings
    assert isinstance(BUNDLE_MANIFEST, str)
    assert isinstance(LAYER_INDEX, str)
    assert isinstance(EXTERNAL_REF, str)
    assert isinstance(OCI_MANIFEST, str)
    assert isinstance(OCI_EMPTY_CFG, str)


def test_package_root_exports():
    """Test that all artifacts are properly exported from package root."""
    # Import from package root
    from modelops_contracts import (
        BundleRef as RootBundleRef,
        ResolvedBundle as RootResolvedBundle,
        BUNDLE_MANIFEST as root_manifest,
        LAYER_INDEX as root_layer,
        EXTERNAL_REF as root_external,
        OCI_MANIFEST as root_oci,
        OCI_EMPTY_CFG as root_empty,
    )
    
    # Constants should be identical
    assert root_manifest == BUNDLE_MANIFEST
    assert root_layer == LAYER_INDEX
    assert root_external == EXTERNAL_REF
    assert root_oci == OCI_MANIFEST
    assert root_empty == OCI_EMPTY_CFG
    
    # Classes should be the same type
    ref = BundleRef(name="test", version="1.0")
    root_ref = RootBundleRef(name="test", version="1.0")
    assert type(ref) == type(root_ref)
    assert ref == root_ref
    
    # ResolvedBundle should work the same way
    digest = "sha256:" + "a" * 64
    rb = ResolvedBundle(
        ref=ref,
        manifest_digest=digest,
        roles={"sim": ["code"]},
        layers=["code"],
        external_index_present=False,
        total_size=100
    )
    root_rb = RootResolvedBundle(
        ref=root_ref,
        manifest_digest=digest,
        roles={"sim": ["code"]},
        layers=["code"],
        external_index_present=False,
        total_size=100
    )
    assert type(rb) == type(root_rb)
    assert rb == root_rb