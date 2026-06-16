<div align="center">
  <img src="./assets/logo.svg" alt="Academic Pipeline Engine Logo" width="760"/>
  <br>
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Next.js-UI-black" alt="Next.js UI"/>
  <img src="https://img.shields.io/badge/Status-Active%20Prototype-orange" alt="Status"/>
  <img src="https://img.shields.io/badge/License-GPLv3-blue" alt="License"/>
</div>

# Academic Pipeline Engine

Academic Pipeline Engine - рабочий прототип агентной системы для подготовки, ревью, продолжения и экспорта документов. Проект ориентирован не только на академические статьи: он умеет маршрутизировать запросы по типу артефакта, сохранять жанр и структуру, запускать текстовый pipeline через LLM-агентов и отдельно экспортировать готовый черновик в DOCX/PDF.

Система состоит из FastAPI backend, Next.js интерфейса, FSM-оркестратора, конфигурируемых агентов, библиотеки шаблонов, manifest/contract слоя, quality gate, истории работ и экспортного QA. Локально проект можно поднять в mock-режиме без API-ключей.

## Возможности

- Генерация черновиков по теме, инструкциям, выбранному шаблону и режиму исполнения.
- Artifact-first маршрутизация: poem, story, school essay, academic paper, technical README, plan, report, continuation и freeform fallback.
- Два режима исполнения:
  - `standard` сохраняет запрошенный жанр без лишней академизации.
  - `academic` добавляет строгость, проверку допущений и доказательность там, где это совместимо с артефактом.
- Режимы шаблонов `custom`, `fixed`, `auto`:
  - `custom` берет секции из `config/agents.yaml`;
  - `fixed` использует сохраненный шаблон из `config/document_templates.yaml`;
  - `auto` строит runtime-шаблон через `PlannerAgent`.
- Manifest/contract слой компилирует пользовательский замысел в проверяемый runtime contract и S-expression блок для агентов.
- Prompt enhancement через `/api/prompt/enhance` с сохранением выбранного manifest/contract metadata.
- Continuation mode с автоматическим определением намерений (`append`/`bridge`/`revise_in_place`), построением Edit Plan и слиянием через `section_patch` (новая генерация продолжает прошлую работу, сохраняя исходную структуру, стиль и метаданные).
- Агентный pipeline `INIT -> PLANNING -> DRAFTING -> REVIEWING -> RENDERING -> DONE`.
- Writer/Reviewer loop с line-based patch revision и fallback на полную перегенерацию секции.
- One-pass self-critique для агентов, если включен `self_critique`.
- Quality gate: объем секций, LaTeX-баланс, raw code fence/Markdown artifacts.
- Contract drift checks: жанровый дрейф, AI markers, запрещенные title page/citations/rubric/visualizations.
- Academic sandbox для блоков `python-run` с `pandas`, `sympy`, `scipy`, `matplotlib` и автоисправлением при ошибках выполнения.
- Интеграция распознавания вложений (PDF/картинки через Mistral Document AI OCR) и веб-исследований (DuckDuckGo crawling, BeautifulSoup парсинг, SHA-256 дедупликация) с Leakage Barrier защитой писателя от утечки контекста.
- Полноценная база данных SQLite (`academic_pe_registry.sqlite3`) для надежного сохранения истории запусков, конфигураций агентов, шаблонов, оценок и логов событий с контекстным управлением транзакциями (locked-safe).
- Сценарии автоматического тестирования и оценки качества (Smoke & Quality runners для OCR, поиска и продолжения документов) с сохранением результатов в реестр.
- Explicit export: генерация сохраняет черновик, а DOCX/PDF создаются отдельным действием.
- DOCX renderer на `python-docx`: Markdown headings, списки, таблицы, формулы, простые chart-блоки.
- PDF export через LibreOffice/`soffice`, если он доступен в системе.
- Next.js UI: live preview, FSM monitor, SSE-статусы, консоль логов, конфиг-редактор, история, архив, профиль, theme/language controls, continuation controls.
- Тесты для оркестратора, API, конфигов, шаблонов, manifests, contracts, adapters, sandbox, export QA и frontend schema.

## Структура

```text
academic_pe/
  agent_adapters/   # manifest/contract guidance for planner, writer, reviewer, exporter, researcher
  agents/           # BaseAgent, WriterAgent, ReviewerAgent, PromptEnhancerAgent, factory
  contracts/        # ArtifactContract, AgentContract, S-expression render, drift checks
  core/             # config, orchestrator, LLM providers, templates, sandbox, quality gate
  manifests/        # YAML manifest loading, selection evidence, fallback policy
  tools/            # DOCX renderer, LibreOffice discovery, export QA
  api_models.py     # FastAPI request/response models
  server.py         # FastAPI app and endpoints

config/
  agents.example.yaml      # starter runtime config; copy to config/agents.yaml
  document_templates.yaml  # saved document templates and prompt manifests
  artifact_manifests.yaml  # artifact routing manifests and execution overlays
  frontend_schema.json     # JSON Schema exported for UI config editing

ui/
  app/              # Next.js app router
  app/components/   # workspace, preview, FSM, profile, archive, config editor
  components/ui/    # UI primitives

docs/               # public project documentation
tests/              # pytest suite
exports/            # local generated drafts, metadata and exported artifacts
```

## Быстрый Старт

### 1. Подготовить конфиг

`config/agents.yaml` локальный и не хранится в Git. Скопируйте пример:

```powershell
Copy-Item config/agents.example.yaml config/agents.yaml
```

Linux/macOS:

```bash
cp config/agents.example.yaml config/agents.yaml
```

Пример использует `mock`, поэтому первый запуск возможен без внешних API-ключей.

### 2. Запуск через Docker Compose

```bash
docker compose up --build
```

После запуска:

- Backend API: `http://localhost:8000`
- Frontend UI: `http://localhost:3000`

PDF export зависит от LibreOffice/`soffice`. Backend Dockerfile не устанавливает LibreOffice автоматически.

### 3. Локальный запуск

Backend:

```bash
poetry install
poetry run uvicorn academic_pe.server:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd ui
pnpm install
pnpm run dev
```

Если `pnpm` не установлен:

```bash
cd ui
npm install
npm run dev
```

Также есть интерактивные лаунчеры:

```powershell
.\run.bat
```

```bash
./run.sh
```

## Конфигурация

Главный runtime-конфиг: `config/agents.yaml`.

В нем задаются:

- агенты, роли, провайдеры, модели, `temperature`, `system_prompt`;
- `self_critique`, retry и circuit breaker;
- quality gate;
- FSM states/transitions;
- стиль DOCX;
- `pipeline.sections`, `template_mode`, `template_id`, `language`, `academic_mode`;
- UI language;
- dynamic examples.

Поддерживаемые провайдеры:

```text
mock
openai
custom_openai
anthropic
google
lm_studio
zen
```

API-ключи можно задать через UI, переменные окружения или локальный `config/secrets.json`. Файл секретов игнорируется Git.

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
GOOGLE_API_KEY=...
CUSTOM_API_KEY=...
LM_STUDIO_API_KEY=...
ZEN_API_KEY=...
LIBREOFFICE_PATH=/path/to/soffice
```

Для OpenAI-compatible локальной модели:

```yaml
provider: custom_openai
base_url: "http://localhost:11434/v1"
```

Для LM Studio:

```yaml
provider: lm_studio
base_url: "http://localhost:1234/v1"
```

## Как Работает Pipeline

1. Пользователь отправляет тему, инструкции, шаблон, режим и optional continuation source через UI или `POST /api/run`.
2. Сервер загружает `config/agents.yaml`, применяет runtime overrides и создает `run_id`.
3. `TemplateSelector` выбирает структуру документа: `custom`, `fixed` или `auto`.
4. `ArtifactManifestResolver` определяет тип артефакта, execution mode, ограничения и selection evidence.
5. Contract compiler создает runtime `ArtifactContract`, agent contracts и S-expression contract block.
6. `PromptManifestResolver` добавляет template/contract guidance в системные промпты агентов.
7. Оркестратор планирует документ, пишет секции, запускает sandbox при необходимости и стримит состояние через SSE.
8. Reviewer и deterministic gates проверяют результат; при reject Writer делает line-based patch revision.
9. После успешной проверки черновик сохраняется в историю и metadata.
10. Пользователь отдельно запускает DOCX или PDF export.

Генерация и экспорт намеренно разделены. Это уменьшает лишний рендеринг, дает отдельный QA-этап для файлов и позволяет экспортировать как активный, так и архивный документ.

## API

Основные endpoints:

```text
GET  /api/config
POST /api/config

GET  /api/templates

GET  /api/examples
POST /api/examples/refresh
POST /api/prompt/enhance

POST /api/run
POST /api/cancel
GET  /api/status
GET  /api/status/stream

GET  /api/export/prerequisites
POST /api/export/docx
POST /api/export/pdf
GET  /api/download/{filename}

GET    /api/history
POST   /api/history/{metadata_id}/archive
POST   /api/history/{metadata_id}/unarchive
POST   /api/history/unarchive
DELETE /api/history/{metadata_id}

GET  /api/secrets
POST /api/secrets
GET  /api/models
POST /api/context
```

Пример запуска генерации:

```bash
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d "{\"topic\":\"State machines in document pipelines\",\"instructions\":\"Write a compact technical report.\",\"template_mode\":\"auto\"}"
```

Проверить состояние:

```bash
curl http://localhost:8000/api/status
```

Проверить доступность LibreOffice для PDF export:

```bash
curl http://localhost:8000/api/export/prerequisites
```

## Разработка

Backend tests:

```bash
poetry run pytest
```

Экспорт JSON Schema для frontend:

```bash
poetry run python scripts/export_schema.py
```

Frontend build:

```bash
cd ui
pnpm run build
```

Backend dev server:

```bash
poetry run uvicorn academic_pe.server:app --reload --host 127.0.0.1 --port 8000
```

Frontend dev server:

```bash
cd ui
pnpm run dev
```

## Текущее Состояние И Ограничения

- Это активный прототип, ориентированный на локальное использование разработчиком.
- История запусков, конфигурации агентов, артефакты и оценки полностью сохраняются в долговечной базе данных SQLite (`exports/_metadata/academic_pe_registry.sqlite3`).
- Пайплайн поддерживает параллельные и вложенные запуски пайплайнов (например, при вызовах смоук-тестов).
- PDF export требует установленный LibreOffice/`soffice`.
- Интеграция распознавания вложений (PDF OCR via Mistral API), веб-исследований (DuckDuckGo crawling/scraping) и продолжения работы (FSM merge & patch) полностью реализована и протестирована на реальных моделях.

## Документация

- [ARCHITECTURE.md](file:///f:/projects/Academic-Pipeline-Engine/docs/ARCHITECTURE.md) — архитектура backend, UI, template/manifest/contract и registry слоев.
- [ORCHESTRATION.md](file:///f:/projects/Academic-Pipeline-Engine/docs/ORCHESTRATION.md) — FSM, sequence flow, review loop, cancellation и explicit export.
- [CONFIGURATION_GUIDE.md](file:///f:/projects/Academic-Pipeline-Engine/docs/CONFIGURATION_GUIDE.md) — структура `agents.yaml`, шаблоны, провайдеры, секреты, реестр.
- [AGENTS_AND_TOOLS.md](file:///f:/projects/Academic-Pipeline-Engine/docs/AGENTS_AND_TOOLS.md) — агенты, LLM providers, sandbox, renderer, export QA.
- [MANIFEST_CONTRACT_ARCHITECTURE.md](file:///f:/projects/Academic-Pipeline-Engine/docs/MANIFEST_CONTRACT_ARCHITECTURE.md) — границы manifest/contract пакетов и non-executable DSL.
- [REGISTRY_SYSTEM.md](file:///f:/projects/Academic-Pipeline-Engine/docs/REGISTRY_SYSTEM.md) — схема БД SQLite, таблицы, миграции и API чтения реестра.
- [SMOKE_AND_QUALITY_RUNNERS.md](file:///f:/projects/Academic-Pipeline-Engine/docs/SMOKE_AND_QUALITY_RUNNERS.md) — сценарии смоук-тестов и качественной оценки, запуск и верификация.
- [CONTINUATION_AND_MERGE.md](file:///f:/projects/Academic-Pipeline-Engine/docs/CONTINUATION_AND_MERGE.md) — интент-анализ продолжения документов, Edit Plan и слияние патчами.
- [OCR_AND_RESEARCH.md](file:///f:/projects/Academic-Pipeline-Engine/docs/OCR_AND_RESEARCH.md) — краулинг веб-поиска, дедупликация и оцифровка через Mistral Document AI OCR.
- [PROJECT_STRENGTHS.md](file:///f:/projects/Academic-Pipeline-Engine/docs/PROJECT_STRENGTHS.md) — обзор сильных сторон проекта и решений для расширения кодовой базы.

## Лицензия

GPLv3. См. `LICENSE`.
