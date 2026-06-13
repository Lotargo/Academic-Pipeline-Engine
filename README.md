<div align="center">
  <img src="./assets/logo.svg" alt="Academic Pipeline Engine Logo" width="760"/>
  <br>
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Next.js-UI-black" alt="Next.js UI"/>
  <img src="https://img.shields.io/badge/Status-Active%20Prototype-orange" alt="Status"/>
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License"/>
</div>

# Academic Pipeline Engine

Academic Pipeline Engine - это рабочий прототип системы для генерации, ревью и экспорта академических, технических и свободно-структурированных документов через набор LLM-агентов.

Проект уже не похож на одиночный скрипт вокруг LLM. Внутри есть state machine, конфигурируемые агенты, шаблоны документов, manifest/contract слой для защиты от жанрового дрейфа, FastAPI-сервер, Next.js-интерфейс, история работ, экспорт в DOCX/PDF и набор автоматических проверок качества.

README промежуточный: он фиксирует текущее состояние проекта и помогает быстро войти в кодовую базу.

## Что Уже Есть

- Генерация черновика по теме и пользовательским инструкциям.
- Pipeline на состояниях `INIT -> PLANNING -> DRAFTING -> REVIEWING -> RENDERING -> DONE`.
- Агенты `writer`, `reviewer`, `planner`, `example_generator`, создаваемые из YAML-конфига.
- Поддержка провайдеров `mock`, `openai`, `custom_openai`, `anthropic`, `google`, `lm_studio`, `zen`.
- Режимы шаблонов: `custom`, `fixed`, `auto`.
- Библиотека шаблонов документов в `config/document_templates.yaml`.
- Artifact manifests в `config/artifact_manifests.yaml` для выбора типа артефакта и contract drift checks.
- Quality gate: объем секций, LaTeX-баланс, raw Markdown/code-fence артефакты.
- Явный экспорт после генерации: черновик создается отдельно, DOCX/PDF публикуются отдельным действием.
- DOCX renderer на `python-docx`, таблицы, Markdown-фрагменты, формулы и простые chart-блоки.
- Export QA: проверка структуры DOCX, безопасное имя файла, PDF-конвертация через LibreOffice при наличии.
- FastAPI API с SSE-статусом пайплайна.
- Next.js UI: live preview, FSM monitor, консоль логов, конфиг-редактор, история, архив, профиль, продолжение прошлой работы.
- Тесты для оркестратора, агентов, контрактов, манифестов, шаблонов, export QA, sandbox и API-контракта.

## Структура

```text
academic_pe/
  agents/        # BaseAgent, WriterAgent, ReviewerAgent, AgentFactory
  contracts/     # Artifact contracts, S-expression render, drift checks
  core/          # config, orchestrator, LLM providers, templates, sandbox, quality gate
  manifests/     # artifact manifest loading/resolution
  tools/         # DOCX renderer, LibreOffice discovery, export QA
  server.py      # FastAPI app and API endpoints

config/
  agents.example.yaml      # пример локального конфига агентов
  document_templates.yaml  # сохраненные шаблоны документов
  artifact_manifests.yaml  # правила выбора типа артефакта
  frontend_schema.json     # JSON Schema для UI

ui/
  app/            # Next.js app router
  app/components/ # рабочий интерфейс, preview, FSM, config editor, sidebar
  components/ui/  # shadcn/radix UI primitives

tests/            # pytest suite
docs/             # техническая документация
dev_docs/         # рабочие заметки и roadmap/sprint-документы
exports/          # локальные результаты генерации и metadata
```

## Быстрый Старт

### 1. Подготовить конфиг

`config/agents.yaml` игнорируется Git, потому что это локальная рабочая конфигурация.

```powershell
Copy-Item config/agents.example.yaml config/agents.yaml
```

На Linux/macOS:

```bash
cp config/agents.example.yaml config/agents.yaml
```

По умолчанию пример использует `mock`, поэтому проект можно поднять без API-ключей.

### 2. Запуск через Docker Compose

```bash
docker compose up --build
```

После запуска:

- Backend API: `http://localhost:8000`
- Frontend UI: `http://localhost:3000`

Примечание: PDF export и визуальная проверка зависят от LibreOffice/`soffice`. Текущий backend Dockerfile не устанавливает LibreOffice автоматически.

### 3. Локальный запуск

Backend:

```bash
poetry install
poetry run uvicorn academic_pe.server:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd ui
pnpm install
pnpm run dev
```

Если `pnpm` не установлен, для разработки обычно сработает:

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

## Конфигурация И Секреты

Главный runtime-конфиг: `config/agents.yaml`.

В нем задаются:

- роли и системные промпты агентов;
- LLM-провайдеры, модели, `temperature`;
- retry и circuit breaker;
- quality gate;
- секции документа;
- режим шаблонов;
- язык интерфейса и генерации;
- директория экспорта.

API-ключи можно задать через UI или переменные окружения. Локальный файл `config/secrets.json` игнорируется Git.

Поддерживаемые переменные:

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

Для локальной OpenAI-compatible модели можно использовать:

```yaml
provider: custom_openai
base_url: "http://localhost:11434/v1"
```

или:

```yaml
provider: lm_studio
base_url: "http://localhost:1234/v1"
```

## Как Работает Pipeline

1. Пользователь отправляет тему и инструкции через UI или `POST /api/run`.
2. Сервер загружает `config/agents.yaml`.
3. Template selector выбирает структуру документа:
   - `custom` - секции из `agents.yaml`;
   - `fixed` - шаблон из `config/document_templates.yaml`;
   - `auto` - временный runtime-шаблон от PlannerAgent.
4. Artifact manifest resolver определяет тип артефакта и contract constraints.
5. Orchestrator строит план документа.
6. WriterAgent генерирует секции с учетом плана, предыдущих секций и continuation source.
7. ReviewerAgent принимает или отклоняет документ.
8. При `REJECTED` writer делает targeted revision.
9. Quality gate и contract drift checks блокируют плохой результат до экспорта.
10. Черновик сохраняется в историю.
11. Пользователь явно запускает DOCX/PDF export.

Важно: генерация черновика и экспорт разделены. Это сделано специально, чтобы не создавать DOCX на каждый прогон и дать экспорту отдельный QA-этап.

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
  -d "{\"topic\":\"State machines in document pipelines\",\"instructions\":\"Write a compact technical report.\"}"
```

Проверить состояние:

```bash
curl http://localhost:8000/api/status
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

Backend entrypoint:

```bash
poetry run uvicorn academic_pe.server:app --reload --host 127.0.0.1 --port 8000
```

Frontend dev server:

```bash
cd ui
pnpm run dev
```

## Текущее Состояние И Ограничения

- Это активный прототип, а не стабильный публичный SDK.
- `docs/` частично отстают от кода и еще содержат старые упоминания `src/`.
- `config/agents.yaml` и `config/secrets.json` локальные и не должны попадать в Git.
- PDF export требует установленный LibreOffice/`soffice`.
- Визуальная QA заявлена как направление, но фактическая глубина проверки зависит от доступности LibreOffice и возможностей reviewer-модели.
- `ui/package.json` пока называется `my-v0-project`, это стоит переименовать перед публичным релизом.
- В frontend build включено `typescript.ignoreBuildErrors`, так что TypeScript-долг лучше отдельно закрыть перед стабилизацией.
- Слой хранения истории пока файловый: JSON metadata под `exports/_metadata`.

## Полезные Документы

- `docs/ARCHITECTURE.md` - архитектурный обзор.
- `docs/ORCHESTRATION.md` - состояние pipeline и переходы.
- `docs/CONFIGURATION_GUIDE.md` - конфиг агентов и секций.
- `docs/AGENTS_AND_TOOLS.md` - агенты и инструменты.
- `dev_docs/REFACTORING_MAP.md` - карта выполненного и оставшегося рефакторинга.
- `dev_docs/DOCUMENT_EXPORT_AND_AGENT_TOOLS.md` - направление по export QA и constrained document tools.
- `dev_docs/FRONTEND_UX_SPRINT.md` - недавний frontend UX sprint.

## Лицензия

MIT. См. `LICENSE`.
