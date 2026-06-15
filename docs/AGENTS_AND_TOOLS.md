# Агенты и Инструменты

Academic Pipeline Engine разделяет LLM-агентов и детерминированные инструменты. Агенты принимают решения и пишут текст; инструменты выполняют проверяемые операции: патчи, sandbox execution, DOCX/PDF export, QA и работу с секретами.

## Агенты

### BaseAgent И DefaultAgent

`academic_pe/agents/base.py` задает общий интерфейс:

```python
process(
    task_description: str,
    context: str | None = None,
    on_delta: Callable[[str], None] | None = None,
    document_sections: dict[str, str] | None = None,
) -> str
```

`DefaultAgent` собирает system/user prompt, вызывает provider и, если включено, выполняет self-critique.

### WriterAgent

`WriterAgent` (`academic_pe/agents/writer.py`) отвечает за:

- document plan;
- секционное drafting;
- continuation-aware writing;
- line-based patch revision;
- fallback full-section revision;
- self-verification после первой критики Reviewer;
- streaming deltas в UI;
- использование `document_sections` для контекста и вспомогательных операций.

Writer получает template/manifest/contract guidance до начала работы, поэтому должен писать под конкретный artifact type, а не под глобальный академический шаблон.

### ReviewerAgent

`ReviewerAgent` проверяет полный документ и возвращает:

```text
APPROVED
```

или:

```text
REJECTED
- [section_name]: line <number>: <issue>
- [general]: <issue>
```

Reviewer остается внешним качественным gate. Детерминированные проверки выполняются отдельно и могут создать synthetic rejection до вызова LLM Reviewer.

### PlannerAgent

`PlannerAgent` (`academic_pe/core/planner_agent.py`) используется для `template_mode: auto`.

Он строит:

- runtime document type;
- section list;
- section instructions;
- prompt manifest;
- style/review constraints.

Planner не пишет финальный документ. Его результат становится `RuntimeTemplate` и `RuntimePromptManifest`.

### PromptEnhancerAgent

`PromptEnhancerAgent` уточняет пользовательский brief через `/api/prompt/enhance`.

Задачи:

- убрать неоднозначность;
- сохранить artifact type;
- не добавлять лишний scope;
- не превращать creative/school/README/plan запросы в academic paper;
- вернуть structured JSON с `topic` и `instructions`;
- сохранить compact manifest/contract metadata.

### Example Generator

`example_generator` используется для dynamic examples и prompt enhancement backend. Интервал обновления примеров задается `dynamic_examples_interval_mins`.

## Agent Factory

`academic_pe/agents/factory.py` создает агентов из `AgentConfig`:

- выбирает provider;
- оборачивает provider в retry/circuit breaker;
- выбирает agent class по имени или `agent_type`;
- поддерживает регистрацию дополнительных agent types.

## Agent Adapters

`academic_pe/agent_adapters` переводит resolved contract в инструкции для конкретной роли:

- `prompt_enhancer.py`;
- `planner.py`;
- `writer.py`;
- `reviewer.py`;
- `researcher.py`;
- `exporter.py`;
- `registry.py`.

Adapters не выбирают manifest и не компилируют contracts. Они только формируют role-specific guidance.

## Self-Critique

Self-critique включается на уровне агента:

```yaml
agents:
  writer:
    self_critique:
      enabled: true
      temperature: 0.2
```

Это one-pass repair:

```text
agent draft -> internal critique -> repaired output
```

Self-critique не блокирует pipeline, не спрашивает пользователя и не заменяет Reviewer. В metadata сохраняется только короткое summary.

## LLM Providers

Абстракция находится в `academic_pe/core/llm.py`.

Поддерживаемые providers:

| Provider | Назначение |
|---|---|
| `mock` | Локальная разработка и тесты без API-ключей. |
| `openai` | OpenAI Chat Completions client. |
| `custom_openai` | OpenAI-compatible endpoint с custom `base_url`. |
| `anthropic` | Anthropic Messages API. |
| `google` | Google Gemini API. |
| `lm_studio` | Локальный LM Studio OpenAI-compatible server. |
| `zen` | OpenCode Zen OpenAI-compatible endpoint. |

Ключи берутся из `config/secrets.json` или переменных окружения.

## Детерминированные Инструменты

### Section Patch Tools

`academic_pe/core/section_patch.py` реализует line-based patching:

- `add_line_numbers(text)`;
- `parse_line_replace_blocks(raw)`;
- `replace_lines(original, start_line, end_line, replacement)`;
- `apply_line_replace_patch(original, patch_text)`.

Reviewer выдает замечания по line numbers, Writer отвечает patch-блоками, backend применяет их сам. Если patch невалиден, оркестратор переходит к full-section revision.

### Quality Gate

`academic_pe/core/quality_gate.py` проверяет:

- минимальный объем секций;
- баланс LaTeX braces и `\begin`/`\end`;
- отсутствие raw code fence delimiters в финальном тексте.

Quality gate выполняется до Reviewer и перед финальным `DONE`.

### Contract Drift Checks

`academic_pe/contracts/drift.py` сравнивает финальный output с active `ArtifactContract`.

Примеры проверок:

- AI markers;
- academic drift;
- genre/style drift;
- forbidden visualization;
- forbidden citations;
- forbidden title page;
- forbidden rubric.

Эти checks являются hard gates для очевидных нарушений, а Reviewer LLM остается качественной оценкой.

### Python Sandbox

`academic_pe/core/sandbox.py` выполняет блоки:

````markdown
```python-run
print(2 + 2)
```
````

Механика:

1. Код записывается во временный `.py` файл.
2. Запускается текущий Python interpreter с UTF-8 окружением.
3. `stdout` заменяет исходный fenced block.
4. При ошибке бросается `SandboxExecutionError`, а traceback возвращается Writer'у для исправления.
5. Есть timeout по умолчанию 15 секунд.

Sandbox используется, когда active contract или `academic_mode` требуют вычислений/visualization.

### DOCX Renderer

`academic_pe/tools/docx_renderer.py` создает DOCX через `python-docx`.

Поддержка:

- title/style settings из `config`;
- Markdown headings;
- paragraphs и inline formatting;
- списки;
- таблицы;
- LaTeX-like fragments;
- chart/image blocks;
- секции из active runtime template.

Renderer не генерирует новые идеи, а только верстает готовый контент.

### Export QA

`academic_pe/tools/export_qa.py` отвечает за explicit export:

- `sanitize_filename`;
- `resolve_export_filename`;
- `inspect_docx_artifacts`;
- `render_docx_pages`;
- `convert_docx_to_pdf`;
- `export_docx_with_qa`;
- `export_pdf_with_qa`.

Export QA проверяет:

- required sections;
- безопасный путь внутри export directory;
- корректное имя файла;
- DOCX structure;
- отсутствие грубых markdown artifacts;
- LibreOffice conversion status для PDF.

### LibreOffice Discovery

`academic_pe/tools/libreoffice.py` ищет `soffice`:

1. `LIBREOFFICE_PATH`;
2. `soffice` / `libreoffice` в `PATH`;
3. типовые пути Windows/macOS/Linux.

`GET /api/export/prerequisites` возвращает availability и install hint.

### Secrets

`academic_pe/core/secrets.py`:

- `get_secret(provider_name)`;
- `save_secret(provider_name, key)`;
- `is_secret_configured(provider_name)`.

Секреты не пишутся в logs и не должны попадать в Git.

## Инструменты В API

| Endpoint | Инструмент |
|---|---|
| `GET /api/templates` | TemplateLibrary list. |
| `POST /api/prompt/enhance` | PromptEnhancerAgent + manifest resolver. |
| `POST /api/run` | Orchestrator background run. |
| `POST /api/cancel` | Orchestrator cancellation event. |
| `GET /api/status/stream` | SSE stream из `current_run`. |
| `GET /api/export/prerequisites` | LibreOffice discovery. |
| `POST /api/export/docx` | DOCX renderer + export QA. |
| `POST /api/export/pdf` | DOCX renderer + LibreOffice PDF conversion + QA. |
| `GET /api/models` | Provider model listing. |
| `GET/POST /api/secrets` | Secrets status/update. |

## Безопасные Границы

- Agents не должны напрямую писать файлы экспорта.
- Manifest YAML не должен содержать исполняемый код.
- Contract S-expression не является языком программирования.
- Server не должен дублировать manifest/contract policy.
- Renderer и export QA не должны менять смысл документа.
- Selected-text и scoped editing должны проходить через constrained patch tools, а не через свободную перезапись всего документа.
