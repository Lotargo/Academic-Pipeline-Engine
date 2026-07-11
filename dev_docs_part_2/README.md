# Academic Pipeline Engine — Development Plan, Part 2

## Назначение

Этот каталог описывает переход APE от local-first приложения к бесплатному многопользовательскому сервису.

Этот файл является точкой входа и индексом общего прогресса. Детали находятся в `PLAN.md` и `TODO.md` отдельных композиций.

---

# 1. Цель

Part 2 включает многопользовательскую модель, отдельные frontend/API/workers, Supabase/PostgreSQL, очередь задач, object storage, защищённое хранение credentials, admin panel, глобальные AI/OCR-ресурсы, BYOK и Docker deployment.

Платных статусов и преимуществ за пожертвования нет. Local-first режим сохраняется через адаптеры.

---

# 2. Индекс выполнения

Агент сначала смотрит сюда, затем открывает только документы выбранной композиции.

## Как выбрать следующую работу

1. Найти подходящую композицию с `[ ]`.
2. Открыть её `PLAN.md` и проверить `Depends on`.
3. Если зависимость ниже ещё не отмечена как завершённая, выбрать другую композицию.
4. Открыть `TODO.md` и взять конкретную незавершённую задачу.

Порядок ID является рекомендуемой последовательностью. `Depends on` имеет приоритет.

## Когда ставить `[x]`

Композиция отмечается завершённой только когда:

- обязательные пункты `TODO.md` выполнены или явно отменены;
- acceptance criteria из `PLAN.md` выполнены;
- необходимые тесты пройдены;
- создан итоговый walkthrough;
- нет незадокументированных блокирующих проблем.

Частично выполненная композиция остаётся с `[ ]`. Её подробный прогресс смотрят только в локальном `TODO.md`.

После полного завершения агент обновляет этот индекс в том же commit или PR.

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
- [ ] **FE-04** — [History and Artifacts](frontend/FE-04-history-and-artifacts/PLAN.md) · [TODO](frontend/FE-04-history-and-artifacts/TODO.md)
- [ ] **FE-05** — [Provider Settings](frontend/FE-05-provider-settings/PLAN.md) · [TODO](frontend/FE-05-provider-settings/TODO.md)
- [ ] **FE-06** — [Admin Panel](frontend/FE-06-admin-panel/PLAN.md) · [TODO](frontend/FE-06-admin-panel/TODO.md)
- [ ] **FE-07** — [Support and Contact](frontend/FE-07-support-and-contact/PLAN.md) · [TODO](frontend/FE-07-support-and-contact/TODO.md)
- [ ] **FE-08** — [Frontend Security](frontend/FE-08-frontend-security/PLAN.md) · [TODO](frontend/FE-08-frontend-security/TODO.md)
- [ ] **FE-09** — [Workspace Settings and Modes](frontend/FE-09-workspace-settings-and-modes/PLAN.md) · [TODO](frontend/FE-09-workspace-settings-and-modes/TODO.md)

## Backend additions

- [ ] **BE-12** — [Workspace Data Deletion](backend/BE-12-workspace-data-deletion/PLAN.md) · [TODO](backend/BE-12-workspace-data-deletion/TODO.md)

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

Для одной композиции читаются только:

1. Этот файл и индекс выше.
2. `PLAN.md` выбранной композиции.
3. Её `TODO.md`.
4. Файлы из `Required context`.
5. Прямо указанные contracts, ADR или reports.

Не нужно читать соседние композиции и всю хронологию отчётов.

```text
root README + один PLAN + один TODO + явные зависимости
```

Если этого недостаточно, задача должна быть разделена точнее.

---

# 5. Формат работы

Каждая композиция содержит:

```text
PLAN.md
TODO.md
reports/
```

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

---

# 7. Рабочий алгоритм

1. Открыть этот файл.
2. Проверить обязательные архитектурные переходы и deployment gates.
3. Найти доступную композицию с `[ ]`.
4. Проверить её `Depends on`.
5. Выбрать связанный пакет незавершённых задач в `TODO.md`.
6. Прочитать только `Required context`.
7. Выполнить задачу и тесты.
8. Обновить локальный TODO и создать walkthrough.
9. При полном завершении отметить композицию `[x]` в этом индексе.

Этот порядок обязателен для людей и AI-агентов.

Рабочая сессия не обязана ограничиваться одним task ID. Следует брать
максимальный связанный пакет задач, который помещается в один рабочий контекст,
имеет общую проверку и не пересекает незакрытые зависимости. Одиночная задача
выбирается только когда следующая требует отдельного решения, внешнего доступа
или существенно другого контекста. TODO и walkthrough перечисляют все task ID,
фактически закрытые в сессии.

После полного завершения backend-композиции её код, документация, TODO,
walkthrough и отметка в этом индексе закрепляются отдельным коммитом. Перед
коммитом должны пройти предусмотренные композицией проверки и `git diff
--check`. Незавершённая композиция может оставаться без промежуточного коммита,
если это не мешает безопасному продолжению работы.
