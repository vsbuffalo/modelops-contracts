"""Tests for manifest types."""

import pytest
from modelops_contracts import ModelEntry, BundleManifest


class TestModelEntry:
    """Tests for ModelEntry validation and functionality."""

    def test_model_entry_validates_digest_format(self):
        """Model digest must be 64-character hex string."""
        # Valid digest
        valid_entry = ModelEntry(
            entrypoint_base="models.seir.StochasticSEIR",
            scenarios=["baseline"],
            outputs=["infections"],
            parameters=["beta", "gamma"],
            model_digest="a" * 64
        )
        assert valid_entry.model_digest == "a" * 64

        # Invalid: too short
        with pytest.raises(ValueError, match="64-character hex"):
            ModelEntry(
                entrypoint_base="models.seir.StochasticSEIR",
                scenarios=["baseline"],
                outputs=["infections"],
                parameters=["beta"],
                model_digest="abc123"
            )

        # Invalid: non-hex characters
        with pytest.raises(ValueError, match="64-character hex"):
            ModelEntry(
                entrypoint_base="models.seir.StochasticSEIR",
                scenarios=["baseline"],
                outputs=["infections"],
                parameters=["beta"],
                model_digest="z" * 64
            )

    def test_model_entry_requires_scenarios(self):
        """ModelEntry must have at least one scenario."""
        # Valid: has scenarios
        valid_entry = ModelEntry(
            entrypoint_base="models.test.Model",
            scenarios=["baseline", "intervention"],
            outputs=["results"],
            parameters=["x"],
            model_digest="0" * 64
        )
        assert len(valid_entry.scenarios) == 2

        # Invalid: empty scenarios
        with pytest.raises(ValueError, match="at least one scenario"):
            ModelEntry(
                entrypoint_base="models.test.Model",
                scenarios=[],
                outputs=["results"],
                parameters=["x"],
                model_digest="0" * 64
            )

    def test_model_entry_requires_parameters(self):
        """ModelEntry must have at least one parameter."""
        # Valid: has parameters
        valid_entry = ModelEntry(
            entrypoint_base="models.test.Model",
            scenarios=["baseline"],
            outputs=["results"],
            parameters=["x", "y", "z"],
            model_digest="0" * 64
        )
        assert len(valid_entry.parameters) == 3

        # Invalid: empty parameters
        with pytest.raises(ValueError, match="at least one parameter"):
            ModelEntry(
                entrypoint_base="models.test.Model",
                scenarios=["baseline"],
                outputs=["results"],
                parameters=[],
                model_digest="0" * 64
            )

    def test_model_entry_get_entrypoints(self):
        """Test entrypoint formatting with scenarios."""
        entry = ModelEntry(
            entrypoint_base="models.seir.StochasticSEIR",
            scenarios=["baseline", "lockdown", "vaccination"],
            outputs=["infections"],
            parameters=["beta"],
            model_digest="0" * 64
        )

        entrypoints = entry.get_entrypoints()
        assert len(entrypoints) == 3
        assert "models.seir.StochasticSEIR/baseline" in entrypoints
        assert "models.seir.StochasticSEIR/lockdown" in entrypoints
        assert "models.seir.StochasticSEIR/vaccination" in entrypoints


class TestBundleManifest:
    """Tests for BundleManifest validation and functionality."""

    def test_bundle_manifest_validation(self):
        """BundleManifest validates required fields."""
        model = ModelEntry(
            entrypoint_base="models.test.Model",
            scenarios=["baseline"],
            outputs=["results"],
            parameters=["x"],
            model_digest="1" * 64
        )

        # Valid manifest
        manifest = BundleManifest(
            bundle_ref="oci://registry/bundle:latest",
            bundle_digest="2" * 64,
            models={"models.test.Model": model},
            version=1
        )
        assert manifest.bundle_digest == "2" * 64

        # Invalid: bad bundle digest
        with pytest.raises(ValueError, match="64-character hex"):
            BundleManifest(
                bundle_ref="oci://registry/bundle:latest",
                bundle_digest="not-a-hash",
                models={"models.test.Model": model}
            )

        # Invalid: empty models
        with pytest.raises(ValueError, match="at least one model"):
            BundleManifest(
                bundle_ref="oci://registry/bundle:latest",
                bundle_digest="2" * 64,
                models={}
            )

        # Invalid: empty bundle_ref
        with pytest.raises(ValueError, match="bundle_ref must be non-empty"):
            BundleManifest(
                bundle_ref="",
                bundle_digest="2" * 64,
                models={"models.test.Model": model}
            )

    def test_get_model_by_entrypoint(self):
        """Test model lookup by entrypoint base."""
        model1 = ModelEntry(
            entrypoint_base="models.seir.SEIR",
            scenarios=["baseline"],
            outputs=["infections"],
            parameters=["beta"],
            model_digest="1" * 64
        )
        model2 = ModelEntry(
            entrypoint_base="models.sir.SIR",
            scenarios=["baseline"],
            outputs=["infections"],
            parameters=["beta"],
            model_digest="2" * 64
        )

        manifest = BundleManifest(
            bundle_ref="local://dev",
            bundle_digest="3" * 64,
            models={
                "models.seir.SEIR": model1,
                "models.sir.SIR": model2
            }
        )

        # Found
        found = manifest.get_model_by_entrypoint("models.seir.SEIR")
        assert found == model1

        # Not found
        not_found = manifest.get_model_by_entrypoint("models.unknown.Model")
        assert not_found is None

    def test_list_all_entrypoints(self):
        """Test listing all available entrypoints."""
        model1 = ModelEntry(
            entrypoint_base="models.a.ModelA",
            scenarios=["s1", "s2"],
            outputs=["out"],
            parameters=["p"],
            model_digest="1" * 64
        )
        model2 = ModelEntry(
            entrypoint_base="models.b.ModelB",
            scenarios=["baseline"],
            outputs=["out"],
            parameters=["p"],
            model_digest="2" * 64
        )

        manifest = BundleManifest(
            bundle_ref="local://dev",
            bundle_digest="3" * 64,
            models={
                "a": model1,
                "b": model2
            }
        )

        entrypoints = manifest.list_all_entrypoints()
        assert len(entrypoints) == 3
        assert "models.a.ModelA/s1" in entrypoints
        assert "models.a.ModelA/s2" in entrypoints
        assert "models.b.ModelB/baseline" in entrypoints
        # Should be sorted
        assert entrypoints == sorted(entrypoints)