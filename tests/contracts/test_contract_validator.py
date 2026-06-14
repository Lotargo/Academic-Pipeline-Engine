import pytest

from academic_pe.contracts import (
    ArtifactContract,
    ContractValidationError,
    compile_artifact_contract,
    contract_validation_issues,
    validate_contract,
)
from academic_pe.manifests.models import ArtifactManifest


def test_validate_contract_accepts_safe_data_contract():
    contract = ArtifactContract(
        manifest_id="creative_poem",
        artifact="creative_poem",
        style=["human", "natural"],
        structure=["lines", "stanzas"],
        forbid=["academic_drift", "title_page"],
        requirements={
            "min_lines": 12,
            "motifs": ["red", "rain"],
            "nested": {"evidence_discipline": True},
        },
        content_boundaries={
            "adult_content": {
                "explicitness": "user_requested",
                "require_all_characters_adult": True,
                "require_consent": True,
                "forbid": ["minors", "coercion", "non_consensual"],
            }
        },
    )

    assert validate_contract(contract) is contract
    assert contract_validation_issues(contract) == []


def test_validate_contract_rejects_reserved_constraint_names():
    contract = ArtifactContract(
        manifest_id="creative_poem",
        artifact="creative_poem",
        forbid=["eval"],
    )

    with pytest.raises(ContractValidationError, match="reserved contract name 'eval'"):
        validate_contract(contract)


def test_validate_contract_rejects_non_atom_constraint_names():
    contract = ArtifactContract(
        manifest_id="creative_poem",
        artifact="creative_poem",
        forbid=["title page"],
    )

    with pytest.raises(ContractValidationError, match="safe atom name"):
        validate_contract(contract)


def test_validate_contract_rejects_unsafe_requirement_keys():
    contract = ArtifactContract(
        manifest_id="creative_poem",
        artifact="creative_poem",
        requirements={"os.system": "nope"},
    )

    with pytest.raises(ContractValidationError, match="reserved contract name 'os.system'"):
        validate_contract(contract)


def test_validate_contract_rejects_non_json_like_requirement_values():
    contract = ArtifactContract(
        manifest_id="creative_poem",
        artifact="creative_poem",
        requirements={"callback": object()},
    )

    with pytest.raises(ContractValidationError, match="unsupported value type object"):
        validate_contract(contract)


def test_compile_artifact_contract_validates_manifest_constraints():
    manifest = ArtifactManifest(
        id="bad_manifest",
        artifact_type="creative_poem",
        forbid=["exec"],
    )

    with pytest.raises(ContractValidationError, match="reserved contract name 'exec'"):
        compile_artifact_contract(manifest)


def test_validate_contract_rejects_unsafe_content_boundary_names():
    contract = ArtifactContract(
        manifest_id="creative_story",
        artifact="creative_story",
        content_boundaries={
            "adult content": {
                "forbid": ["minors"],
            }
        },
    )

    with pytest.raises(ContractValidationError, match="safe atom name"):
        validate_contract(contract)


def test_validate_contract_rejects_unsafe_content_boundary_forbid_values():
    contract = ArtifactContract(
        manifest_id="creative_story",
        artifact="creative_story",
        content_boundaries={
            "adult_content": {
                "forbid": ["os.system"],
            }
        },
    )

    with pytest.raises(ContractValidationError, match="reserved contract name 'os.system'"):
        validate_contract(contract)


def test_compile_artifact_contract_carries_content_boundaries():
    manifest = ArtifactManifest(
        id="creative_story",
        artifact_type="creative_story",
        content_boundaries={
            "adult_content": {
                "explicitness": "user_requested",
                "require_all_characters_adult": True,
                "require_consent": True,
                "forbid": ["minors", "coercion"],
            }
        },
    )

    contract = compile_artifact_contract(manifest)

    assert contract.content_boundaries["adult_content"]["require_consent"] is True
    assert contract.content_boundaries["adult_content"]["forbid"] == ["minors", "coercion"]
