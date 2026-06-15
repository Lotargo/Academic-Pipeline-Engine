import pytest

from academic_pe.core.section_patch import (
    SectionPatchError,
    add_line_numbers,
    apply_line_replace_patch,
    is_valid_line_replace_patch_response,
    parse_line_replace_blocks,
)


def test_add_line_numbers():
    assert add_line_numbers("") == ""
    assert add_line_numbers("Hello\nWorld") == "1: Hello\n2: World"
    assert add_line_numbers("Line 1\nLine 2\n") == "1: Line 1\n2: Line 2\n3: "


def test_no_changes_patch_returns_original():
    original = "Paragraph one.\n\nParagraph two."
    assert apply_line_replace_patch(original, "NO_CHANGES") == original


def test_line_replace_patch_updates_exact_range():
    original = "The complexity is O(n^2).\n\nThis remains unchanged."
    patch = """<<<<<<< REPLACE 1-1
The complexity is O(n log n).
>>>>>>>"""
    assert apply_line_replace_patch(original, patch) == "The complexity is O(n log n).\n\nThis remains unchanged."


def test_multiple_line_replace_blocks_apply_in_descending_order():
    original = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    patch = """<<<<<<< REPLACE 2-2
New Line 2
>>>>>>>
<<<<<<< REPLACE 4-4
New Line 4.1
New Line 4.2
>>>>>>>"""
    expected = "Line 1\nNew Line 2\nLine 3\nNew Line 4.1\nNew Line 4.2\nLine 5"
    assert apply_line_replace_patch(original, patch) == expected


def test_patch_fails_when_line_number_out_of_bounds():
    with pytest.raises(SectionPatchError, match="out of bounds"):
        apply_line_replace_patch("Existing line.", """<<<<<<< REPLACE 2-2
New line.
>>>>>>>""")


def test_patch_fails_when_invalid_range():
    with pytest.raises(SectionPatchError, match="must be <= end"):
        apply_line_replace_patch("Line 1\nLine 2", """<<<<<<< REPLACE 2-1
New line.
>>>>>>>""")


def test_patch_fails_when_overlapping_ranges():
    with pytest.raises(SectionPatchError, match="overlaps"):
        apply_line_replace_patch(
            "Line 1\nLine 2\nLine 3\nLine 4",
            """<<<<<<< REPLACE 2-3
New 2-3
>>>>>>>
<<<<<<< REPLACE 3-4
New 3-4
>>>>>>>""",
        )


def test_patch_fails_when_response_has_extra_text():
    with pytest.raises(SectionPatchError, match="outside"):
        parse_line_replace_blocks("""Here is the patch:
<<<<<<< REPLACE 1-1
new
>>>>>>>""")


def test_apply_patch_accepts_common_llm_wrapper_text():
    original = "Old line.\nSecond line."
    patch = """Here is the patch:
```markdown
<<<<<<< REPLACE 1-1
New line.
>>>>>>>
```"""

    assert apply_line_replace_patch(original, patch) == "New line.\nSecond line."


def test_patch_response_validator_accepts_wrapped_blocks_and_no_changes():
    assert is_valid_line_replace_patch_response("NO_CHANGES")
    assert is_valid_line_replace_patch_response("""```text
<<<<<<< REPLACE 1-1
New text.
>>>>>>>
```""")
