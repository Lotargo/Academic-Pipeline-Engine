# Агенты и Инструменты (Agents & Tools)

## 1. Агенты (`src/agents`)

### BaseAgent
Класс `BaseAgent` (`src/agents/base.py`) инкапсулирует логику взаимодействия с LLM.

**Интерфейс:**
*   `__init__(config: AgentConfig, llm: LLMProvider)` — принимает конфигурацию и провайдер LLM.
*   `process(task_description: str, context: str | None = None) -> str` — формирует промпт и вызывает LLM.

**Логика `process()`:**
1.  Берёт `system_prompt` из конфига.
2.  Если передан `context`, добавляет его в конец системного промпта.
3.  Вызывает `self.llm.generate()` с `model` и `temperature` из конфига.
4.  Возвращает текст ответа.

Writer и Reviewer — это экземпляры `BaseAgent` с разными конфигами из `agents.yaml`.

## 2. LLM Provider (`src/core/llm.py`)

Абстракция над LLM API через паттерн **Strategy**.

### LLMProvider (ABC)
```python
class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str,
                 model: str, temperature: float) -> str: ...
```

### OpenAIProvider
*   Читает `OPENAI_API_KEY` из окружения.
*   При отсутствии ключа вызывает `ValueError` (не тихий fallback).
*   Пробрасывает исключения API наверх (нет тихих ошибок).

### MockProvider
*   Возвращает шаблонный текст для тестов и CI/CD.
*   Не требует API-ключа.
*   Используется по умолчанию в `create_orchestrator()`.

## 3. Инструменты (`src/tools`)

Инструменты — детерминированные функции для работы, недоступной LLM.

### Docx Renderer (`src/tools/docx_renderer.py`)

Генерация документа Word из словаря контента.

**Вход:** `Dict[str, str]` (ключи: `theory`, `calculation`, `conclusion`)

**Логика:**
1.  Создаёт объект `Document`.
2.  Генерирует титульный лист.
3.  Парсит Markdown-разметку:
    *   `# Header` → заголовок Word.
    *   `**Bold**` → жирный шрифт.
    *   `$Formula$` → LaTeX-подобный парсинг формул.
4.  Сохраняет `.docx` на диск.
