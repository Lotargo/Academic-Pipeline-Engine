# Academic Pipeline Engine — Development Plan, Part 2

## Статус документа

Этот каталог описывает переход Academic Pipeline Engine от локального однопользовательского приложения к бесплатному многопользовательскому сервису.

Документ является архитектурным планом верхнего уровня. Он **не является TODO-листом** и не разрешает начинать реализацию отдельных компонентов без последующей декомпозиции.

Для каждой композиции, выделенной в этом плане, позднее должен быть создан отдельный документ с собственным TODO-листом, критериями готовности, тестами и порядком миграции.

Этот файл обязаны прочитать разработчики и агенты перед любой работой, относящейся к `dev_docs_part_2`.

---

# 1. Обязательная граница релиза

## Release gate

- [ ] **LOCAL-FIRST RELEASE GATE COMPLETE**

Поля заполняются один раз после проверки или создания релиза:

```text
Release tag: NOT SET
Release title: NOT SET
Release URL: NOT SET
Boundary commit: 9bb555a9465a9c0906455c5a8b1a6bb4004c88dd
Release date: NOT SET
Verified by: NOT SET
```

## Правило для агентов и разработчиков

Перед первым изменением кода по Part 2 необходимо открыть этот документ и проверить только чекбокс выше.

Если чекбокс уже отмечен:

- не нужно повторно проверять GitHub Releases и tags;
- не нужно создавать ещё один local-first релиз;
- следует считать указанную release boundary подтверждённой;
- можно переходить к документу конкретной композиции и её TODO-листу.

Если чекбокс не отмечен:

1. Один раз проверить, существует ли уже релиз, фиксирующий текущую local-first версию.
2. Если эквивалентный релиз уже существует, заполнить поля выше и отметить чекбокс.
3. Если релиза нет, создать его от boundary commit, указанного выше.
4. После создания релиза заполнить поля и отметить чекбокс.
5. Только после этого разрешается начинать реализацию Part 2.

Документационные изменения внутри `dev_docs_part_2` могут находиться после boundary commit. Сам релиз должен фиксировать последнюю рабочую local-first версию до начала архитектурной миграции.

## Рекомендуемая идентификация релиза

```text
Tag: v0.1.0-local-first
Title: Academic Pipeline Engine v0.1.0 — Local First
Target commit: 9bb555a9465a9c0906455c5a8b1a6bb4004c88dd
```

Если аналогичный релиз уже существует под другим корректным именем, дублировать его не нужно.

## Назначение релиза

Local-first релиз должен стать неизменяемой точкой разделения между двумя поколениями проекта:

```text
До релиза
└── локальный однопользовательский workspace

После релиза
└── многопользовательская облачная архитектура Part 2
```

Эта граница нужна для:

- безопасного возврата к рабочей локальной версии;
- разделения изменений архитектуры хранения и исполнения;
- сохранения понятной истории проекта;
- фиксации лицензии local-first версии;
- возможной будущей смены лицензии без смешивания старой и новой кодовой базы;
- корректного сравнения поведения до и после миграции.

Релиз создаётся **один раз**, а не перед каждой композицией Part 2.

---

# 2. Цель Part 2

Part 2 превращает Academic Pipeline Engine в бесплатный многопользовательский сервис с облачным хранением, очередями задач, отдельным пользовательским кабинетом и административной панелью.

Основные свойства целевой системы:

- весь основной функционал остаётся бесплатным;
- платных статусов, подписок и пользовательских привилегий нет;
- общие OCR- и AI-ресурсы предоставляются в пределах доступных глобальных лимитов проекта;
- когда общий ресурс недоступен или исчерпан, пользователь может подключить собственный API-ключ поддерживаемого провайдера;
- пользовательские и системные ключи хранятся в профессиональном зашифрованном хранилище секретов;
- длительные pipeline-задачи выполняются background workers через очередь;
- состояние работы не зависит от памяти одного FastAPI-процесса;
- данные пользователей разделены на уровне приложения и базы данных;
- frontend, API и workers являются отдельными зонами ответственности;
- Docker остаётся основным способом сборки и развёртывания.

---

# 3. Базовые продуктовые решения

## 3.1 Бесплатная модель

В Part 2 не вводятся:

- тарифы Free/Paid;
- платные подписки;
- платные лимиты;
- приоритет за оплату;
- специальные модели за оплату;
- дополнительные возможности за пожертвование;
- entitlements, связанные с переводами денег.

Все функции доступны на одинаковых условиях. Ограничение возникает только из-за доступности общих вычислительных ресурсов или правил защиты сервиса от злоупотребления.

## 3.2 Общие ресурсы проекта

Проект может использовать:

- бесплатные или спонсируемые ключи OpenCode и других AI-провайдеров;
- общий бесплатный ключ Mistral для OCR;
- другие общие провайдеры, добавленные администратором.

Для Mistral и провайдеров с понятными квотами допускается учёт глобального бюджета.

Для OpenCode и провайдеров с непрозрачными лимитами не нужно имитировать точный остаток токенов. Их состояние определяется как доступность сервиса:

```text
unknown
available
degraded
exhausted
disabled
```

Система должна использовать circuit breaker, cooldown и пробные запросы, а не выдуманный точный счётчик квоты.

## 3.3 BYOK

Пользователь может добавить собственный ключ любого поддерживаемого провайдера.

Собственный ключ может использоваться:

- по явному выбору пользователя;
- как fallback после исчерпания общего ресурса;
- для конфиденциальных документов;
- для провайдеров или моделей, которых нет в общем пуле;
- для продолжения работы без ожидания восстановления общего лимита.

Пользовательские ключи не должны храниться в `localStorage` как основная архитектура Part 2. Они сохраняются в серверном хранилище секретов в зашифрованном виде.

## 3.4 Добровольная поддержка

Проект может иметь отдельную страницу добровольной поддержки через СБП.

Предлагаемые кнопки:

```text
150 ₽
500 ₽
1000 ₽
5000 ₽
Другая сумма
```

Поддержка:

- не связывается с аккаунтом;
- не меняет лимиты;
- не даёт приоритет;
- не открывает функции;
- не создаёт платный статус;
- не требует billing-подсистемы внутри APE;
- не должна использоваться как скрытая продажа доступа.

Рядом должна быть отдельная ссылка на публичный Telegram автора для:

- коммерческих предложений;
- интеграций;
- сотрудничества;
- заказа похожих решений;
- обсуждения отдельных доработок.

Эта ссылка является каналом связи и рекламным элементом, а не предложением выкупить проект.

---

# 4. Целевая архитектура

```text
Browser
│
├── Public pages
│   ├── registration
│   ├── login
│   ├── project information
│   └── voluntary support
│
├── User application
│   ├── workspace
│   ├── jobs
│   ├── history
│   ├── artifacts
│   └── provider settings
│
└── Admin application
    ├── users
    ├── roles
    ├── providers
    ├── platform keys
    ├── limits
    ├── jobs
    ├── audit
    └── system health

                    HTTPS / JWT
                         │
                         ▼
                    FastAPI API
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     PostgreSQL       RabbitMQ      Object Storage
          │              │              │
          │              ▼              │
          │         Celery workers      │
          │              │              │
          └──────────────┴──────────────┘
                         │
                         ▼
                AI / OCR providers
```

Предпочтительная первая cloud-композиция:

```text
Frontend:           Render или Vercel
API:                Render Docker Web Service
Workers:            Render Background Workers
Queue:              RabbitMQ
Database:           Supabase PostgreSQL
Auth:               Supabase Auth или собственный JWT-слой поверх PostgreSQL
Object storage:     Supabase Storage
Secret storage:     Supabase Vault на первой версии
```

Альтернативная композиция:

```text
Neon PostgreSQL
+ отдельный Auth
+ Cloudflare R2 / S3
+ HashiCorp Vault Transit или managed KMS
```

Выбор Supabase или Neon должен быть окончательно зафиксирован в отдельной композиции до начала миграции persistence-слоя.

---

# 5. Разделение frontend и backend

Работы по frontend и backend не должны смешиваться в одном неструктурированном TODO-листе.

После декомпозиции должны появиться независимые документы минимум для двух основных потоков:

```text
dev_docs_part_2/
├── README.md
├── frontend/
│   └── отдельные планы и TODO
└── backend/
    └── отдельные планы и TODO
```

Этот каталог пока не создаёт TODO-файлы. Он только фиксирует обязательное разделение ответственности.

## 5.1 Frontend workstream

Frontend отвечает за пользовательские интерфейсы и клиентские состояния, но не реализует серверные правила безопасности.

Основные области frontend:

### Public/Auth

- отдельная страница регистрации;
- отдельная страница входа;
- восстановление доступа;
- подтверждение регистрации при необходимости;
- публичная информация о бесплатной модели;
- страница добровольной поддержки;
- ссылка на публичный Telegram для коммерческих предложений.

Предполагаемые маршруты:

```text
/register
/login
/support
/app
/admin
```

### User cabinet

- профиль пользователя;
- рабочие пространства;
- создание задания;
- просмотр статуса и этапов pipeline;
- история генераций;
- загрузки и экспортированные документы;
- настройка AI- и OCR-провайдеров;
- добавление, замена, проверка и удаление собственных ключей;
- выбор между общим провайдером и BYOK;
- понятное сообщение об исчерпании общего ресурса;
- отображение состояния провайдера без выдуманного точного остатка квоты.

### Admin panel

- отдельный защищённый layout;
- управление пользователями и ролями;
- блокировка и разблокировка аккаунтов;
- управление общими provider credentials;
- управление разрешёнными моделями;
- управление глобальными лимитами;
- просмотр состояния очередей и workers;
- просмотр активных, зависших и завершённых jobs;
- просмотр usage и ошибок провайдеров;
- audit log;
- health dashboard.

Frontend не должен получать plaintext сохранённых API-ключей, включая административные ключи.

## 5.2 Backend workstream

Backend отвечает за бизнес-правила, авторизацию, persistence, очереди, workers, секреты и взаимодействие с провайдерами.

Основные области backend:

### API

- FastAPI HTTP API;
- JWT-аутентификация;
- refresh sessions;
- RBAC;
- user, workspace и admin endpoints;
- job creation и job status;
- signed artifact access;
- provider configuration;
- global resource status;
- audit logging.

### Worker layer

- generation worker;
- export worker;
- OCR/research worker;
- maintenance worker;
- retry policy;
- cancellation;
- heartbeat;
- interrupted job recovery;
- checkpointing по этапам pipeline.

### Persistence

- PostgreSQL вместо SQLite как production source of truth;
- object storage вместо постоянных локальных файлов;
- локальные временные файлы только внутри `/tmp`;
- stateless API и worker containers;
- отдельные repository interfaces;
- возможность сохранить SQLite adapter для local-first режима и тестов.

### Security

- secret encryption;
- ограничение decrypt permission;
- разделение API и worker credentials;
- защита административных endpoints;
- RLS или эквивалентная tenant isolation;
- audit trail;
- защита от утечки ключей в логах и telemetry.

---

# 6. Данные и многопользовательская модель

Минимальная модель должна учитывать не только пользователя, но и workspace.

Даже если первая версия создаёт каждому пользователю один personal workspace, прикладные данные должны быть привязаны к `workspace_id`.

Основные сущности:

```text
users
user_sessions
roles
user_roles
organizations
organization_members
workspaces
workspace_members

jobs
job_stages
job_sections
job_events
job_checkpoints
job_attempts

artifacts
uploads
sources
evaluations

provider_definitions
provider_models
platform_provider_credentials
user_provider_credentials
provider_health
provider_budgets
usage_events

admin_invites
audit_log
outbox_events
```

Не создаются как часть текущей модели:

```text
paid_plans
subscriptions
paid_entitlements
payment_privileges
```

## Tenant isolation

Каждая пользовательская сущность должна иметь явную принадлежность:

```text
workspace_id
created_by
```

Доступ проверяется на нескольких уровнях:

- API authorization;
- repository/application service;
- PostgreSQL permissions или RLS;
- object storage policies;
- signed download URLs.

Администратор получает расширенные права через отдельную роль, а не через отключение всех проверок внутри пользовательского API.

---

# 7. ORM и миграции

Для production PostgreSQL используется:

```text
SQLAlchemy 2.x
Alembic
psycopg 3
Pydantic 2
Repository pattern
Unit of Work
```

ORM-модели, API-схемы и domain-модели не должны быть одним классом.

```text
SQLAlchemy models
    persistence

Pydantic schemas
    API contracts

Domain entities/services
    business rules
```

Raw SQL или SQLAlchemy Core допускается для:

- `SELECT FOR UPDATE`;
- `SKIP LOCKED`;
- атомарного резервирования ресурсов;
- outbox dispatcher;
- advisory locks;
- массовых операций;
- сложной usage-аналитики;
- RLS policies.

OGM и отдельная графовая база в Part 2 не требуются.

---

# 8. Очереди и workers

Основной брокер Part 2:

```text
RabbitMQ
```

Основной task layer:

```text
Celery
```

Kafka не включается в первую архитектуру, потому что APE работает прежде всего с длительными заданиями, а не с высоконагруженным event stream и replay несколькими consumer groups.

Предварительное разделение очередей:

```text
pipeline.generate
pipeline.export
research.ocr
research.web
maintenance
```

В RabbitMQ передаются только identifiers и безопасная metadata:

```json
{
  "job_id": "...",
  "workspace_id": "...",
  "credential_id": "...",
  "provider": "...",
  "model": "..."
}
```

В очередь запрещено помещать:

- plaintext API keys;
- JWT пользователей;
- refresh tokens;
- полное содержимое приватных документов без отдельной необходимости;
- данные, которые должны загружаться worker из PostgreSQL или object storage.

## Outbox

Создание job и публикация сообщения не должны зависеть от двух несвязанных успешных операций.

Используется transactional outbox:

```text
DB transaction
├── create job
├── reserve resource if needed
└── create outbox event

Outbox dispatcher
├── publish to RabbitMQ
└── mark event as published
```

Workers должны быть идемпотентными и уметь безопасно обрабатывать повторную доставку.

---

# 9. Управление общими ресурсами

Part 2 не вводит искусственные персональные токеновые тарифы.

Система управляет:

- глобальной доступностью platform providers;
- известными глобальными квотами;
- очередью заданий;
- конкурентной нагрузкой;
- защитой от полного захвата ресурса одним пользователем;
- fallback на пользовательский ключ.

Для первой версии допустимы технические ограничения справедливости, не связанные с оплатой:

```text
ограничение числа одновременно выполняемых jobs;
ограничение числа ожидающих jobs;
ограничение размера одной загрузки;
ограничение числа OCR-страниц в одной задаче;
rate limiting против автоматического злоупотребления.
```

Это эксплуатационные ограничения общего бесплатного ресурса, а не тарифы.

## Provider resolution

Предварительное правило выбора credentials:

```text
1. Пользователь явно выбрал собственный ключ
   → использовать user credential.

2. Иначе доступен общий provider
   → использовать platform credential.

3. Общий provider exhausted/degraded
   → попробовать настроенный fallback.

4. Общие ресурсы недоступны
   → предложить добавить собственный ключ.
```

Система не должна обходить upstream-лимиты путём постоянного создания новых виртуальных машин или ротации окружений.

---

# 10. Хранилище секретов

Пользовательские и системные ключи сохраняются в специализированном зашифрованном хранилище.

Минимальные криптографические требования:

```text
AEAD: AES-256-GCM
или: ChaCha20-Poly1305 / XChaCha20-Poly1305 через проверенную библиотеку

Architecture: envelope encryption
Fingerprint: HMAC-SHA-256 с отдельным fingerprint secret
```

SHA-256 не используется как замена шифрованию.

ML-KEM и X25519 могут рассматриваться позднее как transport/key-establishment слой, но не заменяют AEAD-шифрование секретов at rest.

## Envelope encryption

```text
KEK
└── хранится в Vault/KMS

DEK
├── генерируется для секрета или ограниченной группы секретов
├── шифрует API key через AEAD
└── сам хранится только в wrapped form
```

В PostgreSQL допускается хранить:

```text
ciphertext
nonce
wrapped_dek
algorithm
key_version
fingerprint
provider
owner_id
metadata
```

В PostgreSQL, RabbitMQ, логах и frontend responses запрещено хранить или возвращать plaintext ключа.

## Доступ к расшифровке

```text
Frontend
└── не получает сохранённый plaintext

API service
└── принимает новый ключ и передаёт его на шифрование

Scheduler / RabbitMQ
└── видит только credential_id

Generation/OCR worker
└── получает право кратковременно расшифровать нужный ключ

Admin UI
└── видит только provider, owner, status, label и masked metadata
```

Первая реализация может использовать Supabase Vault. При отдельном PostgreSQL рассматривается HashiCorp Vault Transit или managed KMS.

---

# 11. Auth и административный доступ

## Пользовательская авторизация

Система должна иметь:

- регистрацию;
- вход;
- refresh session;
- logout/revocation;
- роли;
- привязку пользователя к workspace;
- защиту пользовательских и административных endpoints.

## JWT

JWT используется для авторизованной сессии после входа.

JWT не является кодом регистрации администратора.

Рекомендуемая модель:

```text
short-lived access JWT
+ rotated refresh session
+ session revocation
+ token version
```

## Отдельный admin bootstrap micro-project

Создание первых и последующих администраторов должно быть вынесено в отдельный малый проект или отдельную deployment-композицию.

Его назначение:

- bootstrap первого администратора;
- выпуск одноразового admin invite token;
- ограничение срока действия invite;
- хранение только hash invite token;
- пометка invite как использованного;
- отсутствие постоянной публичной регистрации администраторов.

Предпочтительная форма:

```text
CLI / one-off job / временно запускаемый admin-bootstrap service
```

Он не должен постоянно выдавать access JWT и не должен быть открытым публичным endpoint без дополнительной защиты.

После активации администратор входит через обычную auth-систему и получает JWT с административной ролью.

---

# 12. Object storage и артефакты

Постоянные файлы не должны зависеть от файловой системы Render container.

В object storage переносятся:

- пользовательские uploads;
- DOCX;
- PDF;
- графики;
- экспортные отчёты;
- при необходимости крупные промежуточные данные.

В PostgreSQL хранится metadata:

```text
artifact_id
workspace_id
job_id
storage_provider
storage_key
filename
mime_type
size_bytes
checksum
created_at
```

Worker может создавать временный файл:

```text
/tmp/ape/<job_id>/...
```

После успешной загрузки в object storage временный файл удаляется.

Доступ к приватным артефактам выполняется через проверку membership и signed URL с ограниченным сроком жизни.

---

# 13. Docker и deployment

Docker является основным способом сборки production-компонентов.

Предполагаемые процессы:

```text
frontend
api
generation-worker
export-worker
research-worker
maintenance-worker
```

API и workers могут использовать один backend image с разными командами запуска.

Контейнеры должны быть stateless. Перезапуск или redeploy не должен уничтожать:

- историю;
- аккаунты;
- jobs;
- credentials;
- uploads;
- DOCX/PDF;
- audit logs.

Persistent disk Render не должен быть обязательным элементом production-архитектуры.

LibreOffice рекомендуется устанавливать только в export worker image, а не во все backend-контейнеры.

---

# 14. Миграция текущей local-first версии

Миграция не должна превращаться в одномоментное удаление существующих механизмов.

Предпочтительные переходные интерфейсы:

```text
RegistryStore
├── SQLiteRegistryStore
└── PostgresRegistryStore

ArtifactStorage
├── LocalArtifactStorage
└── ObjectArtifactStorage

TaskDispatcher
├── LocalBackgroundDispatcher
└── RabbitMQTaskDispatcher

CredentialStore
├── LocalDevelopmentCredentialStore
└── VaultCredentialStore
```

Это позволяет:

- сохранить local-first режим;
- тестировать новые компоненты отдельно;
- сравнивать старую и новую реализацию;
- выполнять миграцию композициями;
- не смешивать cloud-зависимости с domain-логикой pipeline.

Global `current_run` перестаёт быть source of truth. Его заменяют `jobs`, `job_events`, checkpoints и worker state.

---

# 15. Композиции для будущей декомпозиции

Ниже перечислены композиции, для которых позднее создаются отдельные планы и TODO-листы.

Это **не TODO-лист текущего документа**.

## Backend compositions

1. Release boundary and compatibility strategy.
2. PostgreSQL schema and tenant model.
3. SQLAlchemy repositories and Alembic migrations.
4. Authentication, sessions and RBAC.
5. Admin bootstrap micro-project.
6. RabbitMQ, Celery and outbox.
7. Job state, events, checkpoints and cancellation.
8. Provider registry and routing.
9. Global provider budgets and health states.
10. Secret storage and credential lifecycle.
11. Object storage and artifact access.
12. OCR/research workers.
13. DOCX/PDF export worker.
14. Audit, observability and security hardening.
15. Docker and Render deployment.
16. Local-first compatibility and data migration.

## Frontend compositions

1. Public/auth pages.
2. Registration and login flows.
3. User workspace shell.
4. Job creation and live status.
5. History and artifact management.
6. Provider and credential settings.
7. Global resource availability UX.
8. Admin application shell.
9. User and role administration.
10. Provider, model and global limit administration.
11. Queue/job monitoring.
12. Audit and system health views.
13. Voluntary support page.
14. Public Telegram/commercial contact surface.
15. Frontend security, CSP and safe content rendering.

Каждая композиция должна получить собственный документ до начала реализации.

---

# 16. Архитектурные инварианты

Следующие правила не должны нарушаться при декомпозиции:

1. Local-first релиз создаётся один раз до первой реализации Part 2.
2. Пожертвования не влияют на доступ, функции, лимиты или очередь.
3. В проекте нет платных пользовательских статусов.
4. Пользовательские API-ключи не передаются через RabbitMQ.
5. Сохранённые ключи не возвращаются во frontend в plaintext.
6. Только минимально необходимый worker имеет право decrypt.
7. Global `current_run` не является production state storage.
8. Production containers являются stateless.
9. PostgreSQL является source of truth для многопользовательского состояния.
10. Object storage является source of truth для постоянных файлов.
11. Frontend route guard не заменяет backend authorization.
12. Admin bootstrap token не заменяет session JWT.
13. Provider с неизвестной квотой отслеживается по доступности, а не по выдуманному остатку токенов.
14. Система не обходит лимиты провайдеров ротацией VM или fingerprint.
15. Frontend и backend декомпозируются отдельно.
16. Для каждой композиции создаётся отдельный TODO до изменения кода этой композиции.
17. Смена лицензии не должна задним числом размывать local-first release boundary.

---

# 17. Не входит в первую реализацию Part 2

Без отдельного архитектурного решения не добавляются:

- Kafka;
- Neo4j или другая graph database;
- OGM;
- платёжный шлюз;
- подписки;
- рекуррентные платежи;
- платные планы;
- преимущества за пожертвования;
- хранение пользовательских ключей только в browser localStorage;
- самописная криптография;
- обязательный post-quantum transport для первой версии;
- горизонтальное масштабирование без завершённой job isolation;
- обход upstream provider limits.

---

# 18. Условие начала реализации

Реализация Part 2 может начаться только когда одновременно выполнены два условия:

1. В этом документе отмечен `LOCAL-FIRST RELEASE GATE COMPLETE` и заполнены поля релиза.
2. Для выбранной композиции создан отдельный документ с TODO-листом, зависимостями, тестами, migration path и критериями готовности.

До выполнения этих условий разрешены только:

- уточнение архитектуры;
- обновление этого master plan;
- создание документов декомпозиции;
- проверка и создание local-first release.

Этот порядок обязателен как для людей, так и для AI-агентов.
