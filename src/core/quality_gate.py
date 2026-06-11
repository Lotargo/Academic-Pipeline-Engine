from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from src.core.config import QualityGateConfig


@dataclass
class GateResult:
    passed: bool
    issues: List[str] = field(default_factory=list)


def check_volume(context: Dict[str, str], cfg: QualityGateConfig) -> GateResult:
    if not cfg.volume.enabled:
        return GateResult(passed=True)

    issues: List[str] = []
    for name, text in context.items():
        text = text or ""
        char_count = len(text)
        if char_count < cfg.volume.min_chars:
            issues.append(
                f"Section '{name}' too short: {char_count} chars "
                f"(min {cfg.volume.min_chars})"
            )
    return GateResult(passed=len(issues) == 0, issues=issues)


def _find_tex_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    pos = 0
    while pos < len(text):
        dollar = text.find("$", pos)
        if dollar == -1:
            break
        if dollar + 1 < len(text) and text[dollar + 1] == "$":
            end = text.find("$$", dollar + 2)
            if end == -1:
                blocks.append(text[dollar:])
                break
            blocks.append(text[dollar:end + 2])
            pos = end + 2
        else:
            end = text.find("$", dollar + 1)
            if end == -1:
                blocks.append(text[dollar:])
                break
            blocks.append(text[dollar:end + 1])
            pos = end + 1
    return blocks


def _balanced_braces(s: str) -> bool:
    depth = 0
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def check_latex(context: Dict[str, str], cfg: QualityGateConfig) -> GateResult:
    if not cfg.latex.enabled:
        return GateResult(passed=True)

    issues: List[str] = []
    for name, text in context.items():
        text = text or ""
        blocks = _find_tex_blocks(text)

        for block in blocks:
            inner = block.strip("$")

            if not _balanced_braces(inner):
                issues.append(
                    f"Section '{name}' has unbalanced braces in: {block[:40]}..."
                )

            if inner.count("\\begin") != inner.count("\\end"):
                issues.append(
                    f"Section '{name}' has unmatched \\begin/\\end in: {block[:40]}..."
                )

    return GateResult(passed=len(issues) == 0, issues=issues)


def run_all(context: Dict[str, str], cfg: QualityGateConfig) -> GateResult:
    combined: List[str] = []
    for check_name, check_fn in [("volume", check_volume), ("latex", check_latex)]:
        result = check_fn(context, cfg)
        if not result.passed:
            combined.extend(result.issues)
    return GateResult(passed=len(combined) == 0, issues=combined)
