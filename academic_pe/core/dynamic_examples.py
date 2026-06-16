import os
import json
import logging
import asyncio
import re
import time
import threading
from typing import List, Dict, Optional

from academic_pe.core.config import load_config
from academic_pe.agents.factory import create_agent

logger = logging.getLogger(__name__)

# Cache of generated examples
_dynamic_examples_cache: List[Dict[str, str]] = []
# Epoch timestamp in seconds when examples were last generated
last_generated_at: float = 0.0

_examples_lock = asyncio.Lock()
_examples_generation_lock = asyncio.Lock()
_DYNAMIC_EXAMPLES_PATH = "config/dynamic_examples.json"
_DYNAMIC_EXAMPLES_META_PATH = "config/dynamic_examples_meta.json"
_PREVIOUS_EXAMPLE_LIMIT = 3
_PREVIOUS_TOPIC_CHAR_LIMIT = 160
_PREVIOUS_INSTRUCTIONS_CHAR_LIMIT = 500
_GENERATED_TOPIC_CHAR_LIMIT = 220
_GENERATED_INSTRUCTIONS_CHAR_LIMIT = 1400

DEFAULT_EXAMPLES_RU = [
    {
        "topic": "README для локального API сервиса",
        "instructions": "Опишите установку, запуск, переменные окружения и примеры запросов. Сохраняйте практичный технический стиль без лишней академической структуры."
    },
    {
        "topic": "Короткое стихотворение о дождливом городе",
        "instructions": "Напишите 12-16 строк с живым образным голосом, внутренним ритмом и без пояснительного анализа."
    },
    {
        "topic": "Аналитический отчёт о метриках алгоритмической сложности",
        "instructions": "Сделайте структурированный отчёт с выводами, ограничениями и формулами LaTeX только там, где они нужны для расчётов."
    }
]

DEFAULT_EXAMPLES_EN = [
    {
        "topic": "Technical README for a Local API Service",
        "instructions": "Describe installation, startup, environment variables, and request examples. Keep the style practical and avoid unnecessary academic structure."
    },
    {
        "topic": "Short Poem About a Rainy City",
        "instructions": "Write 12-16 lines with vivid imagery, a natural voice, and no explanatory analysis."
    },
    {
        "topic": "Analytical Report on Algorithmic Complexity Metrics",
        "instructions": "Create a structured report with findings, limitations, and LaTeX formulas only where they support the calculations."
    }
]


def get_default_examples(lang: str = "ru") -> List[Dict[str, str]]:
    if lang == "ru":
        return DEFAULT_EXAMPLES_RU
    return DEFAULT_EXAMPLES_EN


async def load_cached_examples(lang: str = "ru") -> List[Dict[str, str]]:
    global _dynamic_examples_cache, last_generated_at
    async with _examples_lock:
        if _dynamic_examples_cache:
            return _dynamic_examples_cache

        path = _DYNAMIC_EXAMPLES_PATH
        if os.path.exists(path):
            try:
                # Get file modification time as generation timestamp fallback
                mtime = os.path.getmtime(path)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        _dynamic_examples_cache = data
                        last_generated_at = mtime
                        return data
            except Exception as e:
                logger.warning("Failed to load dynamic examples from file: %s", e)

        # Fallback to local default list, mark last_generated_at as current time
        # so client sees a full TTL cycle on fallback
        last_generated_at = time.time()
        return get_default_examples(lang)


def clean_and_parse_json(text: str) -> List[Dict[str, str]]:
    text = text.strip()
    # Remove markdown code fences if present
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # Try parsing directly
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Regex search for the first [ to last ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        json_slice = text[start:end+1]
        try:
            data = json.loads(json_slice)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse valid JSON array from agent response: {text[:200]}")


async def generate_new_examples(timeout_seconds: Optional[float] = None):
    """
    Invokes the Example Generator agent to formulate 3 new artifact requests.
    Serializes requests using an asyncio.Lock to prevent overlapping runs,
    skips execution if examples were generated recently, and propagates exceptions.
    """
    global _dynamic_examples_cache, last_generated_at

    async with _examples_generation_lock:
        # Avoid running a new generation if one just finished in the last 10 seconds
        if time.time() - last_generated_at < 10.0:
            logger.info("Dynamic examples were generated very recently. Skipping generation.")
            return

        config = load_config("config/agents.yaml")
        if not getattr(config, "dynamic_examples_enabled", True):
            logger.info("Dynamic examples generation is disabled in settings. Skipping.")
            return

        agent_cfg = config.agents.get("example_generator")
        if not agent_cfg:
            logger.warning("example_generator agent configuration not found in agents.yaml.")
            return

        logger.info("Generating new dynamic examples via example_generator agent...")

        # Run in executor since BaseAgent calls block synchronously
        loop = asyncio.get_running_loop()

        previous_examples = _load_previous_examples_for_prompt()
        language_plan = _next_language_plan(config.ui.language)

        def run_agent():
            agent = create_agent(
                "example_generator",
                agent_cfg,
                retry_cfg=config.retry,
                cb_cfg=config.circuit_breaker
            )

            prompt = build_dynamic_examples_prompt(
                config.ui.language,
                previous_examples=previous_examples,
                language_plan=language_plan,
            )
            return agent.process(prompt)

        try:
            generation_future = loop.run_in_executor(None, run_agent)
            if timeout_seconds is not None and timeout_seconds > 0:
                raw_response = await asyncio.wait_for(asyncio.shield(generation_future), timeout=timeout_seconds)
            else:
                raw_response = await generation_future
            parsed = clean_and_parse_json(raw_response)

            # Validate structure
            valid_examples = []
            for item in parsed:
                if isinstance(item, dict) and "topic" in item and "instructions" in item:
                    valid_examples.append({
                        "topic": _truncate_text(item["topic"].strip(), _GENERATED_TOPIC_CHAR_LIMIT),
                        "instructions": _truncate_text(item["instructions"].strip(), _GENERATED_INSTRUCTIONS_CHAR_LIMIT),
                    })

            if len(valid_examples) > 0:
                async with _examples_lock:
                    _dynamic_examples_cache = valid_examples
                    last_generated_at = time.time()

                # Save to file
                os.makedirs("config", exist_ok=True)
                with open(_DYNAMIC_EXAMPLES_PATH, "w", encoding="utf-8") as f:
                    json.dump(valid_examples, f, ensure_ascii=False, indent=2)
                _save_dynamic_examples_meta(language_plan)
                logger.info("Successfully updated and saved dynamic examples.")
            else:
                logger.warning("Agent returned empty or invalid example list format.")
                raise ValueError("Agent returned empty or invalid example list format.")

        except asyncio.TimeoutError as te:
            logger.warning("Dynamic examples generation timed out after %.1fs; keeping cached examples.", timeout_seconds)
            raise te
        except Exception as e:
            logger.exception("Error generating dynamic examples: %s", e)
            raise e


def build_dynamic_examples_prompt(
    lang: str,
    previous_examples: List[Dict[str, str]] | None = None,
    language_plan: List[str] | None = None,
) -> str:
    plan = language_plan or _language_plan_for_primary(_normalize_example_language(lang))
    plan_lines = "\n".join(
        f"- Item {idx}: write topic and instructions in {language}."
        for idx, language in enumerate(plan, 1)
    )
    previous_block = ""
    if previous_examples:
        compact_previous_examples = _compact_previous_examples(previous_examples)
        previous_block = (
            "\n\n[Previous examples to avoid repeating]\n"
            + json.dumps(compact_previous_examples, ensure_ascii=False, indent=2)
            + "\nCreate substantially different examples: vary artifact types, domains, tones, constraints, and wording."
        )

    return (
        "Generate exactly 3 creative, diverse, and relevant artifact requests "
        "along with clear instructions for each.\n"
        "Examples are illustrative entry points only, not an exhaustive list of supported artifact types; "
        "include diverse forms and avoid implying that unknown or niche requests must be converted into these examples.\n"
        "Follow this exact language plan; do not translate all examples into one language:\n"
        f"{plan_lines}\n"
        "Use Russian for items marked 'ru' and English for items marked 'en'. "
        "Each item must be self-contained and useful as a prompt seed.\n"
        "Keep each topic under 120 characters and each instructions field concise: 2-5 sentences or a short bullet list. "
        "Do not write full documents, long rubrics, or deeply nested requirements inside examples.\n"
        f"{previous_block}\n\n"
        "Return ONLY a valid JSON array of objects without markdown code block syntax. "
        "Do not add a language field. Format:\n"
        "[\n"
        '  {"topic": "...", "instructions": "..."},\n'
        "  ...\n"
        "]"
    )


def _normalize_example_language(lang: str) -> str:
    return "ru" if str(lang).lower().startswith("ru") else "en"


def _truncate_text(text: str, max_chars: int) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _compact_previous_examples(examples: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [
        {
            "topic": _truncate_text(str(item.get("topic", "")), _PREVIOUS_TOPIC_CHAR_LIMIT),
            "instructions": _truncate_text(str(item.get("instructions", "")), _PREVIOUS_INSTRUCTIONS_CHAR_LIMIT),
        }
        for item in examples[:_PREVIOUS_EXAMPLE_LIMIT]
        if isinstance(item, dict) and item.get("topic") and item.get("instructions")
    ]


def _language_plan_for_primary(primary_language: str) -> List[str]:
    primary = _normalize_example_language(primary_language)
    secondary = "en" if primary == "ru" else "ru"
    return [primary, primary, secondary]


def _next_language_plan(preferred_lang: str) -> List[str]:
    meta = _load_dynamic_examples_meta()
    last_primary = meta.get("last_primary_language")
    if last_primary in {"ru", "en"}:
        primary = "en" if last_primary == "ru" else "ru"
    else:
        primary = _normalize_example_language(preferred_lang)
    return _language_plan_for_primary(primary)


def _load_previous_examples_for_prompt() -> List[Dict[str, str]]:
    if _dynamic_examples_cache:
        return list(_dynamic_examples_cache)
    if not os.path.exists(_DYNAMIC_EXAMPLES_PATH):
        return []
    try:
        with open(_DYNAMIC_EXAMPLES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [
                {"topic": str(item.get("topic", "")), "instructions": str(item.get("instructions", ""))}
                for item in data
                if isinstance(item, dict) and item.get("topic") and item.get("instructions")
            ]
    except Exception as e:
        logger.warning("Failed to load previous dynamic examples for prompt: %s", e)
    return []


def _load_dynamic_examples_meta() -> Dict[str, str]:
    if not os.path.exists(_DYNAMIC_EXAMPLES_META_PATH):
        return {}
    try:
        with open(_DYNAMIC_EXAMPLES_META_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Failed to load dynamic examples metadata: %s", e)
        return {}


def _save_dynamic_examples_meta(language_plan: List[str]) -> None:
    os.makedirs("config", exist_ok=True)
    primary = language_plan[0] if language_plan else "en"
    meta = {
        "last_primary_language": primary,
        "last_language_plan": language_plan,
        "updated_at": time.time(),
    }
    with open(_DYNAMIC_EXAMPLES_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


async def dynamic_examples_loop():
    """
    Infinite loop that updates examples periodically.
    """
    # Wait 5 seconds after server startup before triggering the first run
    # to let the server start cleanly without blocking instant checks
    await asyncio.sleep(5)

    while True:
        try:
            config = load_config("config/agents.yaml")
            enabled = getattr(config, "dynamic_examples_enabled", True)
            interval_mins = getattr(config, "dynamic_examples_interval_mins", 15)
            
            if enabled:
                await generate_new_examples()
            else:
                logger.info("Dynamic examples disabled. Skipping update.")
                
            # Read interval again in case it was updated while generating
            config = load_config("config/agents.yaml")
            interval_mins = getattr(config, "dynamic_examples_interval_mins", 15)
            sleep_sec = max(interval_mins, 1) * 60
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Exception in dynamic examples loop: %s", e)
            sleep_sec = 15 * 60

        try:
            await asyncio.sleep(sleep_sec)
        except asyncio.CancelledError:
            break
