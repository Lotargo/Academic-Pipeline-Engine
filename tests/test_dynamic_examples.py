import pytest
from academic_pe.core.config import AppConfig, AgentConfig
from academic_pe.core.dynamic_examples import clean_and_parse_json, get_default_examples, DEFAULT_EXAMPLES_RU, DEFAULT_EXAMPLES_EN


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
