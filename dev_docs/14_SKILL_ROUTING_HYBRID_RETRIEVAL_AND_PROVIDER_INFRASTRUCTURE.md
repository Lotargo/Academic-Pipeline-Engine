# 14. Skill Routing, Hybrid Retrieval and Provider Infrastructure

## Статус

Реализация завершена. Foundations этапов 1--7, semantic Qdrant path, rank
fusion, ColBERT second-stage rerank, tenant-safe fallback и routing benchmark
выполнены. `RoutingEngine` публикует фактические channel evidence в
`RoutingDecision`; runtime factory загружает только проверенный holdout profile
и безопасно остаётся uncalibrated при отсутствии его файла.

### Checkpoint (2026-07-13)

- Добавлены типизированный `config/providers.yaml` и безопасный
  `config/secrets.example.json`. Проверенные Qdrant Cloud Inference model IDs
  закреплены для E5, BM25 и ColBERT.
- `SecretResolver` использует приоритет environment -> local JSON -> missing,
  принимает стандартные имена секретов и сохраняет compatibility API старых
  provider IDs.
- Введён отдельный artifact/skill `RoutingDecision` с candidates, margin,
  coverage, fallback depth и confidence bands. Legacy lexical resolver публикует
  его в metadata как `local_rules_only`, не меняя пока orchestration policy.
- `SkillManifest` расширен версиями, examples, compatibility, role scope,
  preconditions, dependencies, conflicts, provides и gates. Добавлены
  валидируемые `SkillPlan`, typed graph edges и детерминированный DAG order.
- Artifact и skill manifests содержат versioned bilingual retrieval profiles с
  positive/negative examples, capabilities, compatibility и agent scope.
  `RetrievalCard` хранит tenant, active state и readiness для `dense_jina`,
  `dense_e5`, `sparse_bm25` и `late_colbert`; negative examples не попадают в
  embedding projection и используются только penalty layer.
- Добавлены adapter-neutral async `RoutingIndex` и обязательный
  `InMemoryRoutingIndex`. Локальный adapter поддерживает upsert/delete,
  deterministic lexical search, latest-version semantics, inactive tombstones,
  tenant override без cross-tenant visibility и safe healthcheck.
- Добавлены `QdrantRoutingIndex` и `QdrantRoutingRecord`: cloud projection
  использует deterministic UUID, Qdrant payload для всей versioned card и
  отдельный `scope` filter для global/tenant данных. Запрос tenant получает
  только global scope и свой scope; сторонние tenants не читаются. До проверки
  model IDs card-only projection повторяет deterministic local scoring,
  поэтому генерация по-прежнему не зависит от Qdrant.
- Named vectors разрешены только через `QdrantRoutingRecord`; его readiness
  обязана в точности совпадать с реально переданными `dense_jina`, `dense_e5`,
  `sparse_bm25` и `late_colbert` representations. Adapter не угадывает model
  IDs; Qdrant Cloud Document inputs передаются только с уже проверенными IDs.
- `RoutingFallbackPolicy` выбирает документированные depth 0--3 только когда
  все active cards готовы к соответствующему vector channel: Jina+BM25,
  E5+BM25, BM25+local rules или local rules only с обязательным Planner.
- Runtime configuration нормализована: `config/secrets.json` использует
  стандартные secret names, а `providers.yaml` хранит Qdrant endpoint, cluster
  ID, Cloud Inference flag и подтверждённые model IDs:
  `intfloat/multilingual-e5-small`, `qdrant/bm25` и
  `answerdotai/answerai-colbert-small-v1`. Live Cloud Inference показал, что
  ColBERT output имеет 96 dimensions; это значение фиксируется в schema вместо
  generic 128. Секреты не дублируются в provider config.
  `QdrantRoutingIndex.from_provider_config()` получает URL и collection из
  typed config, а ключ — только через `SecretResolver`.
- `routing_knowledge` provisioned idempotently с `dense_e5` (384, Cosine),
  `sparse_bm25`, `late_colbert` (96, Cosine, MaxSim, HNSW disabled) и indexes
  `scope`, `entity_type`, `entity_id`, `active`. Первый generic ColBERT размер
  128 был отклонён Cloud Inference; пустая collection была безопасно пересоздана
  с подтверждённой размерностью 96. Временный smoke point после проверки удалён.
- `LangSearchClient` реализует Web Search; `JinaClient` реализует embeddings и
  rerank. `ResearcherAgent` использует LangSearch -> Jina rerank -> top URLs ->
  existing fetch/read stage; при provider error сохраняется legacy DuckDuckGo
  fallback, а при ошибке Jina — порядок LangSearch.
- Добавлен `RoutingEngine`: он преобразует результаты index adapter-а в
  artifact candidates и переносит неизменённые фактические channel evidence
  (ranks, raw provider score, normalised RRF contribution и graph penalties)
  в `RoutingDecision`; raw provider scores не суммируются напрямую.
- `QdrantRoutingIndex.search()` сначала получает безопасную visibility
  projection, затем выполняет отдельные Cloud Inference запросы E5 и BM25 с
  `scope`, `entity_type`, `active` и, для rerank, `has_id` filters. Он сливает
  channel ranks через RRF, применяет negative/graph penalties и передаёт только
  RRF top-k в ColBERT. Tenant query обращается лишь к `global` и своему
  `tenant:<uuid>` scope; tenant override вытесняет global card до fusion.
- При remote outage optional `fallback_index` возвращает local evidence; при
  неполной vector readiness используется local rules. Поэтому cloud path не
  является источником истины и не блокирует local-first generation.
- Добавлены `cloud_inference_record()`, идемпотентный
  `scripts/reindex_routing_knowledge.py` и canonical projection. Live reindex
  загрузил 13 artifact/skill cards в `routing_knowledge`; live query вернул
  `qdrant_e5`, `qdrant_bm25`, `colbert`, `rrf` и lexical evidence.
- `config/routing_benchmark.yaml` расширен до 28 labelled cases: 16
  calibration и 12 независимых holdout. Corpus покрывает русский, английский
  и mixed language, negative cues, compound request, continuation и explicit
  override. `scripts/run_core14_routing_benchmark.py [--qdrant]` обучает
  serializable isotonic PAVA mapping только на calibration split и считает
  Brier только на holdout.
- Зафиксирован runtime default
  `config/routing_confidence_calibration.yaml`; `RoutingEngine.with_default_calibration()`
  загружает его без каких-либо network calls. Live 28-case run: path
  `e5_bm25_colbert` во всех cases, artifact top-1 `0.928571`, top-3
  `0.964286`, holdout Brier `0.083333`, mean Cloud latency около `2.28 s`.
  Latency остаётся baseline, а не постоянным SLA.
- Regression: полный Python suite — 666 passed, 3 skipped.
- CORE-14 закрыт. Следующий core package — итоговая integration acceptance
  optional revision flow из CORE-13. Local-first fallback остаётся обязательным.

Документ продолжает решения из документа №13 и фиксирует обсуждение механизма уверенности, режима skills, графовой составляющей, гибридного поиска, Qdrant Cloud, Jina AI, LangSearch, реранкинга, резервных провайдеров, Airflow и хранения секретов.

Большая часть описанного ниже ещё не реализована. Сначала требуется проверить варианты на отдельном routing benchmark, после чего внедрять их поэтапно.

## 1. Ограничения текущего механизма уверенности

Текущий `ArtifactManifestResolver` выбирает manifest по количеству совпавших подстрок. Значение `confidence` растёт примерно как `0.55 + 0.15 * число совпадений` и ограничивается значением `0.95`.

Это полезная эвристика, но не вероятность правильного выбора. Основные проблемы:

- все фразы имеют одинаковый вес;
- точные названия и слабые общие слова считаются одинаково;
- отрицания не учитываются;
- неоднозначность почти не уменьшает результат;
- при равенстве влияет порядок candidates;
- русскоязычное покрытие неполное;
- низкая уверенность почти не меняет маршрут нового документа.

Поэтому текущее поле следует трактовать как `routing_score`, а уверенность представить отдельной структурой.

## 2. Разделение ответственности

Необходимо разделить три сущности:

```text
RoutingDecision
    что распознано, какие есть кандидаты и насколько выбор неоднозначен

ArtifactContract
    каким должен быть итоговый документ

SkillPlan
    какие способности нужны и как они применяются
```

Существующий S-expression DSL сохраняется как безопасное и детерминированное промежуточное представление ArtifactContract. Он не должен самостоятельно определять уверенность или выполнять графовую логику.

## 3. RoutingDecision

Предлагаемые поля:

```python
class RoutingDecision(BaseModel):
    candidates: list[ArtifactCandidate]
    selected_artifact_id: str | None
    top_score: float
    runner_up_score: float
    score_margin: float
    cue_coverage: float
    skill_coverage: float
    conflict_score: float
    channel_agreement: float
    fallback_depth: int
    active_retrieval_path: str
    confidence_band: str
    planner_required: bool
    reasons: list[str]
    ambiguity_notes: list[str]
```

Пока score не откалиброван на размеченном наборе запросов, UI не должен показывать его как точный процент. Допустимые bands:

- `direct`;
- `direct_with_fallback`;
- `planner_recommended`;
- `planner_required`.

Planner должен подключаться не только по порогу score, но и при малом margin, конфликте каналов, compound request, недостаточном skill coverage, неизвестном artifact и явном выборе skills mode.

## 4. Отдельный skills mode

Skills mode не является разновидностью template mode.

```text
template_mode
    определяет структуру документа

instruction_mode
    определяет способ выбора инструкций и skills
```

Предлагаемые значения `instruction_mode`:

- `direct`: используются явно выбранные artifact/template и минимальный контракт;
- `auto`: deterministic router выбирает candidates, Planner вызывается только при неоднозначности;
- `skills`: Planner вызывается всегда и выбирает skills из валидированного каталога.

Planner не должен свободно придумывать инструкции. Он возвращает только существующие skill IDs, причины выбора и unresolved conflicts. Затем Python-валидатор проверяет зависимости, совместимость и строит DAG.

## 5. SkillManifest

Skill должен описывать не только текстовую инструкцию, но и:

- version;
- positive и negative examples;
- compatible artifacts;
- agent scope;
- preconditions;
- `requires`;
- `provides`;
- `conflicts_with`;
- role-specific instructions;
- deterministic verification gate.

Пример логики:

```yaml
id: financial_model_validation
version: 1
compatible_artifacts: [academic_paper, report, plan_document]
agent_scope: [planner, writer, reviewer]
preconditions: [numeric_claims_present]
requires: [calculation_ledger]
provides: [validated_financial_model, scenario_consistency]
verified_by: [calculation_integrity_gate]
```

## 6. Графовая составляющая

Первый этап: типизированный DAG в YAML/Pydantic без обязательной graph database.

Узлы:

- Artifact;
- Template;
- Skill;
- Capability;
- AgentRole;
- Gate;
- EvidenceSignal.

Рёбра:

- `COMPATIBLE_WITH`;
- `REQUIRES`;
- `PROVIDES`;
- `CONFLICTS_WITH`;
- `VERIFIED_BY`;
- `EXECUTED_BY`;
- `TRIGGERED_BY`;
- `REFINES`.

После стабилизации схемы можно добавить ontology-lite и rule engine. OGM или отдельную graph database имеет смысл рассматривать только при сотнях или тысячах skills, пользовательских библиотеках, динамических связях и необходимости сложных graph queries.

OGM сам по себе не решает routing, confidence, conflict resolution и workflow planning.

## 7. Instruction Compiler

Сейчас агент может одновременно получать базовый prompt, template role/task, style contract, rubric, output constraints, adapter guidance, ArtifactContract, AgentContract, section instruction, document plan и пользовательские инструкции.

Нужен отдельный `InstructionCompiler`, который:

- удаляет дубли;
- не вкладывает ArtifactContract повторно внутрь AgentContract;
- обнаруживает конфликты;
- компилирует отдельный bundle для каждой роли;
- переносит программно проверяемые правила из prompt в gates;
- сохраняет provenance инструкции.

LLM должны получать только жанр, аудиторию, смысловую задачу, стиль аргументации, выбранные domain skills и релевантные ограничения пользователя.

Уникальность нумерации, существование source IDs, graph dependencies, placeholders, LaTeX и расчёты должны проверяться детерминированно.

## 8. Hybrid retrieval

Целевой routing pipeline:

```text
User Request
    -> explicit override
    -> lexical rules and negative cues
    -> dense retrieval
    -> sparse retrieval
    -> graph compatibility
    -> Rank-Score Fusion
    -> optional late-interaction reranking
    -> APE domain penalties and bonuses
    -> RoutingDecision
```

Lexical слой отвечает за точные термины, отрицания, форматы, аббревиатуры и ограничения вида «без таблиц» или «только план».

Dense слой отвечает за перефразировки, смысловую близость, многоязычные запросы, capabilities и поиск похожих skills.

Graph слой отвечает за compatibility, dependencies, conflicts и coverage.

## 9. Retrieval cards

В индекс следует помещать не только короткий description, а полноценные карточки:

- title;
- несколько русских и английских descriptions;
- positive examples;
- negative examples;
- capabilities;
- compatible artifacts;
- agent scope;
- version.

Negative examples не следует смешивать с positive text в одном dense vector. Они должны использоваться отдельным penalty/rule layer.

## 10. Rank-Score Fusion и confidence

Scores lexical, dense, BM25, ColBERT и rerankers находятся в разных шкалах. Их нельзя напрямую складывать без нормализации.

Первая версия должна использовать rank-based fusion, затем добавлять:

- normalized dense score;
- explicit rule bonus;
- graph compatibility bonus;
- negative cue penalty;
- conflict penalty.

Confidence нельзя приравнивать к cosine similarity, BM25 score, ColBERT score, Qdrant fusion score или relevance score реранкера.

Основные признаки confidence:

- top score;
- top-1/top-2 margin;
- согласие retrieval channels;
- skill coverage;
- conflict score;
- explicit override;
- request complexity;
- fallback depth;
- out-of-distribution score.

После накопления evaluation dataset можно применить logistic regression, isotonic calibration или другой интерпретируемый calibrator.

## 11. Qdrant Cloud

Поднят бесплатный Qdrant Cloud instance. Целевая коллекция:

```text
routing_knowledge
```

Qdrant используется как retrieval projection. Канонические manifests, templates, skills, graph edges и versions остаются в YAML, SQLite или будущем реляционном registry.

На бесплатном inference доступны:

- All MiniLM L6 v2;
- Intfloat Multilingual E5 Small;
- BM25;
- Answer.AI ColBERT Small V1.

Точные model IDs необходимо брать из Qdrant Inference UI/API, а не угадывать по отображаемым названиям.

Роли моделей:

```text
Jina Embeddings v5 Text Nano
    основной dense retriever

Intfloat Multilingual E5 Small
    multilingual dense fallback

All MiniLM L6 v2
    дополнительный English-oriented emergency fallback

BM25
    sparse retrieval

Answer.AI ColBERT Small V1
    late-interaction reranker для routing candidates
```

## 12. Именованные векторы и fallback

Нельзя искать вектором E5 по векторам, созданным Jina, даже если их размерности совпадают. Это разные пространства.

Каждая routing card должна заранее получить отдельные representations:

```text
dense_jina
dense_e5
sparse_bm25
late_colbert
```

Payload должен хранить entity type, entity ID, version, active status, compatibility, capabilities, dependencies, conflicts, tenant и readiness каждого vector representation.

## 13. Routing fallback chain

Нормальный путь:

```text
Jina dense + Qdrant BM25
    -> RRF/DBSF/custom fusion
    -> top candidates
    -> Qdrant ColBERT
    -> APE graph/rule scoring
```

Если Jina недоступна:

```text
Qdrant E5 + BM25 -> ColBERT -> APE scoring
```

Если dense inference недоступен:

```text
BM25 + local lexical rules + explicit overrides -> Planner required
```

Если Qdrant недоступен:

```text
current local rule router + local manifests -> Planner or preserve-first fallback
```

Предлагаемый `fallback_depth`:

- `0`: Jina + BM25 + optional ColBERT;
- `1`: Qdrant E5 + BM25 + optional ColBERT;
- `2`: BM25 + local rules;
- `3`: local rules only.

Чем глубже fallback, тем ниже максимально допустимый confidence band.

## 14. Jina AI

Основная embedding model:

```text
jina-embeddings-v5-text-nano
```

`jina-embeddings-v5-text-small` остаётся challenger-моделью для benchmark.

Основной web reranker:

```text
jina-reranker-v3
```

`jina-reranker-v2-base-multilingual` можно проверить как более простой вариант, если v3 окажется избыточным по latency или стоимости.

## 15. LangSearch

LangSearch выбран как основной web discovery provider для Researcher.

Целевой pipeline:

```text
Researcher
    -> LangSearch Web Search
    -> candidate results
    -> Jina Reranker v3
    -> top URLs
    -> existing URL fetch/read stage
    -> cleaned full text
    -> SourceCards
```

Fallback web reranker: LangSearch reranker. Если оба реранкера недоступны, используется исходный порядок LangSearch.

Не смешивать два разных реранкинга:

- routing cards: Qdrant ColBERT;
- динамические web results: Jina или LangSearch reranker.

## 16. RoutingIndex abstraction

Qdrant не должен быть жёстко встроен в core logic.

```python
class RoutingIndex(Protocol):
    async def upsert(self, records): ...
    async def delete(self, entity_id, version): ...
    async def search(self, query): ...
    async def healthcheck(self): ...
```

Планируемые реализации:

- `InMemoryRoutingIndex`;
- `PostgresRoutingIndex`;
- `QdrantRoutingIndex`.

Это позволит запускать проект без облачной инфраструктуры и упростит миграцию.

## 17. Airflow

Airflow не внедряется в основной интерактивный pipeline. У APE уже есть FSM, job lifecycle, retries, revision flow и streaming statuses. Airflow создаст вторую модель состояний и дублирующую оркестрацию.

Он может быть полезен позднее только для offline batch-задач:

- массовой переиндексации;
- пересчёта embeddings;
- регулярного routing benchmark;
- batch evaluation;
- обучения confidence calibrator;
- миграции model versions.

До появления таких задач достаточно management scripts, cron, Celery Beat или GitHub Actions.

## 18. Политика секретов и конфигурации

### Локальные provider keys

Используется:

```text
config/secrets.json
```

Файл скрыт через `.gitignore`. В нём локально хранятся API keys Jina, LangSearch, Qdrant и других провайдеров. Реальные значения не должны попадать в репозиторий, документацию, логи или чат.

### `.env`

Файл называется именно `.env` и используется только для локального тестирования перед облачным деплоем. Он также исключён из Git.

В нём можно проверять cloud-like startup path и переменные инфраструктуры: Qdrant URL, collection, cluster ID, Supabase, Render и временные локальные overrides.

### Production

В production файл `.env` и локальный `config/secrets.json` не обязательны. Render, Vercel и другие платформы передают секреты через environment variables или собственное secret storage.

### Несекретные параметры

Имена моделей, provider priorities, collection names, timeout, retry, top-k и fusion parameters следует хранить отдельно, например в:

```text
config/providers.yaml
```

## 19. SecretResolver

Текущий resolver следует сделать универсальным и изменить приоритет:

```text
environment variables
    -> config/secrets.json
    -> missing
```

Это позволяет production environment перекрывать локальные значения.

Resolver должен принимать стандартное имя секрета, а не содержать отдельный `elif` для каждого нового провайдера. Для старых имён можно оставить compatibility mapping.

Рекомендуемая структура:

```text
config/
├── agents.yaml
├── providers.yaml
├── secrets.json
├── secrets.example.json
├── artifact_manifests.yaml
├── document_templates.yaml
├── skill_edges.yaml
└── skills/
```

`secrets.example.json` может коммититься только с пустыми значениями.

## 20. Evaluation

До настройки thresholds требуется размеченный dataset с русскими, английскими и смешанными запросами, отрицаниями, compound requests, explicit overrides, continuation и out-of-distribution cases.

Сравнить:

1. current lexical rules;
2. BM25 only;
3. Jina dense only;
4. Jina dense + BM25;
5. Jina dense + BM25 + ColBERT;
6. Qdrant E5 + BM25;
7. Qdrant E5 + BM25 + ColBERT;
8. hybrid retrieval + graph penalties;
9. hybrid retrieval + Planner escalation.

Метрики:

- artifact top-1 accuracy;
- artifact top-3 recall;
- template compatibility;
- required skill recall;
- forbidden skill precision;
- Planner escalation precision/recall;
- fallback success rate;
- latency;
- recovery after provider failure;
- prompt token reduction после Instruction Compiler.

## 21. Этапы внедрения

1. Добавить `providers.yaml`, `secrets.example.json` и universal SecretResolver.
2. Ввести `RoutingDecision`, confidence bands, margin и fallback depth.
3. Добавить `SkillManifest`, `SkillPlan` и typed graph.
4. Расширить manifests retrieval cards и examples.
5. Реализовать `RoutingIndex` и Qdrant adapter.
6. Подключить Jina dense, Qdrant E5 fallback и BM25.
7. Добавить ColBERT только как reranker top-k.
8. Добавить `instruction_mode` и Planner escalation.
9. Реализовать Instruction Compiler.
10. Перевести web discovery на LangSearch с Jina/ LangSearch reranking.
11. Создать benchmark и откалибровать confidence.

## 22. Что пока не внедрять

- обязательную graph database;
- OGM как core dependency;
- Airflow в интерактивный pipeline;
- полностью LLM-based routing;
- свободное создание skills Planner-ом;
- передачу всего каталога skills каждому агенту;
- использование одного vector space для разных моделей;
- прямое смешивание score разных providers;
- Qdrant как единственный source of truth;
- зависимость генерации документа от доступности Qdrant;
- любые секреты в репозитории.

## 23. Зафиксированное направление

```text
Existing manifests + ArtifactContract + S-expression DSL
    +
Typed Skill Graph in YAML/Pydantic
    +
Hybrid Retrieval
    +
Qdrant Cloud retrieval projection
    +
Jina primary dense and web reranking
    +
Qdrant E5/BM25/ColBERT fallback stack
    +
LangSearch web discovery
    +
Planner escalation
    +
Instruction Compiler
```

Graph database, OGM и Airflow остаются возможными будущими адаптерами, но не входят в обязательный первый этап.
