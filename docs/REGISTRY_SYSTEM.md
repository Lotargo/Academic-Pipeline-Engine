# Система Реестра SQLite (SQLite Registry System)

Система реестра в **Academic Pipeline Engine** является единым источником правды для хранения метаданных, связанных с ходом работы пайплайна, конфигурациями агентов, полученными артефактами и результатами проверок качества.

## Архитектура

Реестр построен на базе **SQLite** и располагается по локальному пути `exports/_metadata/academic_pe_registry.sqlite3`. Файловая система используется как хранилище больших блобов (сгенерированных DOCX, PDF, логов поиска и вложений), в то время как база данных SQLite управляет структурированными отношениями, статусами и индексами.

Компонент доступа к БД — [`sqlite_store.py`](../academic_pe/core/registry/sqlite_store.py) — использует контекстное управление соединениями (`connection context manager`), чтобы открывать соединение на короткий промежуток времени и сразу же закрывать его. Это предотвращает блокировки файлов (`database is locked`), типичные для Windows при многопоточном доступе.

## Схема Базы Данных

Реестр состоит из 8 взаимосвязанных таблиц, миграциями которых управляет модуль [`migrations.py`](../academic_pe/core/registry/migrations.py):

```mermaid
erDiagram
    runs ||--o{ run_agents : "has"
    runs ||--o{ artifacts : "produces"
    runs ||--o{ runtime_snapshots : "snapshots"
    runs ||--o{ sections : "drafts"
    runs ||--o{ sources : "references"
    runs ||--o{ evaluations : "evaluates"
    runs ||--o{ events : "logs"

    runs {
        integer id PK
        string run_id UNIQUE
        string kind
        string status
        string topic
        string instructions_preview
        string pipeline_mode
        integer web_search_enabled
        string created_at
        string started_at
        string finished_at
        string output_dir
        string error_type
        string error_message
        string metadata_json
    }

    run_agents {
        integer id PK
        string run_id FK
        string role
        string provider
        string model
        float temperature
        string agent_type
        integer self_critique_enabled
        string metadata_json
    }

    artifacts {
        integer id PK
        string run_id FK
        string artifact_type
        string path
        string relative_path
        string filename
        string mime_type
        integer size_bytes
        string sha256
        string created_at
        integer is_diagnostic
        string metadata_json
    }

    runtime_snapshots {
        integer id PK
        string run_id FK
        string snapshot_type
        string version
        string fingerprint
        string metadata_json
    }

    sections {
        integer id PK
        string run_id FK
        string name
        string title
        string semantic_role
        string heading_policy
        integer char_count
        integer order_index
        string content_path
        string content_sha256
        string metadata_json
    }

    sources {
        integer id PK
        string run_id FK
        string source_type
        string title
        string url
        string path
        string sha256
        string used_by
        string metadata_json
    }

    evaluations {
        integer id PK
        string run_id FK
        string eval_type
        string status
        string summary
        string result_path
        string metadata_json
        string created_at
    }

    events {
        integer id PK
        string run_id FK
        string event_type
        string stage
        string message
        string created_at
        string metadata_json
    }
```

### Назначение таблиц

1. **`runs`**: Основная информация о запуске (тип `generation` или `smoke`/`quality`, текущий статус `running`/`succeeded`/`failed`, ошибки, если есть). `metadata_json` хранит дополнительные свойства (автор, архивные флаги, настройки режимов).
2. **`run_agents`**: Снимок конфигураций всех участвовавших агентов (их провайдер, модель, температура, настройки критики).
3. **`artifacts`**: Файлы, сгенерированные пайплайном (DOCX-экспорты, PDF-файлы, скриншоты-превью, диагностические логи).
4. **`runtime_snapshots`**: Состояние шаблонов (`runtime_template`) и манифестов промптов (`runtime_prompt_manifest`) на момент запуска пайплайна.
5. **`sections`**: Срезы созданных секций документа (количество символов, контрольная сумма контента, очередность).
6. **`sources`**: Все задействованные источники информации (загруженные продолжения, справочные PDF/DOCX, а также страницы, найденные краулером при веб-поиске).
7. **`evaluations`**: Результаты автоматических проверок (Quality Gate, дрейф контракта) и ручных проверок качества (Quality/Smoke Runner).
8. **`events`**: Журнал переходов по состояниям пайплайна FSM (`stage_transition`, `agent_call_start`, `agent_call_end`).

## Импорт старых данных (Legacy JSON Importer)

На старте API-сервера запускается импортер [`importers.py`](../academic_pe/core/registry/importers.py). Он сканирует папку `exports/_metadata` на наличие старых файлов `.metadata.json`, парсит их и импортирует в SQLite, создавая связанные записи для запусков, агентов, артефактов и снэпшотов.

## API Чтения (Read Model)

Реестр предоставляет REST API эндпоинты для фронтенда:

- **`GET /api/registry/runs`**: Возвращает пагинированный список запусков. Поддерживает фильтрацию по:
  - `status`: статус (`succeeded`, `failed`, `running`);
  - `kind`: тип запуска (`generation`, `smoke`, `quality`);
  - `pipeline_mode`: режим пайплайна (`standard`, `continuation`, `research`);
  - `template_id`: ID используемого шаблона документа;
  - `artifact_type`: фильтрация по сгенерированному файлу (например, только `pdf`);
  - `created_date`: по дате создания (`YYYY-MM-DD` или префикс месяца `YYYY-MM`).
- **`GET /api/registry/runs/{run_id}`**: Детальный инспект запуска, собирающий полную реляционную модель воедино.
- **`GET /api/history`**: Обновлённый эндпоинт, который читает из SQLite, преобразуя данные в совместимый с фронтендом формат (используя `.metadata.json` файлы как резервный fallback при отсутствии БД).
