# Academic Pipeline Engine — Development Plan, Part 2

## Назначение

Этот каталог описывает переход APE от local-first приложения к бесплатному многопользовательскому сервису.

Этот файл является точкой входа и индексом общего прогресса. Детали стандартных композиций находятся в их `PLAN.md` и `TODO.md`. Core-pipeline рефакторинг использует уже подготовленные архитектурные заметки из [`dev_docs/`](../dev_docs/README.md) без создания дублирующих планов.

---

# 1. Цель

Part 2 включает многопользовательскую модель, отдельные frontend/API/workers, Supabase/PostgreSQL, очередь задач, object storage, защищённое хранение credentials, admin panel, глобальные AI/OCR-ресурсы, BYOK и Docker deployment.

Платных статусов и преимуществ за пожертвования нет. Local-first режим сохраняется через адаптеры.

---

# 2. Индекс выполнения

Агент сначала смотрит сюда, затем открывает только документы выбранной композиции или одну выбранную core-pipeline заметку.

## Как выбрать следующую работу

1. Найти подходящую композицию или core-pipeline задачу с `[ ]`.
2. Для обычной композиции открыть её `PLAN.md` и проверить `Depends on`.
3. Для `CORE-13`, `CORE-14` или `CORE-15` открыть только связанную заметку из `dev_docs/` и проверить порядок выполнения core-блока ниже.
4. Если зависимость ещё не завершена, выбрать другую задачу.
5. Для обычной композиции открыть `TODO.md`; для core-задачи выбрать следующий связанный пункт P0/P1/P2 из её заметки.

Порядок ID является рекомендуемой последовательностью. Явные зависимости имеют приоритет.

## Когда ставить `[x]`

Обычная композиция отмечается завершённой только когда:

- обязательные пункты `TODO.md` выполнены или явно отменены;
- acceptance criteria из `PLAN.md` выполнены;
- необходимые тесты пройдены;
- создан итоговый walkthrough;
- нет незадокументированных блокирующих проблем.

Core-pipeline задача отмечается завершённой только когда:

- выполнены применимые пункты P0/P1/P2 связанной заметки;
- выполнены её критерии готовности;
- пройдены regression, integration и benchmark-проверки, предусмотренные заметкой;
- изменения не нарушают local-first и service profiles;
- commit history или короткий итоговый отчёт позволяет проверить фактически выполненный объём.

Частично выполненная задача остаётся с `[ ]`. После полного завершения индекс обновляется в том же commit или PR.

## Backend

- [x] **BE-01** — [Data and Tenancy](backend/BE-01-data-and-tenancy/PLAN.md) · [TODO](backend/BE-01-data-and-tenancy/TODO.md)
- [x] **BE-02** — [ORM and Migrations](backend/BE-02-orm-and-migrations/PLAN.md) · [TODO](backend/BE-02-orm-and-migrations/TODO.md)
- [x] **BE-03** — [Authentication and RBAC](backend/BE-03-auth-and-rbac/PLAN.md) · [TODO](backend/BE-03-auth-and-rbac/TODO.md)
- [x] **BE-04** — [Admin Bootstrap](backend/BE-04-admin-bootstrap/PLAN.md) · [TODO](backend/BE-04-admin-bootstrap/TODO.md)
- [x] **BE-05** — [Secret Storage](backend/BE-05-secret-storage/PLAN.md) · [TODO](backend/BE-05-secret-storage/TODO.md)
- [x] **BE-06** — [Queue and Workers](backend/BE-06-queue-and-workers/PLAN.md) · [TODO](backend/BE-06-queue-and-workers/TODO.md)
- [x] **BE-07** — [Job State](backend/BE-07-job-state/PLAN.md) · [TODO](backend/BE-07-job-state/TODO.md)
- [x] **BE-08** — [Provider Routing](backend/BE-08-provider-routing/PLAN.md) · [TODO](backend/BE-08-provider-routing/TODO.md)
- [x] **BE-09** — [Global Resources and BYOK](backend/BE-09-global-resources-and-byok/PLAN.md) · [TODO](backend/BE-09-global-resources-and-byok/TODO.md)
- [x] **BE-10** — [Object Storage](backend/BE-10-object-storage/PLAN.md) · [TODO](backend/BE-10-object-storage/TODO.md)
- [x] **BE-11** — [Local-First Compatibility](backend/BE-11-local-first-compatibility/PLAN.md) · [TODO](backend/BE-11-local-first-compatibility/TODO.md)

## Frontend

- [x] **FE-01** — [Auth Pages](frontend/FE-01-auth-pages/PLAN.md) · [TODO](frontend/FE-01-auth-pages/TODO.md)
- [x] **FE-02** — [User Cabinet](frontend/FE-02-user-cabinet/PLAN.md) · [TODO](frontend/FE-02-user-cabinet/TODO.md)
- [x] **FE-03** — [Jobs and Live Status](frontend/FE-03-jobs-and-live-status/PLAN.md) · [TODO](frontend/FE-03-jobs-and-live-status/TODO.md)
- [x] **FE-04** — [History and Artifacts](frontend/FE-04-history-and-artifacts/PLAN.md) · [TODO](frontend/FE-04-history-and-artifacts/TODO.md)
- [x] **FE-05** — [Provider Settings](frontend/FE-05-provider-settings/PLAN.md) · [TODO](frontend/FE-05-provider-settings/TODO.md)
- [ ] **FE-06** — [Admin Panel](frontend/FE-06-admin-panel/PLAN.md) · [TODO](frontend/FE-06-admin-panel/TODO.md)
- [x] **FE-07** — [Support and Contact](frontend/FE-07-support-and-contact/PLAN.md) · [TODO](frontend/FE-07-support-and-contact/TODO.md)
- [x] **FE-08** — [Frontend Security](frontend/FE-08-frontend-security/PLAN.md) · [TODO](frontend/FE-08-frontend-security/TODO.md)
- [ ] **FE-09** — [Workspace Settings and Modes](frontend/FE-09-workspace-settings-and-modes/PLAN.md) · [TODO](frontend/FE-09-workspace-settings-and-modes/TODO.md)
- [x] **FE-10** — [Main Editor and Unified Jobs](frontend/FE-10-main-editor-and-unified-jobs/PLAN.md) · [TODO](frontend/FE-10-main-editor-and-unified-jobs/TODO.md)
- [ ] **FE-11** — [Frontend Lint Quality](frontend/FE-11-frontend-lint-quality/PLAN.md) · [TODO](frontend/FE-11-frontend-lint-quality/TODO.md)

### Обязательное уточнение для FE-07

Этот блок имеет приоритет над текущими `PLAN.md` и `TODO.md` композиции `FE-07`, пока они не будут синхронизированы с данным решением.

- Основной сценарий добровольной поддержки реализуется обычной HTML-формой, отправляющей пользователя на `https://yoomoney.ru/quickpay/confirm`.
- Пользователь должен иметь возможность самостоятельно указать произвольную сумму доната.
- Значения `150`, `500`, `1000` и `5000` рублей могут использоваться как необязательные быстрые пресеты, но не являются отдельными обязательными способами оплаты.
- Для самой frontend-формы достаточно номера кошелька ЮMoney в поле `receiver`. API key, `client_id` и OAuth token для этого сценария не требуются.
- В рамках `FE-07` не создаются собственный платёжный шлюз, backend-проверка поступления перевода, история платежей или автоматическая выдача статуса. HTTP-уведомления и серверная верификация могут появиться только как отдельное будущее решение.
- СБП-ссылка и QR могут рассматриваться только как необязательный дополнительный вариант и не являются acceptance requirement.
- Текст интерфейса должен явно обозначать добровольную поддержку или благодарность и не связывать перевод с услугой, подпиской, лимитами, приоритетом или иным entitlement.

## Backend additions

- [ ] **BE-12** — [Workspace Data Deletion](backend/BE-12-workspace-data-deletion/PLAN.md) · [TODO](backend/BE-12-workspace-data-deletion/TODO.md)

## Core pipeline and document quality

Подробный контекст находится в [`dev_docs/README.md`](../dev_docs/README.md). Документы ниже являются единственным подробным планом для этих задач. Не создаются зеркальные `PLAN.md` и `TODO.md`, пересказывающие то же содержание.

- [ ] **CORE-13** — [Document Integrity and Optional Revision Pipeline](../dev_docs/13_DOCUMENT_INTEGRITY_AND_OPTIONAL_REVISION_PIPELINE.md)
- [ ] **CORE-14** — [Skill Routing, Hybrid Retrieval and Provider Infrastructure](../dev_docs/14_SKILL_ROUTING_HYBRID_RETRIEVAL_AND_PROVIDER_INFRASTRUCTURE.md)
- [ ] **CORE-15** — [Agent Instruction Refactor and Editorial Quality](../dev_docs/15_AGENT_INSTRUCTION_REFACTOR_AND_EDITORIAL_QUALITY.md)

### Порядок выполнения core-блока

1. До завершения `FE-10` разрешены только безопасные P0-исправления из `CORE-13` и `CORE-15`, которые не меняют публичный Job API, FSM-контракты или формат артефактов: Unicode fixes, leakage gates, regression fixtures, secret/config cleanup и baseline benchmarks.
2. После завершения `FE-10` реализуется фундамент `CORE-13`: DocumentState/ledgers, global integrity gates, SourceCards, CalculationCards и стадия assembly.
3. Затем выполняется `CORE-15`: role-scoped InstructionCompiler, SectionBrief, специализированные reviewers и patch-first corrections.
4. После появления InstructionCompiler выполняется `CORE-14`: RoutingDecision, skills, typed graph, Qdrant/Jina/LangSearch, hybrid retrieval, reranking и confidence calibration.
5. После стабилизации routing и instruction bundles завершается optional revision flow из `CORE-13`.
6. `CORE-13`, `CORE-14` и `CORE-15` должны быть завершены до финальной фиксации production deployment и observability, чтобы platform-слой не закреплял устаревшие pipeline contracts.

## Platform

- [ ] **PL-01** — [Docker](platform/PL-01-docker/PLAN.md) · [TODO](platform/PL-01-docker/TODO.md)
- [ ] **PL-02** — [Render Deployment](platform/PL-02-render-deployment/PLAN.md) · [TODO](platform/PL-02-render-deployment/TODO.md)
- [ ] **PL-03** — [Observability](platform/PL-03-observability/PLAN.md) · [TODO](platform/PL-03-observability/TODO.md)

---

# 3. Обязательный переход к Supabase и provider-only auth

Этот раздел имеет приоритет над завершёнными legacy-композициями авторизации и должен учитываться при выборе следующих задач.

## Статус существующей авторизации

- `BE-03` и `FE-01` завершены по старому контракту с собственными email/password, JWT и refresh sessions.
- Эти композиции не переоткрываются и не считаются финальной production-авторизацией.
- Переход на Supabase Auth оформляется отдельными backend/frontend/platform-композициями с новыми ID, собственными `PLAN.md`, `TODO.md` и walkthrough.
- До создания этих композиций агент не удаляет legacy auth и не смешивает два источника identity в одной незадокументированной реализации.

## Целевая модель окружений

Используются три различных runtime profile:

1. `local` — прежний автономный local-first режим: SQLite, local storage, local dispatcher, без обязательного Supabase.
2. `service-dev` — разработка многопользовательского сервиса: локальный Supabase stack через Supabase CLI/Docker, локальные migrations и seed data.
3. `service-prod` — production: Supabase Cloud для PostgreSQL/Auth и stateless frontend/API/workers на Render и/или Vercel.

Обычный standalone PostgreSQL в Docker не является целевым `service-dev`, если он не входит в локальный Supabase stack. SQLAlchemy и Alembic сохраняются для прикладной схемы, но схема Supabase Auth не изменяется вручную.

## Целевая модель входа

Для первого публичного запуска применяется provider-only auth:

- Google OAuth;
- Яндекс OAuth через поддерживаемый Supabase custom OAuth/OIDC flow;
- без SMS и регистрации по телефону;
- без публичной email/password регистрации;
- без отдельной ручной email verification;
- без password reset flow.

Пользователь приложения определяется стабильным внутренним `user_id`. Внешние identities связываются по `(provider, provider_subject)`, а не только по email. Привязка второго провайдера выполняется из уже авторизованного аккаунта.

## Что разрешено до первого публичного деплоя

До получения стабильного публичного URL разрешено и требуется:

- подготовить кнопки Google и Яндекс;
- подготовить `/auth/callback`, loading, cancel, denied, provider-error и session-restore states;
- реализовать auth adapter/interface, чтобы mock и Supabase implementations заменялись без переписывания UI;
- проверить frontend и backend contracts на моках;
- проверить создание прикладного user/workspace после успешной mock identity;
- оставить provider secrets и production redirects незаполненными;
- явно помечать OAuth как mock/stub и не заявлять, что реальный внешний вход завершён.

Реальный OAuth на localhost допускается как необязательный smoke test, если приложения Google/Яндекс уже зарегистрированы с локальными callback URI. Он не является условием продолжения frontend/backend работ до деплоя.

## Deployment gate для реального OAuth

Полноценная provider-авторизация завершается только после первого публичного деплоя и получения стабильного HTTPS URL. Собственный домен для этого не обязателен:

- Render выдаёт публичный `*.onrender.com`;
- Vercel выдаёт публичный `*.vercel.app`;
- один стабильный production URL выбирается как canonical frontend URL.

После появления URL обязательны следующие шаги:

1. Зафиксировать production frontend URL и API URL.
2. Настроить Supabase Cloud `SITE_URL` и точный allow-list redirect URL для `/auth/callback`.
3. Различать два уровня callback:
   - provider redirect URI ведёт в Supabase Auth `/auth/v1/callback`;
   - application redirect URL ведёт из Supabase в frontend `/auth/callback`.
4. Зарегистрировать или обновить приложения Google и Яндекс с точными production callback URI.
5. Добавить client IDs/secrets только в защищённые environment variables.
6. Заменить mock auth adapter на Supabase implementation.
7. Выполнить реальные E2E-сценарии для Google, Яндекс, cancel/deny, повторного входа, logout, session restore и identity linking.
8. Не отмечать provider-auth композиции завершёнными, пока реальные E2E-проверки на deployment URL не пройдены.

Preview URL не становится canonical production URL автоматически. Wildcard redirects разрешены только для preview/dev, а production использует точный URL.

---

# 4. Правила чтения

Для обычной композиции читаются только:

1. Этот файл и индекс выше.
2. `PLAN.md` выбранной композиции.
3. Её `TODO.md`.
4. Файлы из `Required context`.
5. Прямо указанные contracts, ADR или reports.

Для `CORE-13`, `CORE-14` или `CORE-15` читаются только:

1. Этот файл и core-порядок выше.
2. [`dev_docs/README.md`](../dev_docs/README.md).
3. Одна выбранная архитектурная заметка.
4. Только файлы кода, конфигурации и тестов, прямо необходимые для выбранного пункта P0/P1/P2.
5. Другие core-заметки только при явной междокументной зависимости.

Не нужно читать соседние композиции, все три core-заметки одновременно или всю хронологию отчётов.

```text
standard: root README + один PLAN + один TODO + явные зависимости
core:     root README + dev_docs README + одна numbered note + нужный код
```

Если этого недостаточно, задача должна быть разделена точнее.

---

# 5. Формат работы

Каждая стандартная композиция содержит:

```text
PLAN.md
TODO.md
reports/
```

Core-pipeline задачи не создают зеркальную структуру. Их numbered notes одновременно хранят архитектурный план, приоритеты, критерии готовности и предлагаемые файлы. Частичные изменения остаются `[ ]` в индексе до выполнения всей заметки.

Мягкие лимиты:

```text
PLAN.md:     до 150 строк
TODO.md:     до 120 строк
Walkthrough: до 100 строк
ADR:         до 80 строк
```

Walkthrough содержит task IDs, commit/PR, сделанное, тесты, отклонения, проблемы и следующий шаг. Он не копирует diff и полные логи.

Task IDs не перенумеровываются после начала работы.

Contracts создаются только для интерфейсов между композициями. ADR создаются только для решений, которые трудно отменить.

---

# 6. Инварианты

1. Frontend, backend и platform декомпозируются отдельно.
2. Supabase PostgreSQL хранит многопользовательское production-состояние.
3. Object storage хранит постоянные файлы.
4. Production API и workers являются stateless.
5. Очередь не является базой данных.
6. Workers идемпотентны; публикация jobs использует transactional outbox.
7. Persistence, API и domain-модели разделены.
8. Tenant isolation проверяется на backend и уровне данных.
9. Пожертвования не влияют на доступ, лимиты или очередь.
10. Не вводятся платные планы, Kafka, OGM или graph database без нового решения.
11. Не используется обход upstream-лимитов.
12. Local-first adapters сохраняются до проверки миграции.
13. `local`, `service-dev` и `service-prod` не смешиваются неявными environment defaults.
14. Supabase Auth является целевым source of truth для service identity; FastAPI отвечает за прикладной RBAC и tenant authorization.
15. Provider-only auth не считается завершённым по mock UI или unit tests без реального deployment E2E.
16. FE-01 остаётся завершённой legacy-композицией и не доказывает готовность production OAuth.
17. Отсутствие собственного домена не блокирует запуск: используется стабильный HTTPS URL Render/Vercel.
18. `dev_docs/13`, `dev_docs/14` и `dev_docs/15` являются authoritative plans для core-pipeline рефакторинга и не дублируются новыми композициями.
19. Публичные Job API и frontend-контракты стабилизируются в `FE-10` до крупных изменений FSM, document state и revision flow.
20. Skills, hybrid retrieval и instruction bundles не должны обходить provider routing, tenant isolation или local-first adapters.
21. Production observability должна учитывать routing path, active provider, fallback depth, selected skills, instruction bundle version и revision count.

---

# 7. Рабочий алгоритм

1. Открыть этот файл.
2. Проверить обязательные архитектурные переходы, core-gates и deployment gates.
3. Найти доступную стандартную композицию или core-задачу с `[ ]`.
4. Проверить её зависимости.
5. Для стандартной композиции выбрать связанный пакет незавершённых задач в `TODO.md`; для core-задачи выбрать связанный пакет P0/P1/P2 из одной numbered note.
6. Прочитать только Required context или минимальный набор файлов, указанный правилами core-чтения.
7. Выполнить задачу и тесты.
8. Обновить локальный TODO либо состояние core-задачи и создать walkthrough, когда он необходим.
9. При полном завершении отметить композицию или core-задачу `[x]` в этом индексе.

Этот порядок обязателен для людей и AI-агентов.

Рабочая сессия не обязана ограничиваться одним task ID. Следует брать
максимальный связанный пакет задач, который помещается в один рабочий контекст,
имеет общую проверку и не пересекает незакрытые зависимости. Одиночная задача
выбирается только когда следующая требует отдельного решения, внешнего доступа
или существенно другого контекста. TODO, numbered note и walkthrough перечисляют
фактически закрытый объём.

После полного завершения backend-композиции или core-задачи её код,
документация, TODO/numbered note, walkthrough и отметка в этом индексе
закрепляются отдельным коммитом. Перед коммитом должны пройти предусмотренные
проверки и `git diff --check`. Незавершённая задача может оставаться без
промежуточного коммита, если это не мешает безопасному продолжению работы.

Визуальная browser-верификация остаётся за пользователем: в приложении есть
ошибки, из-за которых автоматическая попытка открыть или проверить UI может
закрыть приложение. Агент не запускает браузерную проверку самостоятельно и
фиксирует в walkthrough только подтверждённую пользователем визуальную проверку.
