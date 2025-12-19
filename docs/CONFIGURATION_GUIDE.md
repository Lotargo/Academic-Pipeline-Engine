# Руководство по Конфигурации (Configuration Guide)

Система **Academic Pipeline Engine** использует декларативный подход к конфигурации. Все параметры поведения агентов вынесены из кода в YAML-файлы.

## Структура `agents.yaml`

Файл конфигурации находится в `config/agents.yaml`. Он определяет роли агентов, используемые модели и системные промпты.

```yaml
agents:
  writer:
    role: "Writer"
    model: "gpt-4o"          # Или gpt-3.5-turbo, local-model
    temperature: 0.7         # Креативность (0.0 - строго, 1.0 - вариативно)
    system_prompt: |
      You are an expert academic writer.
      Your goal is to draft sections...

  reviewer:
    role: "Reviewer"
    model: "gpt-4o"
    temperature: 0.3
    system_prompt: |
      You are a strict academic reviewer...
```

## Валидация (Pydantic)

Для загрузки и проверки конфигурации используется библиотека **Pydantic**. Это гарантирует, что если в YAML допущена ошибка (например, пропущено поле `model`), система сообщит об этом при старте, а не упадет в процессе работы.

Модель конфигурации (`src/core/config.py`):

```python
class AgentConfig(BaseModel):
    role: str
    model: str
    temperature: float
    system_prompt: str

class AppConfig(BaseModel):
    agents: Dict[str, AgentConfig]
```

## Интеграция с Frontend (JSON Schema)

Если вы разрабатываете веб-интерфейс для управления пайплайном, вы можете сгенерировать JSON Schema из Pydantic-моделей. Это позволит автоматически строить формы настроек.

**Команда для экспорта:**
```bash
python scripts/export_schema.py
```

**Результат (`config/frontend_schema.json`):**
```json
{
  "title": "AppConfig",
  "type": "object",
  "properties": {
    "agents": {
      "type": "object",
      "additionalProperties": { "$ref": "#/$defs/AgentConfig" }
    }
  },
  ...
}
```
Эту схему можно использовать с библиотеками типа [react-jsonschema-form](https://github.com/rjsf-team/react-jsonschema-form).
