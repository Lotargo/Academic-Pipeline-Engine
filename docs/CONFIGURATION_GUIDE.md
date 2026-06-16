# Руководство по Конфигурации

Academic Pipeline Engine использует декларативную конфигурацию. Runtime-поведение описывается YAML-файлами, а backend валидирует их через Pydantic models в `academic_pe/core/config.py` и `academic_pe/core/templates.py`.

## Основные Файлы

| Файл | Назначение |
|---|---|
| `config/agents.example.yaml` | Стартовый пример. Скопируйте в `config/agents.yaml`. |
| `config/agents.yaml` | Локальный runtime config: агенты, pipeline, UI, quality gate. |
| `config/document_templates.yaml` | Сохраненные document templates и prompt manifests. |
| `config/artifact_manifests.yaml` | Artifact routing manifests, execution overlays и fallback. |
| `config/frontend_schema.json` | JSON Schema для UI config editor. |
| `config/secrets.json` | Локальные API-ключи, создается UI/secrets layer и не хранится в Git. |

## Быстрая Подготовка

```powershell
Copy-Item config/agents.example.yaml config/agents.yaml
```

Linux/macOS:

```bash
cp config/agents.example.yaml config/agents.yaml
```

Примерный конфиг использует `provider: mock`, поэтому генерация работает без внешних API-ключей.

## Структура `agents.yaml`

Минимальная форма:

```yaml
agents:
  writer:
    role: "Writer"
    provider: mock
    model: "gpt-4o"
    temperature: 0.7
    self_critique:
      enabled: true
      temperature: 0.2
    system_prompt: |
      You are an expert artifact-aware writer.

  reviewer:
    role: "Reviewer"
    provider: mock
    model: "gpt-4o"
    temperature: 0.3
    system_prompt: |
      Return APPROVED or REJECTED with actionable section-level issues.

retry:
  max_retries: 3
  base_delay: 1.0
  max_delay: 30.0

circuit_breaker:
  enabled: false
  failure_threshold: 5
  recovery_timeout: 30.0

quality_gate:
  volume:
    enabled: true
    min_chars: 200
  latex:
    enabled: true
  markdown:
    enabled: true

pipeline:
  sections:
    - name: theory
      topic: "State Machines"
      instruction: "Structure it with H2 and H3 headers."
  output_filename: "Final_Academic_Paper.docx"
  output_dir: "exports"
  language: "auto"
  template_mode: "custom"
  template_id: null
  academic_mode: false

ui:
  language: "ru"

dynamic_examples_enabled: true
dynamic_examples_interval_mins: 15
```

Если `planner` или `example_generator` отсутствуют, `load_config()` добавит default-настройки для них в runtime object. Лучше явно держать их в YAML, если вы хотите управлять провайдерами и моделями.

## Agents

Каждый агент описывается `AgentConfig`:

| Поле | Описание |
|---|---|
| `role` | Человекочитаемая роль агента. |
| `provider` | Один из поддерживаемых LLM providers. |
| `model` | Имя модели для выбранного provider. |
| `temperature` | `0.0` - максимально стабильно, `2.0` - максимально вариативно. |
| `system_prompt` | Базовая инструкция агента. |
| `base_url` | Для `custom_openai` и `lm_studio`. |
| `agent_type` | Optional override: `writer`, `reviewer`, `prompt_enhancer`, `default`. |
| `self_critique` | Optional one-pass self-repair перед возвратом результата. |

Поддерживаемые providers:

```text
mock
openai
custom_openai
anthropic
google
lm_studio
zen
```

Примеры:

```yaml
provider: openai
model: "gpt-4o"
```

```yaml
provider: anthropic
model: "claude-3-5-sonnet-20241022"
```

```yaml
provider: custom_openai
base_url: "http://localhost:11434/v1"
model: "local-model"
```

```yaml
provider: lm_studio
base_url: "http://localhost:1234/v1"
model: "local-model"
```

## Secrets

Ключи можно задать через UI (`GET/POST /api/secrets`) или через окружение:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
GOOGLE_API_KEY=...
CUSTOM_API_KEY=...
LM_STUDIO_API_KEY=...
ZEN_API_KEY=...
MISTRAL_API_KEY=...
LIBREOFFICE_PATH=/path/to/soffice
```

`config/secrets.json` локален, создается автоматически при сохранении ключей через интерфейс и не должен попадать в Git. Он имеет следующий формат:

```json
{
  "openai": "sk-...",
  "anthropic": "sk-ant-...",
  "google": "AIzaSy...",
  "zen": "zen-...",
  "mistral": "mistral-..."
}
```

## Pipeline

`pipeline` задает runtime-поведение:

| Поле | Значение |
|---|---|
| `sections` | Секции для `template_mode: custom`. |
| `output_filename` | Базовое имя export-файла; export layer может заменить его sanitized title-based именем. |
| `output_dir` | Каталог артефактов, обычно `exports`. |
| `title` | Заголовок документа; может переопределяться topic. |
| `language` | `auto`, `en`, `ru`, `zh`. |
| `template_mode` | `custom`, `fixed`, `auto`. |
| `template_id` | ID из `config/document_templates.yaml`, нужен для `fixed`. |
| `academic_mode` | Compatibility input для academic execution overlay. |

### Template Modes

`custom`

Использует `pipeline.sections` как live custom template. Подходит для ручной структуры.

`fixed`

Использует сохраненный шаблон:

```yaml
pipeline:
  template_mode: "fixed"
  template_id: "technical_note"
```

Доступные built-in templates:

- `academic_arxiv`
- `academic_report`
- `essay`
- `school_composition`
- `poem`
- `freeform_article`
- `technical_note`

`auto`

Использует `PlannerAgent`, чтобы на каждый запуск создать временный `RuntimeTemplate` и `RuntimePromptManifest`. Auto-шаблон сохраняется в run metadata, но не добавляется в библиотеку шаблонов автоматически.

## Artifact Manifests

`config/artifact_manifests.yaml` описывает типы артефактов и ограничения:

- `creative_poem`
- `creative_story`
- `school_essay`
- `academic_paper`
- `technical_readme`
- `plan_document`
- `report`
- `continuation_source`
- `unknown_freeform`

Manifest может задавать:

- `artifact_type`;
- `style`;
- `audience`;
- `structure`;
- `forbid`;
- mode overlays для `academic`;
- visualization policy.

Эти YAML-файлы являются data-only. Они не должны содержать исполняемый код, импорты, macros или eval-like директивы.

## Quality Gate

`quality_gate` запускается во время review loop и перед завершением pipeline.

```yaml
quality_gate:
  volume:
    enabled: true
    min_chars: 200
  latex:
    enabled: true
  markdown:
    enabled: true
```

Проверки:

- секции не пустые и длиннее `min_chars`;
- LaTeX-блоки имеют сбалансированные braces и `\begin`/`\end`;
- в финальном тексте не остались raw code fence delimiters.

## Retry И Circuit Breaker

Retry применяется к LLM provider calls:

```yaml
retry:
  max_retries: 3
  base_delay: 1.0
  max_delay: 30.0
```

Circuit breaker отключен по умолчанию:

```yaml
circuit_breaker:
  enabled: false
  failure_threshold: 5
  recovery_timeout: 30.0
```

## Style

`style` используется DOCX renderer'ом:

```yaml
style:
  font_name: "Times New Roman"
  font_size: 14
  title_font_size: 20
  line_spacing: 1.5
  first_line_indent_cm: 1.25
  alignment: "justify"
```

## UI И Dynamic Examples

```yaml
ui:
  language: "ru"

dynamic_examples_enabled: true
dynamic_examples_interval_mins: 15
```

`ui.language` влияет на язык интерфейсных примеров и prompt enhancement defaults. `pipeline.language` управляет языком генерации.

## API Overrides

`POST /api/run` может временно переопределить часть pipeline config:

```json
{
  "topic": "Project README",
  "instructions": "Create installation and usage sections.",
  "template_mode": "auto",
  "template_id": null,
  "academic_mode": false,
  "author": "Lotargo",
  "artifact_override": "technical_readme"
}
```

Эти значения относятся к конкретному run и сохраняются в metadata.

## Валидация

Ключевые модели:

- `ProviderEnum`
- `LanguagePolicy`
- `TemplateMode`
- `SelfCritiqueConfig`
- `AgentConfig`
- `RetryConfig`
- `CircuitBreakerConfig`
- `QualityGateConfig`
- `FSMConfig`
- `StyleConfig`
- `UIConfig`
- `PipelineConfig`
- `AppConfig`
- `DocumentTemplate`
- `PromptManifest`
- `RuntimeTemplate`
- `RuntimePromptManifest`

После изменения схемы для UI обновите JSON Schema:

```bash
poetry run python scripts/export_schema.py
```

## Конфигурация Локального Реестра (Registry)

Для работы реестра SQLite используется база данных, путь к которой жестко задан в API-сервере как `exports/_metadata/academic_pe_registry.sqlite3`. Дополнительной настройки в файлах конфигурации не требуется. При запуске тестов или скриптов раннеров база данных автоматически мокается или перенаправляется во временную папку.

## Запуск Сценариев Тестирования (Runners)

Скрипты-раннеры запускаются через Poetry и читают общую конфигурацию из `config/agents.yaml`. 

Пример запуска смоук-тестов:
```bash
# Запуск сценария продолжения документов
poetry run python scripts/continuation_smoke_runner.py academic_references

# Запуск смоук-теста OCR и поиска с использованием реального провайдера
poetry run python scripts/ocr_research_smoke_runner.py real_llm_web_research
```

Если вы хотите запустить сценарии с использованием заглушек (без отправки запросов к реальным API), передайте флаг `--allow-mock`:
```bash
poetry run python scripts/continuation_smoke_runner.py academic_references --allow-mock
```
