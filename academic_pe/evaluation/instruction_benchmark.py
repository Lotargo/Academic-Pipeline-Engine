from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from academic_pe.core.config import SectionPrompt
from academic_pe.instructions import InstructionCompiler
from academic_pe.manifests.resolver import ArtifactManifestResolver


_ROUTING_CASES = [
    ("academic report", "Write an academic report with methods and sources.", "report"),
    ("course section", "Write one course paper analysis section.", "unknown_freeform"),
    ("technical README", "Create a README with installation, usage, and configuration.", "technical_readme"),
    ("analytical memo", "Write an analytical memo with a recommendation.", "unknown_freeform"),
    ("school essay", "Write a school composition for grade 7.", "school_essay"),
    ("poem", "Write a poem in four stanzas.", "creative_poem"),
    ("technical note", "Write a concise technical note about an API.", "unknown_freeform"),
    ("plan", "Create a sprint plan with owners and risks.", "plan_document"),
    ("story", "Write a short story with a narrator.", "creative_story"),
    ("free article", "Write a readable article about urban gardens.", "unknown_freeform"),
]

_LEAKAGE = re.compile(
    r"Active Agent Contract|GREP TOOL AVAILABLE|USE_GREP:|Template Review Rubric|SEARCH/REPLACE",
    flags=re.IGNORECASE,
)
_ROLE_CONTAMINATION = re.compile(
    r"reviewer rubric|export gates?|prefer approved|blind reviewer",
    flags=re.IGNORECASE,
)
_ABSTRACT_STYLE = re.compile(
    r"natural human|AI-style|machine-like|undetectable|perplexity|burstiness",
    flags=re.IGNORECASE,
)


class VariantScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: str
    estimated_tokens: int = Field(ge=0)
    leakage_markers: int = Field(ge=0)
    role_contamination: int = Field(ge=0)
    abstract_style_markers: int = Field(ge=0)
    typed_scope_signals: int = Field(ge=0)
    specialized_role_signals: int = Field(ge=0)
    editorial_penalty: int = Field(ge=0)
    editorial_score: int = Field(ge=0)


class RoutingScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: int
    total: int
    failures: list[str] = Field(default_factory=list)


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routing: RoutingScore
    variants: list[VariantScore]
    preferred_variant: str


def score_variant(name: str, text: str) -> VariantScore:
    tokens = _estimate_tokens(text)
    leakage = len(_LEAKAGE.findall(text))
    contamination = len(_ROLE_CONTAMINATION.findall(text))
    abstract = len(_ABSTRACT_STYLE.findall(text))
    typed_scope = len(re.findall(r"section_brief|must_not_repeat|output_protocol|diagnostic_hash", text))
    specialized = int('"role":"evidence_reviewer"' in text and '"role":"editorial_reviewer"' in text)
    penalty = tokens + leakage * 400 + contamination * 250 + abstract * 150
    return VariantScore(
        variant=name,
        estimated_tokens=tokens,
        leakage_markers=leakage,
        role_contamination=contamination,
        abstract_style_markers=abstract,
        typed_scope_signals=typed_scope,
        specialized_role_signals=specialized,
        editorial_penalty=penalty,
        editorial_score=max(
            0,
            1000 - min(tokens, 1000) - leakage * 300 - contamination * 200 - abstract * 100
            + min(typed_scope, 8) * 40 + specialized * 300,
        ),
    )


def run_core15_benchmark() -> BenchmarkReport:
    resolver = ArtifactManifestResolver()
    failures: list[str] = []
    for topic, instructions, expected in _ROUTING_CASES:
        actual = resolver.resolve(topic=topic, instructions=instructions, language="en").contract.artifact
        if actual != expected:
            failures.append(f"{topic}: expected {expected}, got {actual}")

    compiler = InstructionCompiler()
    minimal = compiler.compile("writer", section=SectionPrompt(name="analysis", topic="Analysis", instruction=""))
    with_brief = compiler.compile(
        "writer",
        section=SectionPrompt(name="analysis", topic="Determine whether the evidence supports the claim", instruction=""),
        coverage={"central_claim": ["analysis"], "limitations": ["conclusion"]},
        section_names=["analysis", "conclusion"],
        selected_skill_ids=["direct_claims"],
    )
    evidence = compiler.compile("evidence_reviewer", selected_skill_ids=["source_triangulation"])
    editorial = compiler.compile("editorial_reviewer", selected_skill_ids=["direct_claims"])
    legacy = (
        "[Active Agent Contract] Full artifact contract. Template Review Rubric. Export gates. "
        "[GREP TOOL AVAILABLE] USE_GREP: pattern. Write in a natural human style and avoid AI-style prose. "
    ) * 4
    variants = [
        score_variant("current_prompts", legacy),
        score_variant("compiled_minimal", minimal.model_dump_json(exclude_none=True)),
        score_variant("compiled_section_brief", with_brief.model_dump_json(exclude_none=True)),
        score_variant(
            "compiled_specialized_reviewers",
            "\n".join([
                with_brief.model_dump_json(exclude_none=True),
                evidence.model_dump_json(exclude_none=True),
                editorial.model_dump_json(exclude_none=True),
            ]),
        ),
    ]
    # Preference is computed from anonymizable content metrics; variant labels do
    # not participate in scoring or selection.
    preferred = max(variants, key=lambda item: item.editorial_score).variant
    return BenchmarkReport(
        routing=RoutingScore(
            passed=len(_ROUTING_CASES) - len(failures),
            total=len(_ROUTING_CASES),
            failures=failures,
        ),
        variants=variants,
        preferred_variant=preferred,
    )


def _estimate_tokens(text: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return max(1, (len(text) + 3) // 4)
