# Руководство по Конфигурации (Configuration Guide)

Система **Academic Pipeline Engine** использует декларативный подход к конфигурации. Все параметры поведения вынесены из кода в YAML-файлы.

## Структура `agents.yaml`

Файл находится в `config/agents.yaml`. Содержит конфигурацию агентов и пайплайна.

```yaml
agents:
  writer:
    role: "Writer"
    model: "gpt-4o"
    temperature: 0.7         # 0.0 - 2.0 (OpenAI range)
    system_prompt: |
      You are an expert academic writer.
      ...

  reviewer:
    role: "Reviewer"
    model: "gpt-4o"
    temperature: 0.3
    system_prompt: |
      You are a strict academic reviewer.
      Return exactly one line: APPROVED or REJECTED...

pipeline:
  sections:
    - name: theory
      topic: "State Machines"
      instruction: "Structure it with H2 and H3 headers."
    - name: calculation
      topic: "Algorithmic Complexity"
      instruction: "Include LaTeX formulas (e.g. $O(n)$)."
    - name: conclusion
      topic: "Efficiency of State Machines"
      instruction: "Summarize key findings and implications."
```

### Параметры `temperature`

- OpenAI: `0.0` (строго) — `2.0` (креативно)
- Валидируется Pydantic (`Field(ge=0.0, le=2.0)`)

### Параметры `pipeline.sections`

| Поле | Описание |
|---|---|
| `name` | Ключ секции в `context` |
| `topic` | Тема главы (подставляется в промпт) |
| `instruction` | Дополнительные инструкции для Writer |

## Валидация (Pydantic V2)

Модель конфигурации (`src/core/config.py`):

```python
class AgentConfig(BaseModel):
    role: str
    model: str
    temperature: float = Field(ge=0.0, le=2.0)
    system_prompt: str

class SectionPrompt(BaseModel):
    name: str
    topic: str
    instruction: str

class PipelineConfig(BaseModel):
    sections: List[SectionPrompt]

class AppConfig(BaseModel):
    agents: Dict[str, AgentConfig]
    pipeline: PipelineConfig  # имеет значения по умолчанию
```

## Режимы запуска

### Без API-ключа (Mock-режим)

Если `OPENAI_API_KEY` не задан, `create_orchestrator()` использует `MockProvider`:

```python
from src.core.orchestrator import create_orchestrator

app = create_orchestrator()
app.run_pipeline()
```

### С реальным API

Установите переменную окружения:

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

Или создайте `.env` файл (потребуется `python-dotenv`).
