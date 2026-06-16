import pytest
from academic_pe.core.config import AppConfig, AgentConfig
from academic_pe.core.dynamic_examples import (
    DEFAULT_EXAMPLES_EN,
    DEFAULT_EXAMPLES_RU,
    build_dynamic_examples_prompt,
    clean_and_parse_json,
    get_default_examples,
    _language_plan_for_primary,
    _next_language_plan,
    _compact_previous_examples,
)


def test_dynamic_examples_config_defaults():
    cfg = AppConfig(
        agents={
            "test": AgentConfig(
                role="Test", model="m", temperature=0.5,
                system_prompt="test",
            ),
        },
    )
    # Check that new settings are present and default to True/15
    assert cfg.dynamic_examples_enabled is True
    assert cfg.dynamic_examples_interval_mins == 15


def test_clean_and_parse_json_direct():
    text = '[{"topic": "T1", "instructions": "I1"}, {"topic": "T2", "instructions": "I2"}]'
    res = clean_and_parse_json(text)
    assert len(res) == 2
    assert res[0]["topic"] == "T1"
    assert res[1]["instructions"] == "I2"


def test_clean_and_parse_json_markdown():
    text = """
Here are your examples:
```json
[
  {
    "topic": "T1",
    "instructions": "I1"
  }
]
```
Hope you like them!
"""
    res = clean_and_parse_json(text)
    assert len(res) == 1
    assert res[0]["topic"] == "T1"
    assert res[0]["instructions"] == "I1"


def test_clean_and_parse_json_wrapped_no_lang():
    text = """
```
[
  {"topic": "T1", "instructions": "I1"}
]
```
"""
    res = clean_and_parse_json(text)
    assert len(res) == 1
    assert res[0]["topic"] == "T1"


def test_clean_and_parse_json_garbage_around():
    text = """
Sure, here is the list:
[
  {"topic": "T1", "instructions": "I1"}
]
Let me know if you need more!
"""
    res = clean_and_parse_json(text)
    assert len(res) == 1
    assert res[0]["topic"] == "T1"


def test_clean_and_parse_json_invalid():
    with pytest.raises(ValueError):
        clean_and_parse_json("not a json array")


def test_get_default_examples():
    assert get_default_examples("ru") == DEFAULT_EXAMPLES_RU
    assert get_default_examples("en") == DEFAULT_EXAMPLES_EN
    assert get_default_examples("unknown") == DEFAULT_EXAMPLES_EN


def test_default_examples_are_artifact_diverse():
    examples = get_default_examples("en")
    combined = " ".join(f"{item['topic']} {item['instructions']}" for item in examples)

    assert "README" in combined
    assert "Poem" in combined
    assert "Analytical Report" in combined
    assert "academic research topics" not in combined


def test_dynamic_examples_prompt_treats_examples_as_illustrative_not_exhaustive():
    prompt = build_dynamic_examples_prompt("en")

    assert "illustrative entry points only" in prompt
    assert "not an exhaustive list of supported artifact types" in prompt
    assert "unknown or niche requests" in prompt


def test_dynamic_examples_prompt_uses_bilingual_checkerboard_plan():
    prompt = build_dynamic_examples_prompt(
        "ru",
        previous_examples=[
            {"topic": "Old README", "instructions": "Old API instructions."},
        ],
        language_plan=["ru", "ru", "en"],
    )

    assert "Item 1: write topic and instructions in ru" in prompt
    assert "Item 2: write topic and instructions in ru" in prompt
    assert "Item 3: write topic and instructions in en" in prompt
    assert "Previous examples to avoid repeating" in prompt
    assert "Old README" in prompt
    assert "substantially different examples" in prompt
    assert "Do not add a language field" in prompt


def test_dynamic_examples_prompt_limits_previous_examples_to_last_triple():
    prompt = build_dynamic_examples_prompt(
        "en",
        previous_examples=[
            {"topic": "Old 1", "instructions": "I1"},
            {"topic": "Old 2", "instructions": "I2"},
            {"topic": "Old 3", "instructions": "I3"},
            {"topic": "Old 4", "instructions": "I4"},
        ],
        language_plan=["en", "en", "ru"],
    )

    assert "Old 1" in prompt
    assert "Old 2" in prompt
    assert "Old 3" in prompt
    assert "Old 4" not in prompt


def test_dynamic_examples_prompt_compacts_previous_examples():
    compact = _compact_previous_examples([
        {"topic": "T" * 300, "instructions": "I" * 1000},
        {"topic": "Short", "instructions": "Brief"},
        {"topic": "Third", "instructions": "Ok"},
        {"topic": "Fourth", "instructions": "Should not appear"},
    ])

    assert len(compact) == 3
    assert len(compact[0]["topic"]) <= 160
    assert len(compact[0]["instructions"]) <= 500
    assert compact[0]["topic"].endswith("...")
    assert compact[0]["instructions"].endswith("...")
    assert all(item["topic"] != "Fourth" for item in compact)


def test_language_plan_for_primary_alternates_two_to_one():
    assert _language_plan_for_primary("ru") == ["ru", "ru", "en"]
    assert _language_plan_for_primary("en") == ["en", "en", "ru"]
    assert _language_plan_for_primary("unknown") == ["en", "en", "ru"]


def test_next_language_plan_uses_metadata_to_alternate(tmp_path, monkeypatch):
    meta_path = tmp_path / "dynamic_examples_meta.json"
    monkeypatch.setattr(
        "academic_pe.core.dynamic_examples._DYNAMIC_EXAMPLES_META_PATH",
        str(meta_path),
    )

    assert _next_language_plan("ru") == ["ru", "ru", "en"]

    meta_path.write_text('{"last_primary_language": "ru"}', encoding="utf-8")
    assert _next_language_plan("ru") == ["en", "en", "ru"]

    meta_path.write_text('{"last_primary_language": "en"}', encoding="utf-8")
    assert _next_language_plan("ru") == ["ru", "ru", "en"]
