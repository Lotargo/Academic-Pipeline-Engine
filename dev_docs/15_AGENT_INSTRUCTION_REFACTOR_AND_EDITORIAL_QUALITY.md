# 15. Agent Instruction Refactor and Editorial Quality

## Статус

Реализация завершена; документ сохраняет архитектурные решения и критерии приёмки.

### Checkpoint (2026-07-12)

- P0.1 выполнен: runtime prompt содержит ArtifactContract один раз, а
  AgentContract рендерится как role-specific delta со ссылкой на активный contract.
- P0.2 выполнен для template manifest: Writer не получает reviewer rubric,
  Planner не получает output/export constraints, Researcher не получает
  нерелевантные template-секции.
- P0.3--P0.5 начаты в `config/agents.example.yaml`: абстрактные стилевые запреты
  заменены наблюдаемыми критериями, универсальные `3-5 sections` удалены,
  Reviewer использует severity-based решение.
- Regression: `test_config`, `test_prompt_manifest_resolver`,
  `test_prompt_enhance`, `test_orchestrator` — 88 passed.
- P0.8 выполнен: deterministic leakage gate блокирует runtime contract,
  self-critique, GREP и REPLACE protocol markers; профильная проверка — 50 passed.
- P0.6 выполнен для Writer: обычный self-critique возвращает exact-text patches,
  неоднозначные замены отклоняются, незатронутый текст сохраняется; полный system
  prompt и document context повторно не передаются.
- P0.7 выполнен для первичного drafting: legacy `SectionPrompt` компилируется в
  типизированный `SectionBrief`, protocol markers отбрасываются, Writer template
  больше не читает raw `section.instruction`.
- Regression для P0.6--P0.7 и смежных pipeline contracts — 162 passed.
- P0-аудит завершён: patch revision, optional revision и fallback revision также
  используют compiled `SectionBrief`; полный system prompt удалён из всех
  self-critique ролей; абстрактные style checks в active adapters заменены
  наблюдаемыми редакционными критериями. Объединённая regression — 147 passed.
- Оставшийся `section.instruction` используется только в Planner input для legacy
  структуры и будет заменён строгой схемой в P1.
- P1.9--P1.10 выполнены: добавлен типизированный role-scoped
  `InstructionCompiler` с отдельным `GatePlan`; Writer bundle получает только
  собственный `SectionBrief`, authoring constraints и разрешённые ledger inputs,
  тогда как export mechanics остаются в Exporter bundle.
- `SectionBrief` теперь валидирует coverage matrix, назначает текущей секции
  owned responsibilities, помечает чужие responsibilities как
  `must_not_repeat` и выбирает принадлежащие секции ClaimCard, SourceCard и
  CalculationCard IDs. Обычный drafting и optional revision используют один
  compiler path; legacy вызов без coverage остаётся совместимым.
- Regression P1.9--P1.10 и смежных prompt/orchestrator/revision contracts — 81 passed;
  полный suite — 613 passed, 3 skipped.
- P1.11 выполнен: Planner prompt возвращает строгий JSON `DocumentPlan` с
  типизированными sections, coverage, evidence/calculation needs и transitions;
  все section references и лишние поля валидируются. Legacy prose из custom
  adapters изолирован в compatibility fallback и не становится инструкцией.
- Reviewer prompt теперь имеет один непротиворечивый JSON protocol.
  `StructuredReviewPayload` запрещает лишние поля, неизвестные role/severity/code
  и решения `approved`, противоречащие material issues; старые `APPROVED` и
  `REJECTED` поддерживаются только compatibility parser-ом.
- Профильная regression P1.11 и смежных contracts — 83 passed; полный suite —
  617 passed, 3 skipped.
- P1.12 выполнен: `EvidenceReviewer` и `EditorialReviewer` используют общий
  нейтральный JSON protocol, но разные prompt builders и взаимоисключающие
  rubric scopes. Evidence получает SourceCard/ClaimCard/CalculationCard и
  coverage state, не оценивает стиль; Editorial получает coverage/terminology,
  не видит evidence registries и не оценивает числа или источники.
- Specialized role фиксируется схемой: JSON-ответ с чужим `reviewer_role`
  отклоняется. Оба reviewer-а подключены к generation и selective optional
  revision; factory создаёт их как `ReviewerAgent`. Example config содержит
  отдельные настройки ролей вместо одного смешанного prompt.
- Профильная regression P1.12 и смежных contracts — 112 passed; полный suite —
  622 passed, 3 skipped.
- P1.13 выполнен: Researcher возвращает валидируемые `SourceCard` с excerpt,
  reliability notes, supported claims и conflicts; Writer/Planner получают только
  карточки и зарегистрированные claims, а не сырой crawler dump.
- P1.14 выполнен: активный enhancement path заменён однопроходным
  `BriefNormalizer`, который возвращает строгий `NormalizedBrief` и не проектирует
  Writer prompt. Старый `PromptEnhancer` оставлен только как compatibility API.
- P1.15 выполнен: Writer system prompt больше не содержит текстовый GREP-договор.
  Пассивный parser старого `USE_GREP` ответа сохранён для cached providers, но
  активные prompts его не рекламируют.
- P2.16 выполнен: attachment типа `style_sample` компилируется в наблюдаемый
  `StyleProfile`; профиль видят только Writer и EditorialReviewer. Биографические
  факты, мнения и опыт из профиля не выводятся.
- P2.17 выполнен: `config/instruction_policies.yaml` хранит skill IDs и отдельные
  role fragments; Planner выбирает IDs, а compiler раскрывает только фрагменты
  текущей роли.
- P2.18 и P2.20 выполнены: bundle версии `2.0` содержит token estimate, budget
  status и стабильный SHA-256 diagnostic hash. Реально использованные bundles
  сохраняются как `instruction_bundle` runtime snapshots.
- P2.19 выполнен: добавлены воспроизводимый routing/editorial benchmark и CLI
  `scripts/run_core15_benchmark.py`. Зафиксированный прогон: routing 10/10;
  compiled variants имеют 0 leakage/role-contamination/abstract-style markers;
  анонимизированный deterministic editorial rubric предпочёл схему с
  `SectionBrief` и specialized reviewers (1123 score против 0 у legacy fixture).
- Итоговая приёмка CORE-15: профильный integration-срез — 129 passed; полный
  Python suite — 630 passed, 3 skipped; TypeScript typecheck и production UI build
  прошли. Benchmark зафиксирован в `dev_docs/core15_benchmark_result.json`.

Документ продолжает решения из заметок №13 и №14. Он фиксирует проблемы текущих system prompts, task templates, template manifests, agent adapters и self-critique, а также предлагает новую схему компиляции инструкций.

Цель изменений состоит не в обходе AI-детекторов и не в имитации человеческих ошибок. Система должна уменьшать количество воспроизводимых машинных шаблонов, служебных следов, пустых переходов, чрезмерно ровной структуры и повторяющихся выводов. Итоговый текст должен выглядеть естественно потому, что он конкретен, внутренне согласован, соответствует задаче и сохраняет реальный пользовательский замысел.

Нельзя гарантировать, что проверяющий или автоматический классификатор не назовёт качественный текст сгенерированным. Можно устранить признаки, которые создаёт сама архитектура APE и которые дают проверяющему обоснованные причины для такого вывода.

## 1. Что было просмотрено

При анализе учитывались следующие уровни инструкций:

- `config/agents.example.yaml`;
- `config/document_templates.yaml`;
- `academic_pe/core/prompting.py`;
- `academic_pe/core/prompt_manifest_resolver.py`;
- `academic_pe/agent_adapters/*`;
- `academic_pe/agents/writer.py`;
- `academic_pe/agents/researcher.py`;
- `academic_pe/agents/self_critique.py`;
- artifact contract и agent contract, добавляемые во время выполнения;
- section instructions и document plan, передаваемые Writer;
- reviewer feedback и patch-протоколы.

## 2. Текущий стек инструкций

Один вызов Writer может одновременно получить:

1. базовый `system_prompt`;
2. role и task из `PromptManifest`;
3. `style_contract`;
4. `review_rubric`;
5. `output_constraints`;
6. guidance из `agent_adapters/writer.py`;
7. полный ArtifactContract в S-expression;
8. AgentContract, повторно содержащий ArtifactContract;
9. `DEFAULT_DRAFT_TEMPLATE`;
10. `section.instruction`;
11. исходную тему пользователя;
12. исходные инструкции пользователя;
13. document plan;
14. уже написанные секции;
15. GREP-протокол;
16. Academic Mode overlay;
17. self-critique prompt, повторно содержащий полный system prompt, task, context и draft.

Количество текста само по себе не обеспечивает точность. При пересечении правил модель начинает усреднять их, отдавать приоритет наиболее повторяемым формулировкам и производить безопасный, но шаблонный текст.

## 3. Проблемы, связанные с текущими промптами

### 3.1. Дублирование контрактов

`PromptManifestResolver` отдельно добавляет `[Active Artifact Contract]`, после чего добавляет `[Active Agent Contract]`, внутри которого снова находится ArtifactContract.

Последствия:

- один и тот же замысел повторяется дважды;
- растёт prompt budget;
- общие ограничения начинают доминировать над задачей секции;
- модель чаще воспроизводит терминологию внутренних контрактов;
- сложнее определить, какое правило было реально применено.

ArtifactContract должен присутствовать один раз. AgentContract должен содержать только role-specific delta и ссылку на artifact contract.

### 3.2. Review rubric передаётся агентам, которым она не нужна

Сейчас `style_contract`, `review_rubric` и `output_constraints` добавляются без полноценного role-scoping.

Writer не должен получать полный список reviewer criteria. Researcher не должен получать требования к финальной литературной форме. Planner не должен получать экспортные детали, если они не влияют на структуру.

Когда Writer видит rubric, он начинает писать текст как ответ на чек-лист. Это приводит к симметричным абзацам, явному закрытию каждого критерия и повторению формулировок из rubric.

### 3.3. Абстрактные указания «natural», «human» и «avoid AI-style filler»

Текущие prompts многократно используют формулировки:

- natural human style;
- AI-style filler;
- machine-like transitions;
- artificial smoothness;
- generic AI filler;
- natural student register.

Эти понятия не имеют однозначного операционного значения. Разные модели интерпретируют их по-разному. Часто модель отвечает чрезмерной осторожностью: убирает индивидуальные формулировки, делает предложения одинаково аккуратными и создаёт ещё более узнаваемый машинный стиль.

Инструкция должна описывать наблюдаемое поведение, а не абстрактную «человечность».

Плохо:

```text
Write naturally and avoid AI-style prose.
```

Лучше:

```text
State the section's claim directly. Remove sentences that only announce what the
section will discuss. Do not repeat the same conclusion in the opening and closing
paragraphs. Use transitions only when the logical relation is not already clear.
```

### 3.4. Planner принудительно создаёт 3–5 секций

В базовой инструкции Planner закреплено требование создавать 3–5 логически последовательных секций или units.

Это полезно как fallback, но вредно как универсальный закон. Короткая записка может требовать двух частей, техническая инструкция — семи шагов, а связное эссе — вообще не нуждаться в видимых заголовках.

Принудительная одинаковая структура создаёт повторяемый отпечаток APE:

- введение;
- несколько сбалансированных блоков;
- обязательная альтернатива или ограничения;
- заключение с повтором всех тезисов.

Planner должен сначала определить минимальную естественную структуру артефакта и только затем создавать секции.

### 3.5. Шаблонные задания для заключений

В `document_templates.yaml` часто используются инструкции вида:

```text
Summarize findings, limitations, and implications.
Summarize the result and practical implications.
Synthesize the argument.
Finish with a concise summary.
```

Такие задания почти гарантируют типичное заключение, которое повторяет содержание предыдущих разделов и завершает текст универсальной фразой о значимости темы.

Заключение должно иметь конкретную функцию, например:

- ответить на исходный вопрос;
- зафиксировать принятое решение;
- назвать главный предел применимости;
- указать следующий технический шаг;
- завершить аргумент без нового пересказа.

Не каждый документ нуждается в отдельном заключении.

### 3.6. Повторение ограничений в нескольких слоях

Academic Mode просит добавлять ограничения там, где они уместны. Та же идея повторяется в:

- Planner prompt;
- Writer prompt;
- template conclusion instruction;
- self-critique;
- Reviewer prompt;
- artifact requirements.

В результате ограничения могут появиться в методе, анализе, отдельном блоке и заключении.

Ограничения должны иметь владельца в coverage matrix. Остальные секции могут ссылаться на них одной фразой, но не создавать полноценный повторный блок.

### 3.7. Section instructions могут утекать в итоговый текст

`DEFAULT_DRAFT_TEMPLATE` передаёт Writer непосредственно:

- `section.instruction`;
- original user topic;
- original user instructions;
- labels continuation mode;
- semantic role;
- heading policy.

При большом количестве служебного текста модель может повторить его дословно или близко к тексту. Именно так в готовом документе возникают фразы наподобие:

- «строго в тексте»;
- «без ссылки на несуществующий номер»;
- «в данном разделе необходимо»;
- пояснения о том, как была построена секция.

Writer не должен видеть сырые служебные инструкции, если их можно предварительно скомпилировать в типизированный `SectionBrief`.

### 3.8. GREP-протокол находится внутри Writer prompt

Writer получает маркеры:

- `[GREP TOOL AVAILABLE]`;
- `USE_GREP:`;
- `[Grep Call Turn ...]`;
- текстовые ответы инструмента.

Это увеличивает риск утечки протокольных строк. GREP следует оформить как настоящее tool call или отдельный preflight-проход, а не как текстовый договор внутри system prompt.

### 3.9. Self-critique может чрезмерно сглаживать текст

Self-critique получает:

- полный system prompt;
- полный task;
- context;
- draft;
- дополнительные academic rules.

После этого ему предлагается «repair the draft in one pass». Даже если исходный текст был приемлемым, второй проход той же или близкой модели часто:

- выравнивает длину предложений;
- заменяет конкретные обороты на безопасные общие;
- добавляет формальные переходы;
- повторно вставляет ограничения;
- переписывает больше текста, чем требуется;
- стирает локальную авторскую вариативность.

Self-critique не должен быть универсальным парафразером. Его следует ограничить диагностированными проблемами и минимальными patch-операциями.

### 3.10. Reviewer получает конфликтующие установки

Reviewer одновременно назван строгим и получает инструкцию `Prefer APPROVED`, когда оставшиеся проблемы незначительны.

Также Reviewer должен искать:

- фактические ошибки;
- структуру;
- цифры;
- язык;
- форматирование;
- AI-style filler;
- artificial smoothness;
- repeated syntactic patterns.

Один универсальный проход не может одинаково надёжно решать все эти задачи. При этом свободный текст `REJECTED` недостаточно точно определяет границы исправления.

Reviewer должен возвращать типизированные issue records и проверять ограниченный набор критериев за один проход.

### 3.11. Example Generator обучает интерфейс чрезмерно подробным запросам

Инструкция Example Generator требует, чтобы примеры были подробными, профессиональными и не краткими. Эти примеры затем становятся образцом поведения пользователя и усиливают общий объём инструкций.

Примеры в интерфейсе должны различаться по детализации:

- короткий естественный запрос;
- средний запрос с несколькими ограничениями;
- подробный профессиональный brief.

Система должна уметь работать с каждым уровнем, а не приучать пользователя писать внутреннюю спецификацию пайплайна.

### 3.12. Prompt Enhancer расширяет запрос вместо его нормализации

Prompt Enhancer содержит собственный contract, agent contract, девять правил и внутренний candidate-and-critic process. Это может приводить к созданию длинной инструкции, которая затем повторно проходит через Planner и Writer.

Enhancer должен:

- извлечь явные требования;
- нормализовать неоднозначные поля;
- сохранить пользовательские формулировки;
- не добавлять критерии качества, уже известные системе;
- не превращать простой запрос в техническое задание.

## 4. Что нельзя исправить промптами

Следующие проблемы требуют кода, состояния и детерминированных проверок:

- повреждение Unicode и удаление русской буквы `В`;
- повторная нумерация таблиц, формул и рисунков;
- локальные библиографии с разным значением `[1]`;
- проверка существования источников;
- пересчёт формул и сценариев;
- проверка единиц измерения;
- хранение терминологии;
- разрешение перекрёстных ссылок;
- prompt leakage detection;
- запрет протокольных маркеров;
- сборка секций в единый документ.

Нельзя компенсировать отсутствие ledger инструкцией «будь внимателен к нумерации». Нельзя компенсировать отсутствие calculation audit инструкцией «не допускай ошибок в расчётах».

## 5. Целевая архитектура инструкций

Предлагается добавить `InstructionCompiler`.

```text
User Request
    + ArtifactContract
    + SkillPlan
    + Template
    + DocumentLedger
    + SectionBrief
        |
        v
InstructionCompiler
        |
        +-- PlannerInstructionBundle
        +-- ResearcherInstructionBundle
        +-- WriterInstructionBundle
        +-- ReviewerInstructionBundle
        +-- ExporterInstructionBundle
```

Каждый агент получает только необходимые ему данные.

## 6. Иерархия приоритетов

Предлагаемый порядок:

1. явные текущие требования пользователя;
2. подтверждённый ArtifactContract;
3. выбранный SkillPlan;
4. факты и ограничения DocumentLedger;
5. SectionBrief текущей секции;
6. artifact-specific style guidance;
7. безопасные defaults.

Review rubric, export checks и детерминированные gates не должны конкурировать с Writer task.

## 7. Категории инструкций

```python
class CompiledInstructionBundle(BaseModel):
    role: str
    objective: str
    hard_constraints: list[Constraint]
    content_inputs: list[ContentReference]
    section_brief: SectionBrief | None
    style_profile: StyleProfile | None
    selected_skill_guidance: list[SkillInstruction]
    output_protocol: OutputProtocol
```

Детерминированные проверки хранятся отдельно:

```python
class GatePlan(BaseModel):
    gate_ids: list[str]
```

Writer не нужно сообщать каждый regex, которым потом будет проверяться его вывод.

## 8. Правила составления хорошей инструкции

### 8.1. Описывать функцию текста

Плохо:

```text
Write a professional and natural analysis.
```

Лучше:

```text
Explain why the selected approach is appropriate for the stated constraints.
Compare it with the nearest practical alternative and name the condition under
which that alternative becomes preferable.
```

### 8.2. Использовать проверяемые требования

Плохо:

```text
Avoid generic AI wording.
```

Лучше:

```text
Delete sentences that only announce the structure of the section. Do not end more
than one paragraph with a broad statement about importance, relevance, or future
potential. Every quantitative claim must reference a SourceCard or CalculationCard.
```

### 8.3. Предпочитать положительные указания

Не нужно перечислять десятки запрещённых фраз. Лучше определить:

- основной тезис;
- доказательство;
- необходимые примеры;
- допустимые выводы;
- функцию последнего абзаца.

Короткий список критических запретов остаётся допустимым.

### 8.4. Не требовать одинаковой структуры абзацев

Инструкция не должна заставлять каждый блок иметь:

1. тезис;
2. объяснение;
3. пример;
4. мини-вывод.

Такая симметрия быстро становится заметной. Структура должна зависеть от содержания: определение может занимать одно предложение, сложное возражение — несколько абзацев.

### 8.5. Не требовать искусственной вариативности

Запрещено добавлять требования:

- случайно менять длину предложений;
- искусственно повышать perplexity или burstiness;
- вставлять опечатки;
- добавлять разговорные слова без контекста;
- намеренно нарушать логику;
- делать текст «undetectable»;
- писать «как человек» без определения конкретного стиля.

Вариативность должна появляться из разных смысловых функций, а не из случайности.

### 8.6. Сохранять реальный пользовательский голос

Если пользователь предоставил образец собственного текста, можно извлечь `StyleProfile`:

- уровень формальности;
- средняя плотность терминов;
- отношение к спискам и заголовкам;
- предпочтительная длина абзацев;
- допустимость первого лица;
- характер переходов;
- типичные способы объяснения.

Нельзя выдумывать личный опыт, биографические факты, мнения или наблюдения, которых пользователь не предоставлял.

## 9. Новый SectionBrief

```python
class SectionBrief(BaseModel):
    section_id: str
    purpose: str
    owned_claims: list[str]
    required_inputs: list[str]
    allowed_sources: list[str]
    calculations: list[str]
    terms_to_preserve: list[str]
    must_not_repeat: list[str]
    incoming_transition: str | None
    outgoing_handoff: str | None
    visible_heading: bool
    output_form: str
```

Пример:

```json
{
  "section_id": "financial_model",
  "purpose": "Explain whether the project remains viable under the stated assumptions.",
  "owned_claims": ["CLAIM-014", "CLAIM-015"],
  "required_inputs": ["CALC-003", "SRC-008"],
  "terms_to_preserve": ["base scenario", "payback period"],
  "must_not_repeat": ["general project motivation", "full methodology summary"],
  "incoming_transition": "Continue from the operational assumptions without restating them.",
  "outgoing_handoff": "Leave risk interpretation to the risk section.",
  "visible_heading": true,
  "output_form": "two analytical paragraphs followed by the scenario table interpretation"
}
```

Этот формат уменьшает повторения лучше, чем инструкция «не повторяйся».

## 10. Переработка Planner

Planner не должен писать подробные литературные инструкции каждой секции. Он должен построить структуру ответственности.

Обязательный структурированный результат:

```python
class DocumentPlan(BaseModel):
    central_question: str | None
    central_claim: str | None
    artifact_structure: list[PlannedSection]
    coverage_matrix: dict[str, list[str]]
    terminology: dict[str, str]
    evidence_requirements: list[EvidenceNeed]
    calculation_requirements: list[CalculationNeed]
    transition_map: list[TransitionEdge]
    forbidden_duplications: list[str]
```

Из текущей инструкции Planner следует убрать универсальное требование `3-5 sections`.

Planner должен:

- выбирать минимальную достаточную структуру;
- отмечать внутренние blocks отдельно от видимых headings;
- назначать владельца тезисам, ограничениям и выводам;
- не добавлять counterpoint, limitations или conclusion без функциональной причины;
- возвращать JSON, а не свободный Markdown plan;
- выбирать skills по ID, а не сочинять новые правила.

## 11. Переработка Researcher

Researcher должен возвращать не связный пересказ, а карточки:

```python
class SourceCard(BaseModel):
    source_id: str
    title: str
    url: str
    publication_date: str | None
    source_type: str
    reliability_notes: list[str]
    supported_claims: list[str]
    relevant_excerpt: str
    conflicts_with: list[str]
```

Его инструкции должны разделять:

- формирование поисковых запросов;
- поиск через LangSearch;
- reranking;
- чтение исходных страниц;
- извлечение фактов;
- конфликт источников.

Фразы вроде «предпочитай надёжные источники» недостаточно. Нужны source policies по типу задачи и явные основания для отклонения результата.

## 12. Переработка Writer

Writer должен получать компактный bundle:

```text
Role
Artifact summary
Current section purpose
Owned claims
Required SourceCards / CalculationCards
Continuity handoff
StyleProfile
Output protocol
```

Writer не должен получать:

- полный reviewer rubric;
- полный список export gates;
- дублирующий ArtifactContract;
- внутренние confidence scores;
- raw search findings;
- инструкции других агентов;
- полный prompt enhancer trace;
- длинный список AI-related запретов.

Пример целевой Writer instruction:

```text
Write the final text for section `financial_model`.

Purpose: determine whether the base scenario is economically viable.
Use: CALC-003 and SRC-008 only for quantitative claims.
Preserve terms: base scenario, payback period.
Do not restate the project motivation or the full methodology.
Begin from the operational assumptions already established in the previous section.
End by identifying the single variable that most changes the conclusion; the risk
section will discuss mitigation separately.
Return final section Markdown only.
```

Здесь нет просьбы «звучать как человек», но результат будет менее шаблонным благодаря ясной смысловой ответственности.

## 13. Переработка Reviewer

Предпочтительно разделить Reviewer на два прохода:

### EvidenceReviewer

Проверяет:

- связь claims с SourceCards;
- числа с CalculationCards;
- даты;
- противоречия;
- чрезмерные выводы;
- единицы измерения.

### EditorialReviewer

Проверяет:

- функцию секций;
- смысловые повторы;
- пустые переходы;
- одинаковые начала и окончания абзацев;
- повторное введение тезиса;
- шаблонное заключение;
- служебный текст;
- несоответствие пользовательскому StyleProfile.

Результат должен быть структурированным:

```json
{
  "approved": false,
  "issues": [
    {
      "code": "REDUNDANT_CONCLUSION",
      "section": "conclusion",
      "line_start": 12,
      "line_end": 18,
      "severity": "major",
      "message": "The paragraph repeats the introduction without answering the central question.",
      "repair_scope": "replace_lines"
    }
  ]
}
```

Инструкция `Prefer APPROVED` должна быть заменена формальным правилом severity:

- blocker или major → revision required;
- только minor → ready with warnings;
- issues отсутствуют → approved.

## 14. Переработка self-critique

Рекомендуемый режим:

- выключен для полного свободного переписывания хорошего draft;
- включён для проверки protocol compliance;
- включён для исправления конкретных issue codes;
- patch-first;
- не получает полный system prompt;
- не добавляет новые идеи и ограничения;
- не переписывает незатронутые абзацы.

Новый процесс:

```text
Draft
  -> deterministic preflight
  -> compact diagnostic issues
  -> minimal patch
  -> verify only patched ranges
```

Self-critique должен видеть скомпилированные active constraints, а не все исходные слои инструкций.

## 15. Переработка Prompt Enhancer

Prompt Enhancer лучше переименовать в `BriefNormalizer`.

Он должен возвращать:

```python
class NormalizedBrief(BaseModel):
    topic: str
    artifact_hints: list[str]
    explicit_requirements: list[str]
    explicit_forbids: list[str]
    audience: str | None
    tone: str | None
    length_hint: str | None
    unresolved_ambiguities: list[str]
```

Он не должен писать будущий Writer prompt целиком. Planner и InstructionCompiler используют структурированный brief дальше.

## 16. Prompt budget

Начальные ориентиры, которые необходимо проверить benchmark-тестами:

- Writer role/system guidance: до 250–400 токенов;
- SectionBrief и content references: до 800–1200 токенов без самих источников;
- Reviewer criteria: до 300–500 токенов на один специализированный проход;
- Researcher source policy: до 400–600 токенов;
- contract representation: одно компактное представление без дублирования;
- skill guidance: только выбранные skills, без полного каталога.

Это не жёсткие продуктовые лимиты. Они нужны как сигнал, что instruction bundle стал чрезмерным.

## 17. Проверяемые признаки редакционного качества

Вместо задачи «не выглядеть как ИИ» использовать измеримые checks:

- нет служебных маркеров и prompt overlap;
- нет нескольких вступлений или заключений;
- один тезис не формулируется одинаково более одного раза;
- каждый абзац выполняет отдельную функцию;
- переходы отражают реальную логическую связь;
- отсутствуют абзацы только о важности или актуальности темы;
- нет обязательного симметричного перечисления плюсов и минусов без основания;
- длина разделов определяется их функцией, а не одинаковой квотой;
- количественные утверждения имеют источник или расчёт;
- вывод отвечает на поставленный вопрос;
- стиль соответствует реальному user brief или предоставленному образцу;
- отсутствуют выдуманные личные наблюдения.

## 18. Чего не следует делать

Не добавлять в prompts:

- «обмани AI detector»;
- «сделай текст неотличимым от человеческого»;
- «увеличь perplexity»;
- «добавь burstiness»;
- «вставь несколько ошибок»;
- «используй случайные разговорные выражения»;
- «перепиши через несколько моделей»;
- «скрой, что текст был сгенерирован»;
- «подражай конкретному живому автору без предоставленного пользовательского образца и разрешения».

Эти подходы ухудшают качество, создают новые повторяемые шаблоны и не решают проблемы доказательности.

## 19. Evaluation

AI-detector score не должен быть acceptance gate.

Основной benchmark должен содержать реальные запросы разных типов:

- академический отчёт;
- курсовая секция;
- техническая записка;
- README;
- аналитическая записка;
- школьное сочинение;
- продолжение существующего документа;
- точечная ревизия;
- документ с расчётами;
- документ с веб-источниками.

Для каждого результата слепой Reviewer оценивает:

- конкретность;
- связность;
- доказательность;
- повторяемость;
- естественность структуры;
- соответствие аудитории;
- наличие служебных следов;
- объём необязательного текста;
- сохранность пользовательских формулировок;
- корректность заключения.

Сравниваются варианты:

```text
current prompts
compiled minimal prompts
compiled prompts + SectionBrief
compiled prompts + SectionBrief + specialized reviewers
```

Дополнительно сохраняются:

- prompt token count;
- output token count;
- число revision loops;
- число затронутых строк при исправлении;
- количество deterministic gate failures;
- blind reviewer preference.

## 20. План внедрения

### P0

1. Удалить дублирование ArtifactContract внутри AgentContract prompt.
2. Добавить role-scoping для `style_contract`, `review_rubric` и `output_constraints`.
3. Заменить абстрактные `human/natural/AI-style` указания на наблюдаемые criteria.
4. Убрать универсальное требование Planner создавать 3–5 секций.
5. Убрать `Prefer APPROVED`, ввести severity-based решение.
6. Ограничить self-critique минимальными patch-операциями.
7. Не передавать raw section instructions в итоговый Writer prompt без компиляции.
8. Добавить regression tests на prompt leakage и protocol markers.

### P1

9. Ввести `InstructionCompiler`.
10. Ввести `SectionBrief` и coverage matrix.
11. Перевести Planner и Reviewer на строгие JSON-схемы.
12. Разделить EvidenceReviewer и EditorialReviewer.
13. Перевести Researcher на SourceCards.
14. Переименовать Prompt Enhancer в BriefNormalizer и сократить его ответственность.
15. Убрать текстовый GREP-протокол из Writer system prompt.

### P2

16. Добавить опциональный `StyleProfile` из пользовательского образца.
17. Подключить skills как role-specific instruction fragments.
18. Создать prompt budget telemetry.
19. Провести routing и editorial benchmark.
20. Версионировать instruction bundles и сохранять их диагностический hash.

## 21. Предлагаемые файлы

```text
academic_pe/instructions/models.py
academic_pe/instructions/compiler.py
academic_pe/instructions/bundles.py
academic_pe/instructions/style_profile.py
academic_pe/instructions/section_brief.py
academic_pe/review/evidence_reviewer.py
academic_pe/review/editorial_reviewer.py
config/instruction_policies.yaml
config/reviewer_policies.yaml
tests/test_instruction_compiler.py
tests/test_instruction_budget.py
tests/test_prompt_leakage_regressions.py
tests/test_section_brief_coverage.py
```

## 22. Критерии готовности

Переработка считается успешной, когда:

- ArtifactContract попадает в prompt один раз;
- каждый агент получает только role-specific instructions;
- Writer не видит reviewer rubric и export gates;
- Planner не создаёт одинаковое число секций для всех артефактов;
- ограничения и выводы имеют владельца в coverage matrix;
- self-critique не переписывает незатронутый текст;
- Reviewer возвращает структурированные issues;
- prompt leakage блокируется детерминированно;
- blind evaluation предпочитает новую схему текущей;
- качество источников и расчётов не ухудшается;
- система не использует искусственные ошибки и не обещает обход автоматических классификаторов.

## 23. Итоговое решение

Основная причина машинного отпечатка состоит не только в выборе модели. Текущая система многократно сообщает каждому агенту одни и те же общие правила, заставляет Planner создавать похожие структуры и применяет универсальный self-critique, который дополнительно сглаживает текст.

Целевая схема:

```text
Typed user brief
    + ArtifactContract
    + SkillPlan
    + DocumentLedger
    + SectionBrief
        |
        v
Role-scoped InstructionCompiler
        |
        +-- compact Planner bundle
        +-- SourceCard Researcher bundle
        +-- focused Writer bundle
        +-- specialized Reviewer bundles
        +-- deterministic gates outside prompts
```

Качественный текст должен появляться не из просьбы «писать как человек», а из точного распределения ответственности, конкретных фактов, контролируемых источников, естественной для артефакта структуры и минимального количества непротиворечивых инструкций.
