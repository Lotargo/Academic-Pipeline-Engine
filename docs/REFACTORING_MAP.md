# Карта Рефакторинга Academic Pipeline Engine

> **Статусы:** `[ ]` — не начато · `[~]` — в работе · `[x]` — выполнено

---

## 1. Настоящая State Machine

- [x] Заменить линейный скрипт на FSM с таблицей переходов
- [x] Добавить guards (preconditions) на каждый переход
- [ ] Добавить on_enter / on_exit хуки для состояний
- [ ] Реализовать recovery при падении (возврат в предыдущее состояние)
- [ ] Вынести описание состояний и переходов в конфиг (YAML)
- [x] Написать тесты для каждого перехода

## 2. Вынос промптов в конфиг

- [x] Перенести drafting-промпты из `orchestrator.py` в `config/agents.yaml`
- [x] Перенести reviewing-промпт из `orchestrator.py` в `config/agents.yaml`
- [x] Добавить поддержку шаблонов с переменными (`{section_name}`, `{topic}`)
- [x] Убрать хардкод температуры из `llm.py:27` (брать из конфига)
- [ ] Убрать хардкод `output_filename` из `orchestrator.py`
- [ ] Добавить параметр `output_dir` в конфиг

## 3. Архитектура агентов

- [ ] Создать ABC `BaseAgent` с абстрактным методом `process()`
- [ ] Выделить `WriterAgent` с ролевой логикой (генерация секций)
- [ ] Выделить `ReviewerAgent` с парсингом структурированного фидбека
- [ ] Создать `AgentFactory` для регистрации и создания агентов
- [ ] Добавить поддержку custom-агентов через конфиг

## 4. Абстракция LLM-провайдеров

- [x] Создать ABC `LLMProvider` с методом `generate()`
- [x] Реализовать `OpenAIProvider` (текущий)
- [x] Реализовать `MockProvider` (для тестов)
- [x] Реализовать `CustomOpenAIProvider` (Ollama, LocalAI, vLLM, Groq и др.)
- [x] Реализовать `AnthropicProvider` (Claude)
- [x] Реестр провайдеров `_PROVIDER_REGISTRY` + `register_provider()` + `create_provider()`
- [x] `provider` и `base_url` поля в `AgentConfig` (выбор из YAML)
- [x] `RetryProvider` — wrapper с exponential backoff вокруг любого провайдера
- [x] `RetryConfig` в YAML: `max_retries`, `base_delay`, `max_delay`
- [x] `max_retries: 0` отключает retry (pass-through)
- [ ] Добавить circuit breaker

## 5. Dependency Injection

- [x] Передать `LLMProvider` через конструктор Orchestrator
- [x] Передать `BaseAgent` через конструктор Orchestrator
- [x] Передать `Renderer` через конструктор Orchestrator
- [x] Убрать прямые `import` и инстанцирование внутри `__init__`

## 6. Работающий Quality Gate

- [x] Проверка заполнения всех секций (`theory`, `calculation`, `conclusion`)
- [ ] Проверка минимального объёма текста (char/word count)
- [ ] Проверка валидности LaTeX-формул
- [x] Блокировка перехода в RENDERING при провале проверок
- [x] Цикл ревью: REJECT → возврат в DRAFTING → исправление

## 7. Обработка ошибок и логирование

- [x] Заменить `print()` на `logging` (с уровнями DEBUG/INFO/WARNING/ERROR)
- [x] Добавить try/except в `run_pipeline()` с корректным завершением
- [x] Добавить состояние `FAILED` для аварийного завершения
- [x] Не допускать тихих ошибок LLM (пробрасывать исключения наверх)
- [x] Добавить валидацию API-ключа на старте (не тихий mock)
- [x] Логировать каждый шаг пайплайна в структурированном виде

## 8. Чистка мёртвого кода

- [x] Удален `src/core/socket_manager.py`
- [x] Удалены `create_chart_image()`, `create_table()`
- [x] Убраны неиспользуемые импорты (`matplotlib`, `os`) из `docx_renderer.py`
- [ ] Убрать `orchestrator` секцию из `agents.yaml` (пока не нужна)
- [x] `docs/AGENTS_AND_TOOLS.md` и `AGENTS.md` — теперь различны по смыслу

## 9. Конфигурация и валидация

- [ ] Добавить `Field(ge=0.0, le=2.0)` для `temperature` в Pydantic
- [ ] Добавить валидацию модели (enum или regex)
- [ ] Добавить `StyleConfig` для шрифтов, отступов, размеров
- [ ] Добавить `PipelineConfig` для состояний и переходов
- [ ] Добавить загрузчик `.env` (python-dotenv) для `OPENAI_API_KEY`
- [ ] Добавить config reload по сигналу (SIGHUP)

## 10. Документация

- [x] Обновить `docs/CONFIGURATION_GUIDE.md` под актуальный YAML
- [x] Обновить `docs/ARCHITECTURE.md` после изменений
- [x] Обновить `docs/ORCHESTRATION.md` под настоящую FSM
- [x] Синхронизировать `AGENTS.md` с кодом
- [ ] Добавить пример `config/agents.example.yaml` с комментариями

## 11. Тесты

- [x] Покрыть `MockProvider`
- [x] Покрыть `ConfigLoader` — загрузка, pipeline sections
- [x] Покрыть `Orchestrator` — каждый state transition, invalid transition, full pipeline, FAILED
- [x] Покрыть `BaseAgent` — composition prompt, context append
- [x] Покрыть `CustomOpenAIProvider` — base_url, custom api_key env
- [x] Покрыть `AnthropicProvider` — missing key, missing package
- [x] Покрыть `create_provider()` — все типы, регистрация, ошибки
- [ ] Покрыть `DocxRenderer` — all sections, missing keys, empty content

## 12. Рендерер DOCX

- [ ] Вынести стили (шрифт, размер, отступы) в конфиг
- [ ] Сделать порядок секций настраиваемым
- [ ] Сделать заголовок документа настраиваемым
- [ ] Добавить поддержку custom-секций через конфиг
- [ ] Реализовать `create_chart_image()` (работающий)
- [ ] Реализовать `create_table()` (работающий)
- [ ] Добавить обработку ошибок при сохранении файла

---

## Легенда

```
[x] — выполнено
[~] — в работе
[ ] — не начато
```
