import os
import json
import logging
import asyncio
import re
import time
from typing import List, Dict

from academic_pe.core.config import load_config
from academic_pe.agents.factory import create_agent

logger = logging.getLogger(__name__)

# Cache of generated examples
_dynamic_examples_cache: List[Dict[str, str]] = []
# Epoch timestamp in seconds when examples were last generated
last_generated_at: float = 0.0

_examples_lock = asyncio.Lock()

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

        path = "config/dynamic_examples.json"
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


async def generate_new_examples():
    """
    Invokes the Example Generator agent to formulate 3 new artifact requests.
    """
    global _dynamic_examples_cache, last_generated_at
    try:
        config = load_config("config/agents.yaml")
    except Exception as e:
        logger.error("Failed to load config for dynamic examples generation: %s", e)
        return

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

    def run_agent():
        agent = create_agent(
            "example_generator",
            agent_cfg,
            retry_cfg=config.retry,
            cb_cfg=config.circuit_breaker
        )

        lang = config.ui.language
        prompt = (
            f"Generate exactly 3 creative, diverse, and relevant artifact requests "
            f"along with clear instructions for each, tailored to the '{lang}' language. "
            f"Write the topics and instructions in the language corresponding to '{lang}' "
            f"(e.g. if 'ru' write in Russian, if 'en' write in English). "
            f"Return ONLY a valid JSON array of objects without markdown code block syntax. "
            f"Format:\n"
            f'[\n'
            f'  {{"topic": "...", "instructions": "..."}},\n'
            f'  ...\n'
            f']'
        )
        return agent.process(prompt)

    try:
        raw_response = await loop.run_in_executor(None, run_agent)
        parsed = clean_and_parse_json(raw_response)

        # Validate structure
        valid_examples = []
        for item in parsed:
            if isinstance(item, dict) and "topic" in item and "instructions" in item:
                valid_examples.append({
                    "topic": item["topic"].strip(),
                    "instructions": item["instructions"].strip()
                })

        if len(valid_examples) > 0:
            async with _examples_lock:
                _dynamic_examples_cache = valid_examples
                last_generated_at = time.time()

            # Save to file
            os.makedirs("config", exist_ok=True)
            with open("config/dynamic_examples.json", "w", encoding="utf-8") as f:
                json.dump(valid_examples, f, ensure_ascii=False, indent=2)
            logger.info("Successfully updated and saved dynamic examples.")
        else:
            logger.warning("Agent returned empty or invalid example list format.")

    except Exception as e:
        logger.exception("Error generating dynamic examples: %s", e)


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
