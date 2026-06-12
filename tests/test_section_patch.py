import pytest

from academic_pe.core.section_patch import SectionPatchError, apply_search_replace_patch, parse_search_replace_blocks


def test_no_changes_patch_returns_original():
    original = "Paragraph one.\n\nParagraph two."

    assert apply_search_replace_patch(original, "NO_CHANGES") == original


def test_search_replace_patch_updates_exact_span():
    original = "The complexity is O(n^2).\n\nThis remains unchanged."
    patch = """<<<<<<< SEARCH
The complexity is O(n^2).
=======
The complexity is O(n log n).
>>>>>>> REPLACE"""

    assert apply_search_replace_patch(original, patch) == "The complexity is O(n log n).\n\nThis remains unchanged."


def test_multiple_search_replace_blocks_apply_in_order():
    original = "Chapter 2 is missing.\nChapter 4 is also missing."
    patch = """<<<<<<< SEARCH
Chapter 2 is missing.
=======
Section 2 is present.
>>>>>>> REPLACE
<<<<<<< SEARCH
Chapter 4 is also missing.
=======
Section 3 is present.
>>>>>>> REPLACE"""

    assert apply_search_replace_patch(original, patch) == "Section 2 is present.\nSection 3 is present."


def test_patch_fails_when_search_does_not_match():
    with pytest.raises(SectionPatchError, match="did not match"):
        apply_search_replace_patch("Existing text.", """<<<<<<< SEARCH
Missing text.
=======
Replacement.
>>>>>>> REPLACE""")


def test_patch_fails_when_search_matches_multiple_locations():
    with pytest.raises(SectionPatchError, match="multiple"):
        apply_search_replace_patch("Repeat.\nRepeat.", """<<<<<<< SEARCH
Repeat.
=======
Replacement.
>>>>>>> REPLACE""")


def test_patch_fails_when_response_has_extra_text():
    with pytest.raises(SectionPatchError, match="outside"):
        parse_search_replace_blocks("""Here is the patch:
<<<<<<< SEARCH
old
=======
new
>>>>>>> REPLACE""")
