from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


class SectionPatchError(ValueError):
    pass


@dataclass(frozen=True)
class SearchReplaceBlock:
    search: str
    replace: str


_BLOCK_RE = re.compile(
    r"<<<<<<< SEARCH\s*\n(?P<search>.*?)\n=======\s*\n(?P<replace>.*?)\n>>>>>>> REPLACE",
    re.DOTALL,
)


def parse_search_replace_blocks(raw: str) -> List[SearchReplaceBlock]:
    text = raw.strip()
    if text == "NO_CHANGES":
        return []

    blocks = [
        SearchReplaceBlock(
            search=match.group("search").strip("\n"),
            replace=match.group("replace").strip("\n"),
        )
        for match in _BLOCK_RE.finditer(raw)
    ]
    if not blocks:
        raise SectionPatchError("No SEARCH/REPLACE blocks found.")

    consumed = _BLOCK_RE.sub("", raw).strip()
    if consumed:
        raise SectionPatchError("Patch response contains text outside SEARCH/REPLACE blocks.")

    for block in blocks:
        if not block.search:
            raise SectionPatchError("SEARCH block cannot be empty.")

    return blocks


def apply_search_replace_patch(original: str, patch_text: str) -> str:
    blocks = parse_search_replace_blocks(patch_text)
    updated = original

    for block in blocks:
        matches = updated.count(block.search)
        if matches == 0:
            raise SectionPatchError("SEARCH block did not match the section text.")
        if matches > 1:
            raise SectionPatchError("SEARCH block matched multiple locations.")
        updated = updated.replace(block.search, block.replace, 1)

    return updated
