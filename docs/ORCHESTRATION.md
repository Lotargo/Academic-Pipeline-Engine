# Оркестрация и Поток Выполнения (Orchestration)

Оркестратор (`src/core/orchestrator.py`) реализует паттерн **Finite State Machine (FSM)**. Это гарантирует детерминированность процесса: генерация документа всегда проходит через строго определенные этапы.

## Диаграмма Состояний (State Machine)

```mermaid
stateDiagram-v2
    [*] --> INIT

    INIT --> DRAFTING : Запуск пайплайна
    note right of DRAFTING
        Агенты-писатели генерируют
        текст по секциям (Theory, Calc...)
    end note

    DRAFTING --> REVIEWING : Генерация завершена
    note right of REVIEWING
        Агент-рецензент проверяет
        качество и стиль
    end note

    REVIEWING --> RENDERING : Валидация пройдена
    note right of RENDERING
        Сборка бинарного файла
        DOCX из контекста
    end note

    RENDERING --> DONE : Файл сохранен
    DONE --> [*]
```

## Последовательность Взаимодействия (Sequence Diagram)

Ниже показан типичный сценарий выполнения задачи:

```mermaid
sequenceDiagram
    autonumber
    participant Client as User/Main
    participant Orch as Orchestrator
    participant Writer as Writer Agent
    participant Reviewer as Reviewer Agent
    participant LLM as LLM Client
    participant Tool as Docx Renderer

    Client->>Orch: run_pipeline()
    Orch->>Orch: Set State: DRAFTING

    rect rgb(240, 248, 255)
        note right of Orch: Этап написания (Drafting)

        Orch->>Writer: process("Draft Chapter 1")
        Writer->>LLM: generate(System + User Prompt)
        LLM-->>Writer: "Theory Content..."
        Writer-->>Orch: Store in Context['theory']

        Orch->>Writer: process("Draft Chapter 2")
        Writer->>LLM: generate(...)
        LLM-->>Writer: "Calculation Content..."
        Writer-->>Orch: Store in Context['calculation']
    end

    rect rgb(255, 240, 245)
        note right of Orch: Этап проверки (Reviewing)
        Orch->>Orch: Set State: REVIEWING

        Orch->>Reviewer: process("Review text", Context)
        Reviewer->>LLM: generate(Validation Prompt)
        LLM-->>Reviewer: "Approved / Issues"
        Reviewer-->>Orch: Feedback
    end

    rect rgb(240, 255, 240)
        note right of Orch: Этап сборки (Rendering)
        Orch->>Orch: Set State: RENDERING

        Orch->>Tool: render_paper(Context)
        Tool-->>Tool: Generate DOCX
        Tool-->>Orch: "Final_Paper.docx"
    end

    Orch->>Orch: Set State: DONE
    Orch-->>Client: Return Output Path
```

## Логика Переходов

1.  **INIT**: Загрузка конфигурации `agents.yaml`, инициализация агентов и подключение к LLM.
2.  **DRAFTING**: Последовательный вызов `WriterAgent` для каждой секции документа. Результаты сохраняются в словарь `self.context`.
3.  **REVIEWING**: (Опционально) Отправка накопленного контекста агенту `ReviewerAgent`. В текущей версии MVP это линейный шаг, но архитектура позволяет реализовать цикл "Draft -> Review -> Fix -> Draft".
4.  **RENDERING**: Передача словаря `self.context` в чистую функцию `render_paper`.
5.  **DONE**: Завершение работы, возврат пути к файлу.
