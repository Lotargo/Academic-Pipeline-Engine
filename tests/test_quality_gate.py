from academic_pe.core.quality_gate import check_volume, check_latex, run_all
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
