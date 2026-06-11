# Оркестрация и Поток Выполнения (Orchestration)

Оркестратор (`src/core/orchestrator.py`) реализует паттерн **Finite State Machine (FSM)** с таблицей переходов, guards и обработкой ошибок.

## Диаграмма Состояний (State Machine)

```mermaid
stateDiagram-v2
    [*] --> INIT

    INIT --> DRAFTING : Запуск пайплайна
    note right of DRAFTING
        Агенты-писатели генерируют
        текст по секциям из конфига
    end note

    DRAFTING --> REVIEWING : Все секции написаны
    note right of REVIEWING
        Агент-рецензент проверяет
        качество и стиль.
        REJECT → возврат в DRAFTING
    end note

    REVIEWING --> DRAFTING : REJECT (макс. 3 попытки)
    REVIEWING --> RENDERING : APPROVED

    note right of RENDERING
        Сборка бинарного файла
        DOCX из контекста
    end note

    RENDERING --> DONE : Файл сохранен

    DRAFTING --> FAILED : Ошибка генерации
    REVIEWING --> FAILED : Ошибка ревью
    RENDERING --> FAILED : Ошибка рендеринга

    FAILED --> [*]
    DONE --> [*]
```

## Последовательность Взаимодействия (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    participant Client as User/Main
    participant Orch as Orchestrator
    participant Writer as Writer Agent
    participant Reviewer as Reviewer Agent
    participant LLM as LLM Provider
    participant Tool as Docx Renderer

    Client->>Orch: run_pipeline()
    Orch->>Orch: transition_to(DRAFTING)

    rect rgb(240, 248, 255)
        note right of Orch: Этап написания (Drafting)

        loop for each section in config.pipeline.sections
            Orch->>Writer: process(section.task)
            Writer->>LLM: generate(System + User Prompt)
            LLM-->>Writer: "Section Content..."
            Writer-->>Orch: Store in Context[section.name]
        end
    end

    rect rgb(255, 240, 245)
        note right of Orch: Этап проверки (Reviewing)
        Orch->>Orch: transition_to(REVIEWING)

        loop max 3 attempts
            Orch->>Reviewer: process("Check text", Context)
            Reviewer->>LLM: generate(Validation Prompt)
            LLM-->>Reviewer: "APPROVED / REJECTED"
            Reviewer-->>Orch: Critique

            alt APPROVED
                Orch->>Orch: break
            else REJECTED and attempts remain
                Orch->>Orch: transition_to(DRAFTING)
                Orch->>Writer: process("Revise section", fixes)
                Writer-->>Orch: Updated content
                Orch->>Orch: transition_to(REVIEWING)
            else REJECTED and max attempts
                Orch->>Orch: proceed to rendering
            end
        end
    end

    rect rgb(240, 255, 240)
        note right of Orch: Этап сборки (Rendering)
        Orch->>Orch: transition_to(RENDERING)
        Orch->>Tool: render_paper(Context)
        Tool-->>Tool: Generate DOCX
        Tool-->>Orch: "Final_Paper.docx"
    end

    Orch->>Orch: transition_to(DONE)
    Orch-->>Client: Return Output Path

    rect rgb(255, 230, 230)
        note right of Orch: Обработка ошибок
        alt Any step fails
            Orch->>Orch: state = FAILED
            Orch-->>Client: PipelineError
        end
    end
```

## Логика Переходов

1.  **INIT**: Загрузка конфигурации `agents.yaml`, инициализация агентов.
2.  **DRAFTING**: Последовательный вызов `WriterAgent` для каждой секции из `config.pipeline.sections`. Результаты сохраняются в `self.context`.
3.  **REVIEWING**: `ReviewerAgent` проверяет текст. Если `REJECTED` — возврат в `DRAFTING` (до 3 попыток). Если `APPROVED` или исчерпаны попытки — переход в `RENDERING`.
4.  **RENDERING**: Передача `self.context` в `render_paper`.
5.  **DONE**: Завершение, возврат пути к файлу.
6.  **FAILED**: Любая необработанная ошибка переводит пайплайн в это состояние. Вызывается `PipelineError`.

## Таблица Переходов

| Текущее состояние | Допустимые переходы |
|---|---|
| `INIT` | `DRAFTING` |
| `DRAFTING` | `REVIEWING` |
| `REVIEWING` | `DRAFTING`, `RENDERING` |
| `RENDERING` | `DONE` |
| `DONE` | — |
| `FAILED` | — |

Невалидный переход (например, `INIT → DONE`) вызывает `InvalidTransitionError`.
