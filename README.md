<div align="center">
  <img src="./assets/logo.svg" alt="Academic Pipeline Engine Logo" width="760"/>
  <br>
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Next.js-UI-black" alt="Next.js UI"/>
  <img src="https://img.shields.io/badge/Status-Active%20Prototype-orange" alt="Status"/>
  <img src="https://img.shields.io/badge/License-AGPLv3-blue" alt="License"/>
</div>

# Academic Pipeline Engine

**Academic Pipeline Engine** - локальный агентный workspace для подготовки, ревью, продолжения и экспорта структурированных документов. Это не просто генератор академических статей: система определяет тип артефакта, компилирует пользовательский замысел в runtime contract, ведет секционный LLM-pipeline, проверяет результат и отдельно экспортирует готовый черновик в DOCX/PDF.

Проект объединяет FastAPI backend, Next.js интерфейс, FSM-оркестратор, конфигурируемых агентов, шаблоны, manifests, contracts, quality gates, OCR/web research, SQLite-историю и export QA.

> Для GitHub Pages уже подготовлена кастомная статическая страница: [`docs/index.html`](./docs/index.html). В настройках репозитория можно включить Pages из папки `docs/`.

## Зачем Это Нужно

Большинство генераторов документов сводят разные задачи к одному усредненному режиму письма. Стихотворение, школьное эссе, технический README, отчет и academic paper не должны проходить через одни и те же предположения. APE держит эти границы явными.

- **Artifact-first routing** сохраняет жанр, аудиторию, структуру и запреты для конкретного типа работы.
- **Runtime contracts** превращают prompt в проверяемые constraints до того, как агенты начинают писать.
- **Writer/Reviewer loop** объединяет LLM-ревью и deterministic quality gates.
- **Continuation mode** умеет дописывать, связывать или точечно пересобирать прошлые работы.
- **Explicit export** отделяет генерацию черновика от DOCX/PDF-рендеринга и QA.
- **Mock mode** позволяет поднять проект локально без внешних API-ключей.

## Возможности

- Генерация черновиков по теме, инструкциям, шаблону и режиму исполнения.
- Режимы шаблонов `custom`, `fixed`, `auto`.
- Artifact routing для poem, story, school essay, academic paper, technical README, plan, report, continuation и freeform fallback.
- Manifest/contract слой с S-expression guidance для агентов.
- Prompt enhancement через `/api/prompt/enhance` с сохранением artifact metadata.
- FSM pipeline `INIT -> PLANNING -> DRAFTING -> REVIEWING -> RENDERING -> DONE`.
- Line-based patch revision после rejection от Reviewer или deterministic gates.
- Academic sandbox для `python-run` блоков с `pandas`, `sympy`, `scipy` и `matplotlib`.
- OCR и web research с leakage barrier между сырыми источниками и Writer.
- SQLite registry для истории запусков, конфигов, шаблонов, sources, evaluations и event logs.
- DOCX export через `python-docx`, PDF export через LibreOffice/`soffice`.
- Next.js UI: live preview, FSM monitor, SSE-статусы, консоль, config editor, history, archive, profile и continuation controls.

## Архитектура В Одном Взгляде

```text
User brief
  -> TemplateSelector
  -> ArtifactManifestResolver
  -> Contract compiler
  -> PromptManifestResolver
  -> Orchestrator FSM
  -> Writer / Reviewer / deterministic gates
  -> Registry metadata
  -> Explicit DOCX/PDF export
```

```text
academic_pe/
  agent_adapters/   # role-specific contract guidance
  agents/           # Writer, Reviewer, PromptEnhancer and factory
  contracts/        # runtime contracts, S-expression render, drift checks
  core/             # config, orchestration, templates, sandbox, registry
  manifests/        # manifest loading, resolver and fallback policy
  tools/            # DOCX renderer, LibreOffice discovery, export QA
  server.py         # FastAPI app and endpoints

config/             # agents, templates, manifests and frontend schema
docs/               # GitHub Pages site and technical documentation
ui/                 # Next.js workspace
tests/              # pytest suite
exports/            # local drafts, metadata and exported artifacts
```

## Быстрый Старт

`config/agents.yaml` локальный и не хранится в Git. Начните с примера:

```powershell
Copy-Item config/agents.example.yaml config/agents.yaml
```

Linux/macOS:

```bash
cp config/agents.example.yaml config/agents.yaml
```

Пример использует provider `mock`, поэтому первый запуск возможен без внешних API-ключей.

### Docker Compose

```bash
docker compose up --build
```

После запуска:

- Backend API: `http://localhost:8000`
- Frontend UI: `http://localhost:3000`

PDF export требует LibreOffice/`soffice`. Backend Dockerfile не устанавливает LibreOffice автоматически.

### Локальная Разработка

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

Если `pnpm` недоступен:

```bash
cd ui
npm install
npm run dev
```

Скрипты запуска разделяют режимы явно. По умолчанию запускается
многопользовательский `service-dev`: он поднимает официальный локальный
Supabase CLI/Docker stack, генерирует ignored `.env.service-dev`, применяет
Alembic migrations в Supabase PostgreSQL и запускает APE API/frontend в
отдельном Docker Compose.

Для стабильной совместимости Docker Desktop/WSL этот development profile не
запускает optional Supabase Logflare/Analytics и Vector logging: они не требуются
для Auth/Postgres/Storage, а Vector ожидает доступ к Docker socket. Это не
относится к production observability APE.

```powershell
.\run.bat
# или явно:
.\run-service-dev.bat
```

```bash
./run.sh
# или явно:
./run-service-dev.sh
```

Проверить состояние или остановить обе локальные композиции можно тем же
скриптом:

```bash
./run-service-dev.sh status
./run-service-dev.sh down
```

```powershell
.\run-service-dev.bat status
.\run-service-dev.bat down
```

Для WSL рекомендуется держать рабочую копию на Linux filesystem (например,
`~/projects/Academic-Pipeline-Engine`), а не в `/mnt/c` или `/mnt/f`: Docker
build context с Windows-mounted диска заметно медленнее. Скрипты остаются
одинаковыми в WSL и PowerShell.

Этот контур запускает Supabase Postgres/Auth/Storage, но до `BE-13` API ещё
использует временную legacy JWT compatibility boundary. Реальные Supabase
sessions и OAuth providers не считаются готовыми; provider secrets и публичные
redirect URLs не добавляются в локальный файл.

Для прежнего автономного режима без аккаунтов, jobs API и service auth:

```powershell
.\run-local.bat
```

```bash
./run-local.sh
```

Не используйте `run-local` для проверки login, cabinet или history service UI:
в этом режиме `/api/auth/*` намеренно не монтируются.

## Конфигурация

Главный runtime-конфиг: `config/agents.yaml`. В нем задаются агенты, providers, модели, temperature, self-critique, retries, quality gates, FSM transitions, DOCX styles, pipeline sections, template mode, language, academic mode, UI language и dynamic examples.

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

API-ключи можно передать через UI, переменные окружения или локальный `config/secrets.json`:

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

## API

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
GET  /api/history
POST /api/history/{metadata_id}/archive
POST /api/history/{metadata_id}/unarchive
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

Проверить статус:

```bash
curl http://localhost:8000/api/status
```

Проверить готовность PDF export:

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

## Документация

- [Architecture](./docs/ARCHITECTURE.md)
- [Orchestration](./docs/ORCHESTRATION.md)
- [Configuration Guide](./docs/CONFIGURATION_GUIDE.md)
- [Project Capabilities](./docs/PROJECT_CAPABILITIES.md)
- [Usage Guide](./docs/USAGE_GUIDE.md)
- [Agents and Tools](./docs/AGENTS_AND_TOOLS.md)
- [Manifest Contract Architecture](./docs/MANIFEST_CONTRACT_ARCHITECTURE.md)
- [Registry System](./docs/REGISTRY_SYSTEM.md)
- [Smoke and Quality Runners](./docs/SMOKE_AND_QUALITY_RUNNERS.md)
- [Continuation and Merge](./docs/CONTINUATION_AND_MERGE.md)
- [OCR and Research](./docs/OCR_AND_RESEARCH.md)

## Текущее Состояние

APE - активный прототип для локального developer use. Уже реализованы основной pipeline, UI, registry, export flow, OCR/research path и тесты для ключевых слоев: contracts, manifests, agents, orchestration, registry и export behavior.

## Лицензия

AGPLv3. См. [LICENSE](./LICENSE).
