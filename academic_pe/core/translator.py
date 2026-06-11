import re
import logging

logger = logging.getLogger(__name__)


_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text or ""))


def translate_markdown_to_ru(text: str) -> str:
    """
    Translates English Markdown text to Russian, protecting LaTeX formulas
    from being translated or corrupted.
    """
    if not text:
        return text

    try:
        # Extract LaTeX formulas to prevent translation corruption
        formulas = []
        def replace_formula(match):
            formula = match.group(0)
            placeholder = f" __FORMULA_INDEX_{len(formulas)}__ "
            formulas.append(formula)
            return placeholder

        # Match double dollars ($$...$$) first, then single dollars ($...$)
        placeholder_text = re.sub(r'\$\$.*?\$\$', replace_formula, text, flags=re.DOTALL)
        placeholder_text = re.sub(r'\$.*?\$', replace_formula, placeholder_text)

        try:
            from deep_translator import GoogleTranslator
        except ImportError:
            logger.warning(
                "deep-translator is not installed; returning source text without machine translation."
            )
            return text

        translator = GoogleTranslator(source='en', target='ru')

        # Translate in paragraphs to avoid Google Translate 5000 character limit
        paragraphs = placeholder_text.split('\n')
        translated_paragraphs = []
        for p in paragraphs:
            if not p.strip():
                translated_paragraphs.append(p)
                continue
            try:
                # Translate paragraph
                trans_p = translator.translate(p.strip())
                translated_paragraphs.append(trans_p)
            except Exception as e:
                logger.warning("Paragraph translation failed: %s", e)
                # Fallback to original paragraph
                translated_paragraphs.append(p)

        translated_text = '\n'.join(translated_paragraphs)

        # Restore formulas
        for idx, formula in enumerate(formulas):
            placeholder = f"__FORMULA_INDEX_{idx}__"
            # Match case-insensitively and replace spaces using lambda to shield backslashes
            translated_text = re.sub(rf'\s*__FORMULA_INDEX_{idx}__\s*', lambda m: f" {formula} ", translated_text, flags=re.IGNORECASE)

        return translated_text
    except Exception as e:
        logger.exception("Failed to translate markdown to Russian")
        return text
