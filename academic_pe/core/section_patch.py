from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


class SectionPatchError(ValueError):
    pass


@dataclass(frozen=True)
class LineReplaceBlock:
    start_line: int
    end_line: int
    content: str


_BLOCK_RE = re.compile(
    r"<<<<<<<[ \t]+REPLACE[ \t]+(?P<start>\d+)-(?P<end>\d+)\s*\n(?P<content>.*?)\n>>>>>>>[ \t]*(?:REPLACE)?",
    re.DOTALL,
)


def add_line_numbers(text: str) -> str:
    if not text:
        return ""
    lines = text.split('\n')
    return "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))


def strip_patch_code_fence(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 2:
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    return text


def parse_line_replace_blocks(
    raw: str,
    *,
    allow_text_outside_blocks: bool = False,
) -> List[LineReplaceBlock]:
    text = raw.strip()
    if text == "NO_CHANGES":
        return []

    blocks = []
    for match in _BLOCK_RE.finditer(raw):
        start = int(match.group("start"))
        end = int(match.group("end"))
        content = match.group("content")
        blocks.append(LineReplaceBlock(start_line=start, end_line=end, content=content))

    if not blocks:
        raise SectionPatchError("No REPLACE blocks found.")

    consumed = _BLOCK_RE.sub("", raw).strip()
    if consumed and not allow_text_outside_blocks:
        raise SectionPatchError("Patch response contains text outside REPLACE blocks.")

    # Validate ranges and overlaps
    for block in blocks:
        if block.start_line < 1:
            raise SectionPatchError(f"Invalid line number {block.start_line}: line numbers must be >= 1.")
        if block.start_line > block.end_line:
            raise SectionPatchError(
                f"Invalid range {block.start_line}-{block.end_line}: start must be <= end."
            )

    sorted_blocks = sorted(blocks, key=lambda b: b.start_line)
    for i in range(1, len(sorted_blocks)):
        prev = sorted_blocks[i - 1]
        curr = sorted_blocks[i]
        if curr.start_line <= prev.end_line:
            raise SectionPatchError(
                f"Overlapping REPLACE blocks: block {prev.start_line}-{prev.end_line} "
                f"overlaps with {curr.start_line}-{curr.end_line}."
            )

    return blocks


def is_valid_line_replace_patch_response(raw: str) -> bool:
    try:
        parse_line_replace_blocks(
            strip_patch_code_fence(raw),
            allow_text_outside_blocks=True,
        )
    except SectionPatchError:
        return False
    return True


def replace_lines(original: str, start_line: int, end_line: int, replacement: str) -> str:
    lines = original.split('\n')
    num_lines = len(lines)

    if start_line < 1 or end_line > num_lines:
        raise SectionPatchError(
            f"Line range {start_line}-{end_line} is out of bounds (1-{num_lines})."
        )
    if start_line > end_line:
        raise SectionPatchError(
            f"Invalid range {start_line}-{end_line}: start must be <= end."
        )

    # Replace the slice
    lines[start_line - 1 : end_line] = replacement.split('\n')
    return '\n'.join(lines)


def apply_line_replace_patch(original: str, patch_text: str) -> str:
    # Strip markdown fences if the LLM wrapped its response
    clean_patch_text = strip_patch_code_fence(patch_text)

    blocks = parse_line_replace_blocks(clean_patch_text, allow_text_outside_blocks=True)
    if not blocks:
        return original

    # To apply multiple edits without line shifting issues, sort by start_line descending
    sorted_descending = sorted(blocks, key=lambda b: b.start_line, reverse=True)
    updated = original
    for block in sorted_descending:
        updated = replace_lines(updated, block.start_line, block.end_line, block.content)

    return updated
