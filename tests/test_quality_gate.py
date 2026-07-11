import pytest

from academic_pe.core.quality_gate import (
    check_continuation_integrity,
    check_latex,
    check_prompt_leakage,
    check_unicode_hygiene,
    check_volume,
    run_all,
)
from academic_pe.core.config import QualityGateConfig, VolumeGateConfig, LatexGateConfig


def _full_cfg(volume_enabled=True, latex_enabled=True, min_chars=200):
    return QualityGateConfig(
        volume=VolumeGateConfig(enabled=volume_enabled, min_chars=min_chars),
        latex=LatexGateConfig(enabled=latex_enabled),
    )


class TestVolumeCheck:
    def test_passes_when_above_minimum(self):
        cfg = _full_cfg(min_chars=10)
        result = check_volume({"theory": "x" * 20}, cfg)
        assert result.passed
        assert result.issues == []

    def test_fails_when_below_minimum(self):
        cfg = _full_cfg(min_chars=100)
        result = check_volume({"theory": "too short"}, cfg)
        assert not result.passed
        assert len(result.issues) == 1
        assert "theory" in result.issues[0]
        assert "100" in result.issues[0]

    def test_disabled_always_passes(self):
        cfg = _full_cfg(volume_enabled=False, min_chars=10_000)
        result = check_volume({"theory": "tiny"}, cfg)
        assert result.passed

    def test_empty_context_passes(self):
        cfg = _full_cfg(min_chars=100)
        result = check_volume({}, cfg)
        assert result.passed

    def test_multiple_sections_one_fails(self):
        cfg = _full_cfg(min_chars=50)
        result = check_volume(
            {"theory": "x" * 100, "calculation": "short", "conclusion": "x" * 60},
            cfg,
        )
        assert not result.passed
        assert len(result.issues) == 1
        assert "calculation" in result.issues[0]


class TestLatexCheck:
    def test_passes_without_latex(self):
        cfg = _full_cfg()
        result = check_latex({"theory": "plain text without formulas"}, cfg)
        assert result.passed

    def test_passes_with_valid_formulas(self):
        cfg = _full_cfg()
        result = check_latex(
            {"calculation": r"Formula $E=mc^2$ and $O(n \log n)$"},
            cfg,
        )
        assert result.passed

    def test_passes_display_math(self):
        cfg = _full_cfg()
        result = check_latex(
            {"theory": r"Display: $$\sum_{i=1}^{n} i$$ inline"},
            cfg,
        )
        assert result.passed

    def test_detects_unopened_brace_in_formula(self):
        cfg = _full_cfg()
        result = check_latex(
            {"theory": r"$formula}without{opening$"},
            cfg,
        )
        assert not result.passed
        assert "unbalanced" in result.issues[0]

    def test_passes_with_balanced_braces(self):
        cfg = _full_cfg()
        result = check_latex(
            {"theory": r"$\alpha + \beta = \gamma$"},
            cfg,
        )
        assert result.passed

    def test_fails_on_unbalanced_braces(self):
        cfg = _full_cfg()
        result = check_latex(
            {"calculation": r"$E=mc^{2+1$"},
            cfg,
        )
        assert not result.passed
        assert len(result.issues) == 1
        assert "unbalanced" in result.issues[0]

    def test_fails_on_unmatched_begin_end(self):
        cfg = _full_cfg()
        result = check_latex(
            {"theory": r"$\begin{align} x = 1$"},
            cfg,
        )
        assert not result.passed
        assert len(result.issues) == 1
        assert "unmatched" in result.issues[0]

    def test_disabled_always_passes(self):
        cfg = _full_cfg(latex_enabled=False)
        result = check_latex({"theory": r"$E=mc^{2+1$"}, cfg)
        assert result.passed

    def test_empty_context_passes(self):
        cfg = _full_cfg()
        result = check_latex({}, cfg)
        assert result.passed


class TestRunAll:
    def test_combines_multiple_failures(self):
        cfg = _full_cfg(min_chars=1000, latex_enabled=True)
        result = run_all(
            {"theory": "short", "calculation": r"x" * 1000 + r"$broken{formula$"},
            cfg,
        )
        assert not result.passed
        assert len(result.issues) == 2

    def test_passes_all(self):
        cfg = _full_cfg(min_chars=10)
        result = run_all(
            {"theory": "x" * 20, "calculation": r"valid $E=mc^2$"},
            cfg,
        )
        assert result.passed
        assert result.issues == []


class TestMarkdownCheck:
    def test_passes_clean_content(self):
        cfg = _full_cfg()
        from academic_pe.core.quality_gate import check_markdown_artifacts
        result = check_markdown_artifacts({"theory": "1. Introduction\nSome clean paragraph."}, cfg)
        assert result.passed

    def test_fails_on_raw_code_fence(self):
        cfg = _full_cfg()
        from academic_pe.core.quality_gate import check_markdown_artifacts
        result = check_markdown_artifacts({"theory": "```markdown\n1. Introduction\n```"}, cfg)
        assert not result.passed
        assert len(result.issues) == 1
        assert "wrapped in raw Markdown code block delimiter" in result.issues[0]

    def test_allows_internal_technical_code_fences(self):
        cfg = _full_cfg()
        from academic_pe.core.quality_gate import check_markdown_artifacts

        result = check_markdown_artifacts(
            {
                "api": (
                    "Use the endpoint below.\n\n"
                    "```bash\n"
                    "curl https://api.example.test/weather\n"
                    "```\n\n"
                    "Response:\n"
                    "```json\n"
                    "{\"ok\": true}\n"
                    "```"
                )
            },
            cfg,
        )

        assert result.passed


class TestIntegrityGates:
    def test_unicode_hygiene_rejects_replacement_character(self):
        result = check_unicode_hygiene({"body": "Clean text \ufffd with damaged byte."}, _full_cfg())

        assert not result.passed
        assert "replacement character" in result.issues[0]

    @pytest.mark.parametrize("character", ["\ufeff", "\u00ad", "\ue000", "\x01"])
    def test_unicode_hygiene_rejects_non_exportable_characters(self, character):
        result = check_unicode_hygiene({"body": f"Text{character}with hidden character."}, _full_cfg())

        assert not result.passed
        assert "Repair the text before export" in result.issues[0]

    def test_unicode_hygiene_accepts_valid_russian_text(self):
        result = check_unicode_hygiene({"body": "В рамках данного раздела приведён анализ."}, _full_cfg())

        assert result.passed

    def test_prompt_leakage_rejects_protocol_marker_and_placeholder(self):
        result = check_prompt_leakage(
            {"body": "Draft text.\nUSE_GREP\n[контекст раздела 1]"},
            _full_cfg(),
        )

        assert not result.passed
        assert any("prompt/internal marker" in issue for issue in result.issues)
        assert any("unresolved placeholder" in issue for issue in result.issues)

    def test_prompt_leakage_rejects_internal_context_marker(self):
        result = check_prompt_leakage({"body": "[Document Plan]\nPrivate outline."}, _full_cfg())

        assert not result.passed
        assert "prompt/internal marker" in result.issues[0]

    def test_run_all_blocks_export_gate_for_unresolved_placeholder(self):
        result = run_all(
            {"body": "The final analysis is incomplete: [TODO add validated result]."},
            _full_cfg(min_chars=10),
        )

        assert not result.passed
        assert any("unresolved placeholder" in issue for issue in result.issues)

    def test_run_all_rejects_global_duplicate_labels_without_document_state(self):
        result = run_all(
            {"first": "Table 1 contains baseline values.", "second": "Table 1 contains updated values."},
            _full_cfg(min_chars=10),
        )

        assert not result.passed
        assert any("Duplicate table label '1'" in issue for issue in result.issues)


class TestContinuationIntegrityCheck:
    def test_passes_without_document_state(self):
        result = check_continuation_integrity({"body": "Clean continuation."})

        assert result.passed

    def test_rejects_body_content_after_terminal_section(self):
        result = check_continuation_integrity(
            {
                "analysis": "Main body.",
                "references": "1. Existing source.",
                "continuation": "This should be before references.",
            },
            {
                "terminal_sections": ["references"],
                "source_sections": [{"name": "references", "title": "References"}],
            },
        )

        assert not result.passed
        assert "appears after terminal section 'references'" in result.issues[0]

    def test_rejects_visible_internal_planning_labels(self):
        result = check_continuation_integrity(
            {"story": "Opening paragraph.\n\n## Red flags\n\nInternal note."},
            {"terminal_sections": [], "source_sections": []},
        )

        assert not result.passed
        assert "internal planning label" in result.issues[0]

    def test_rejects_duplicate_boundary_heading(self):
        result = check_continuation_integrity(
            {"body": "Text.\n\n## Conclusion\n\nSecond ending."},
            {
                "terminal_sections": [],
                "source_sections": [{"name": "conclusion", "title": "Conclusion"}],
            },
        )

        assert not result.passed
        assert "Duplicate conclusion" in result.issues[0]

    def test_rejects_duplicate_structural_labels(self):
        result = check_continuation_integrity(
            {
                "analysis": "Table 1 summarizes baseline values.",
                "continuation": "Table 1 summarizes new values.",
            },
            {"terminal_sections": [], "source_sections": []},
        )

        assert not result.passed
        assert "Duplicate table label '1'" in result.issues[0]

    def test_rejects_numeric_citation_without_reference_entry(self):
        result = check_continuation_integrity(
            {"analysis": "The claim is supported by [2]."},
            {
                "terminal_sections": ["references"],
                "source_sections": [{"name": "references", "title": "References"}],
                "reference_registry": [{"raw_text": "1. Existing source."}],
            },
        )

        assert not result.passed
        assert "Numeric citation [2] has no matching reference entry" in result.issues[0]

    def test_rejects_language_drift_from_source_style_profile(self):
        result = check_continuation_integrity(
            {"body": "This continuation suddenly switches into English prose."},
            {
                "terminal_sections": [],
                "source_sections": [{"name": "body", "title": "Body"}],
                "style_profile": {"language_hint": "ru", "register_hint": "neutral"},
            },
        )

        assert not result.passed
        assert "Continuation language drift detected" in result.issues[0]

    def test_rejects_register_drift_from_narrative_to_academic(self):
        result = check_continuation_integrity(
            {
                "story": (
                    "The methodology analyzes the protagonist's behavioral pattern. "
                    "Therefore, the result indicates a measurable narrative transition."
                )
            },
            {
                "terminal_sections": [],
                "source_sections": [{"name": "story", "title": "Story"}],
                "style_profile": {
                    "language_hint": "en",
                    "register_hint": "personal_or_narrative",
                },
            },
        )

        assert not result.passed
        assert "Continuation register drift detected" in result.issues[0]

    def test_run_all_includes_continuation_integrity(self):
        result = run_all(
            {"analysis": "x" * 20, "references": "x" * 20, "tail": "x" * 20},
            _full_cfg(min_chars=10),
            document_state={"terminal_sections": ["references"], "source_sections": []},
        )

        assert not result.passed
        assert any("appears after terminal section" in issue for issue in result.issues)
