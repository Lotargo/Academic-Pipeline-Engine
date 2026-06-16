# Возможности и Реализованные Решения

Этот документ собирает публично полезную часть внутренних `dev_docs`: не спринтовые заметки, а итоговые решения, границы поведения и фактические возможности Academic Pipeline Engine.

`dev_docs/` остается рабочей зоной для планов, smoke notes и промежуточных решений. `docs/` описывает то, что важно понимать пользователю, контрибьютору или человеку, оценивающему архитектуру проекта.

## Product Positioning

Academic Pipeline Engine построен как локальный document workspace, а не как один prompt вокруг LLM.

Ключевая идея: пользователь просит не просто "текст", а конкретный артефакт. Поэтому система сначала определяет тип работы, режим исполнения, ограничения, структуру и источники контекста, а уже потом передает задачу агентам.

Практический результат:

- creative/story/poem запросы не превращаются в academic paper;
- README и technical reports сохраняют практический формат;
- school essays могут оставаться школьными по регистру;
- academic/RGR/coursework документы получают строгую структуру, расчеты, источники и проверку там, где это уместно;
- continuation работает с прошлым документом как с текущим состоянием артефакта, а не как с простым приложенным текстом.

## Artifact-First Agent Architecture

Проект ушел от academic-first поведения к artifact-first архитектуре.

Поток принятия решения:

```text
user request
  -> artifact manifest resolution
  -> runtime contract
  -> agent-specific contract guidance
  -> planner / writer / reviewer / exporter behavior
```

Основные решения:

- manifests хранятся как data-only YAML;
- runtime boundary проходит через Pydantic-модели и Python-валидаторы;
- contract compilation, fallback behavior и prompt rendering выполняются в коде, а не в YAML;
- `decision_summary` хранит короткие диагностические факты, но не chain-of-thought;
- unknown/freeform fallback сохраняет намерение пользователя и не академизирует запрос автоматически.

## Standard And Academic Modes

`standard` и `academic` являются режимами исполнения, а не двумя разными продуктами.

`standard`:

- сохраняет жанр и естественный формат артефакта;
- избегает лишних титульных страниц, rubric, citations, tables и formulas;
- подходит для creative, school, README, plan, report и freeform задач.

`academic`:

- добавляет строгость, проверку допущений и доказательность;
- может включать методологию, источники, расчеты и визуализации для совместимых артефактов;
- не должен превращать стих, рассказ или README в исследовательскую статью без явного запроса.

## Runtime Contracts And S-Expression Guidance

Manifest слой компилируется в `ArtifactContract`, а затем в компактный S-expression блок для агентов.

Пример формы:

```clojure
(document
  (artifact creative_poem)
  (language ru)
  (mode standard)
  (forbid academic_drift title_page citations rubric ai_markers)
  (requirement min_lines 12))
```

Важно:

- contract DSL является данными, не исполняемым кодом;
- validation и drift checks выполняются Python-кодом;
- агенты получают уже отрендеренные инструкции и не читают manifests напрямую;
- continuation может наследовать предыдущий resolved manifest/contract и затем применить новую инструкцию пользователя.

## Prompt Enhancement

Prompt enhancer не должен "раздувать" задачу. Его задача - снять неоднозначность и сохранить пользовательский artifact type.

Правила:

- не менять artifact type без запроса;
- не добавлять title page, citations, rubric или academic apparatus по умолчанию;
- не терять детали пользователя;
- возвращать структурированный `topic` и `instructions`;
- сохранять compact manifest/contract metadata.

## Continuation, Editing And Merge

Continuation рассматривает предыдущий документ как текущее состояние артефакта.

Система различает намерения:

- `append` / `continue_append`;
- `bridge` / `bridge_and_continue`;
- `revise_in_place`;
- expansion или completion конкретной секции;
- reference/bibliography update;
- restructure, если пользователь явно просит перестройку.

Реализованные принципы:

- Planner строит continuity dossier и edit plan;
- Writer пишет требуемые фрагменты, а не отдельный новый документ;
- merge logic вставляет продолжение до terminal sections вроде references/appendices;
- bibliography/reference registry помогает сохранять и дедуплицировать источники;
- internal planning labels не должны попадать в preview/export;
- UI может показывать operation summary и diff/editorial layer, но экспорт остается чистым.

## Safe Editing And Patch Tools

Для ревизий проект использует constrained editing вместо свободной полной перезаписи.

Ключевой механизм:

- Reviewer дает line-aware замечания;
- Writer возвращает line-based replacement;
- backend применяет patch сам;
- при невалидном patch оркестратор переходит к безопасному fallback.

Это снижает риск случайно перезаписать соседние секции и делает поведение ближе к IDE-style agent tooling, но для документов.

## OCR, Attachments And Web Research

APE поддерживает reference attachments и OCR/research pipeline, но с жесткими ролевыми границами.

Правила boundary:

- web search запускается только при включенном `web_search_enabled`;
- Researcher не должен запускаться в обычном standard pipeline;
- research принадлежит Planning phase;
- Writer не ищет, не краулит, не выбирает источники и не получает raw search findings;
- Planner получает OCR/research материалы, выбирает релевантные факты и передает Writer только curated plan/source notes;
- passive attachments проходят через Planner-curation;
- continuation source documents сохраняют структуру и стиль прошлого документа настолько, насколько это возможно.

OCR:

- PDF/изображения обрабатываются через Mistral Document AI OCR, если настроен ключ;
- есть fallback для локального чтения поддерживаемых форматов;
- действует token guardrail для больших вложений;
- OCR outputs и attachments сохраняются как local artifacts.

Web research:

- DuckDuckGo search/crawling выполняется детерминированным модулем и ResearcherAgent;
- используется дедупликация и сохранение source metadata;
- raw research logs остаются диагностическими файлами, а компактные source notes попадают в planner context.

## Export, QA And LibreOffice

Генерация и экспорт разделены намеренно.

Pipeline сначала создает и сохраняет draft. DOCX/PDF появляются только после явного действия пользователя.

Экспортный слой:

- рендерит DOCX через `python-docx`;
- конвертирует PDF через LibreOffice/`soffice`, если он доступен;
- проверяет prerequisites через `GET /api/export/prerequisites`;
- генерирует safe filenames из названия документа;
- валидирует output path внутри export directory;
- запускает structural export QA;
- умеет экспортировать active и archived documents в правильный `exports/<run_id>`.

LibreOffice discovery:

1. `LIBREOFFICE_PATH`;
2. `soffice` / `libreoffice` в `PATH`;
3. типовые пути Windows, macOS и Linux.

## Python Sandbox

Academic/calculation-heavy документы могут использовать fenced blocks:

````markdown
```python-run
print(2 + 2)
```
````

Sandbox выполняет код в текущем Python environment с UTF-8 окружением, timeout и error feedback. Успешный `stdout` заменяет исходный block; traceback возвращается Writer'у для исправления.

Доступные библиотеки включают:

- `pandas`;
- `sympy`;
- `scipy`;
- `matplotlib`.

Sandbox нужен для расчетов, формул, таблиц и графиков, но не должен включаться в несовместимых creative/standard задачах без необходимости.

## Local SQLite Registry

Проект перешел от ad-hoc metadata files к локальному SQLite registry.

Граница хранения:

```text
SQLite = durable registry, indexes, statuses, relationships, compact metadata
exports/ = generated files, OCR payloads, research logs, smoke/quality artifacts
config/ = active local configuration and secrets
```

SQLite хранит:

- runs;
- participating agents/providers/models;
- artifacts;
- runtime snapshots;
- sections;
- sources;
- evaluations;
- compact events.

Filesystem хранит большие payloads: DOCX/PDF/Markdown, OCR outputs, research logs, rendered previews and diagnostics.

PostgreSQL/Redis остаются будущими адаптерами для multi-user/server mode, но не являются текущей зависимостью.

## Frontend Workspace

Next.js UI развивается как desktop-grade workspace, а не как простая форма.

Реализованные UX-решения:

- resizable sidebar;
- history archive/delete flows;
- archived works modal;
- profile modal with nickname/avatar/theme/language;
- author metadata in generated/exported documents;
- live document canvas;
- FSM monitor with SSE status lines;
- console panel as detailed log source;
- visible export actions;
- compact typography and pastel color system;
- continuation controls and editorial/diff layer.

## Smoke And Quality Gates

Помимо unit/integration tests, проект содержит специализированные runners:

- OCR/research smoke scenarios;
- OCR/research quality evaluation;
- continuation smoke runner;
- real-provider diagnostic smoke scenarios for broad behavior changes.

Проверяемые классы регрессий:

- web search не должен запускаться при выключенном activator;
- raw research findings не должны попадать Writer'у;
- passive attachments должны идти через Planner;
- continuation не должна создавать отдельный disconnected document;
- internal planning labels не должны попадать в final output;
- references/appendices должны оставаться terminal;
- mojibake/smart punctuation normalization не должна ломать финальный текст.

## Current Public Status

Реализовано:

- artifact-first manifests/contracts;
- standard/academic execution overlays;
- prompt enhancement;
- continuation intent and merge operations;
- heading policies and internal-only filtering;
- reference registry and bibliography merge;
- line-based revision;
- Python sandbox;
- OCR/research integration with planner boundary;
- SQLite registry;
- DOCX/PDF explicit export;
- export QA and LibreOffice discovery;
- desktop-grade Next.js workspace;
- smoke/quality runners and regression coverage.

Остается зоной дальнейшего развития:

- более глубокая visual QA для DOCX/PDF через vision-capable reviewer;
- richer provider capability detection;
- optional future PostgreSQL/Redis adapters;
- более полный DOCX round-trip editing с сохранением Word styles;
- расширенная UI-навигация по registry/read model.
