<div align="center">
  <img src="./assets/logo.svg" alt="Academic Engine Logo" width="800"/>
  <br>
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue" alt="Python"/>
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License"/>
  <img src="https://img.shields.io/badge/Status-Beta-orange" alt="Status"/>
  <img src="https://img.shields.io/badge/Tests-Passing-brightgreen" alt="Tests"/>
  <img src="https://img.shields.io/badge/Code%20Style-Pydantic-red" alt="Pydantic"/>
</div>

# Academic Pipeline (Engine)

**Enterprise-Grade AI Documentation Engine**

Этот репозиторий представляет собой промышленное решение (Engine) для автоматической генерации академической и технической документации.

В отличие от простых скриптов, здесь реализована полноценная архитектура:
*   **State Machine Orchestrator:** Управление состоянием конвейера (Drafting -> Reviewing -> Rendering).
*   **Configurable Agents (YAML + Pydantic):** Строгая валидация конфигурации агентов.
*   **Modular Architecture:** Разделение на ядро (`core`), агентов (`agents`) и инструменты (`tools`).
*   **Dependency Management:** Использование `poetry` для воспроизводимости среды.

## Документация

Подробная техническая документация доступна в папке `docs/`:
*   [Архитектура Системы](./docs/ARCHITECTURE.md) — Обзор компонентов и диаграммы.
*   [Оркестрация](./docs/ORCHESTRATION.md) — Описание машины состояний и диаграммы последовательности.
*   [Руководство по Конфигурации](./docs/CONFIGURATION_GUIDE.md) — Настройка `agents.yaml` и схемы.
*   [Агенты и Инструменты](./docs/AGENTS_AND_TOOLS.md) — Детали реализации классов.

## Архитектура

Проект построен по принципам Clean Architecture:

1.  **Core (`src/core`):**
    *   `orchestrator.py`: Машина состояний, управляющая жизненным циклом документа.
    *   `config.py`: Загрузчик конфигураций с валидацией типов.
    *   `llm.py`: Абстракция над LLM-провайдерами (OpenAI-compatible).
2.  **Tools (`src/tools`):**
    *   `docx_renderer.py`: Модуль верстки, преобразующий структурированный контент в DOCX.
3.  **Config (`config/`):**
    *   `agents.yaml`: Декларативное описание ролей и промптов.

## Установка и запуск

Проект использует **Poetry**.

1.  **Установка зависимостей:**
    ```bash
    poetry install
    ```

2.  **Настройка окружения:**
    Создайте файл `.env` (опционально) для доступа к реальному API. Без ключа система работает в режиме MOCK (генерация заглушек).
    ```bash
    OPENAI_API_KEY=sk-...
    ```

3.  **Запуск тестов:**
    Мы гарантируем работоспособность через Unit-тесты.
    ```bash
    poetry run pytest
    ```

4.  **Запуск пайплайна (пример):**
    Создайте скрипт `main.py` или используйте тестовый запуск:
    ```python
    from src.core.orchestrator import Orchestrator

    app = Orchestrator()
    app.run_pipeline()
    ```

## Интеграция с Frontend

Для автоматической генерации форм настроек на фронтенде вы можете использовать JSON Schema, которая генерируется из Pydantic-моделей:

```bash
python scripts/export_schema.py
```

Результат будет сохранен в `config/frontend_schema.json`. Это позволяет строить UI для настройки агентов (например, через react-jsonschema-form) без дублирования логики валидации.

## Технический стек

*   **Language:** Python 3.12+
*   **Package Manager:** Poetry
*   **Validation:** Pydantic V2
*   **Document Generation:** python-docx, matplotlib
*   **Testing:** Pytest

## Disclaimer (Beta)

⚠️ **Внимание:** Данный репозиторий является Reference Implementation. Хотя базовые сценарии покрыты тестами, реальные нагрузочные тесты не проводились. В коде могут присутствовать баги, а качество генерации зависит от используемой LLM.

## Лицензия

Copyright (c) 2025 Lotargo.

Licensed under the MIT License. See [LICENSE](LICENSE) for details.
