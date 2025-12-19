# Архитектура Системы (System Architecture)

Проект **Academic Pipeline Engine** построен на принципах **Clean Architecture** и модульности. Основная цель — отделить бизнес-логику (оркестрацию) от конкретных реализаций (инструменты, LLM) и конфигурации.

## Высокоуровневая диаграмма (Component Diagram)

```mermaid
graph TD
    User[User / CLI] -->|Start Pipeline| Orchestrator

    subgraph Core Layer ["Core Layer (src/core)"]
        Orchestrator[Orchestrator (State Machine)]
        Config[Config Loader]
        LLM[LLM Client (OpenAI/Mock)]
    end

    subgraph Agent Layer ["Agent Layer (src/agents)"]
        Writer[Writer Agent]
        Reviewer[Reviewer Agent]
        BaseAgent[Base Agent Class]

        Orchestrator -->|Instantiates| Writer
        Orchestrator -->|Instantiates| Reviewer
        Writer -- Inherits --> BaseAgent
        Reviewer -- Inherits --> BaseAgent
        BaseAgent -->|Calls| LLM
    end

    subgraph Tool Layer ["Tool Layer (src/tools)"]
        Renderer[Docx Renderer]
        Orchestrator -->|Sends Context| Renderer
    end

    subgraph Configuration ["Configuration"]
        YAML[agents.yaml]
        Pydantic[Pydantic Models]

        Config -->|Validates| YAML
        Config -->|Uses| Pydantic
    end
```

## Описание Компонентов

### 1. Core Layer (`src/core`)
Ядро системы. Здесь содержатся механизмы, не зависящие от конкретного документа:
*   **Orchestrator:** "Мозг" системы. Реализует машину состояний и управляет потоком выполнения.
*   **LLM Client:** Абстракция для работы с нейросетями. Поддерживает режим Mock (заглушки) для тестирования без API ключей.
*   **Config Loader:** Отвечает за загрузку и строгую типизацию настроек.

### 2. Agent Layer (`src/agents`)
Слой бизнес-логики агентов.
*   **BaseAgent:** Базовый класс, инкапсулирующий логику формирования промптов и вызова LLM.
*   **Role-Specific Agents:** (Опционально) Конкретные реализации агентов (Writer, Reviewer), конфигурируемые через YAML.

### 3. Tool Layer (`src/tools`)
Слой инструментов ("Руки" системы).
*   **Docx Renderer:** Модуль, отвечающий за физическое создание файла `.docx`. Он ничего не "придумывает", только верстает переданный ему контент.

## Структура Директорий

```text
.
├── assets/                 # Логотипы и графика
├── config/                 # Конфигурационные файлы (YAML, JSON Schema)
├── docs/                   # Техническая документация
├── scripts/                # Утилиты (например, экспорт схемы)
├── src/
│   ├── agents/             # Реализация агентов
│   ├── core/               # Ядро системы (Оркестратор, Конфиг, LLM)
│   └── tools/              # Инструменты генерации
├── tests/                  # Unit-тесты
├── pyproject.toml          # Управление зависимостями (Poetry)
└── README.md               # Точка входа
```
