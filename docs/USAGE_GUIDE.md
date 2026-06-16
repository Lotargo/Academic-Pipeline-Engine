# Как Работать с Academic Pipeline Engine

Этот гайд написан для человека, который хочет понять проект без чтения кода. Он объясняет, что делает система, какие режимы есть, когда включать research/OCR, зачем нужен sandbox и чем APE отличается от обычного LLM-чата.

## 1. Главная Модель Работы

Academic Pipeline Engine принимает пользовательский brief и превращает его в управляемый pipeline:

```text
brief
  -> artifact detection
  -> template / manifest / contract
  -> planning
  -> optional research / OCR
  -> drafting
  -> review and deterministic gates
  -> saved draft
  -> explicit DOCX/PDF export
```

Главная разница с обычным prompt-based генератором: система не просит модель "просто написать текст". Она сначала определяет, какой артефакт нужен, какие ограничения действуют, какой стиль надо сохранить и какие проверки применить.

## 2. Что Можно Создавать

Проект не ограничен academic papers.

Поддерживаемые сценарии:

- academic paper, report, RGR/coursework-like document;
- technical README and operational brief;
- school essay or composition;
- plan document;
- creative story, fairy tale, poem;
- continuation or revision of an existing work;
- documents with tables, formulas, charts and calculations;
- source-aware briefs using OCR attachments or web research.

Если тип документа неизвестен, система использует preserve-first fallback: сохраняет очевидный формат запроса и не превращает его в научную статью автоматически.

## 3. Два Режима Написания

### Standard Mode

Standard mode нужен, когда важнее естественный жанр и пользовательская форма.

Подходит для:

- рассказов, стихов и creative writing;
- школьных работ;
- README и технических инструкций;
- планов, заметок, отчетов без тяжелой аналитики;
- продолжения уже написанного текста.

Поведение:

- сохраняет жанр, стиль, аудиторию и структуру;
- не добавляет citations, title page, rubric, charts или formulas без необходимости;
- избегает лишней академизации;
- все равно проходит review/gates, но без навязывания research-paper структуры.

### Academic Mode

Academic mode нужен, когда задача требует строгого анализа, расчетов, доказательности или источников.

Подходит для:

- academic papers;
- analytical reports;
- coursework/RGR-like documents;
- technical analysis with formulas;
- documents requiring tables, plots, calculations or critical evaluation.

Поведение:

- усиливает аргументацию и проверку допущений;
- может использовать formulas, tables, plots and source discipline;
- активирует более строгие quality expectations;
- не должен ломать исходный artifact type. README остается README, а story остается story, если пользователь не попросил другой формат.

## 4. Sandbox, Вычисления и Визуализации

APE умеет выполнять вычислительные блоки через Python sandbox.

Пример:

````markdown
```python-run
import sympy as sp
x = sp.symbols("x")
print(sp.integrate(x**2, x))
```
````

Что может sandbox:

- выполнять расчеты;
- строить таблицы;
- генерировать данные для графиков;
- использовать `pandas`, `sympy`, `scipy`, `matplotlib`;
- возвращать ошибки Writer'у, чтобы агент мог исправить код;
- вставлять результаты в документ до review/export.

Практический смысл: проект может не только писать текст, но и создавать вычислительные фрагменты, формулы, таблицы и визуализации для академических и аналитических задач.

## 5. Critical Analysis

В academic-oriented задачах система должна не просто красиво оформить ответ, а критически проверить его.

Critical analysis включает:

- проверку слабых предположений;
- поиск unsupported claims;
- выявление противоречий;
- проверку терминов и структуры аргумента;
- limitations and caveats;
- source discipline, если включен research или документ требует источников.

Это реализуется несколькими слоями:

- agent self-critique, если включен в конфиге;
- ReviewerAgent;
- deterministic quality gate;
- contract drift checks;
- continuation/references checks для документов с источниками.

## 6. Research и OCR

Research/OCR - опциональный слой. Он не запускается всегда.

Когда включать:

- нужно использовать текущую информацию из web;
- есть PDF/image/DOCX/MD attachment;
- нужно продолжить или проанализировать внешний документ;
- задача требует source-aware output.

Граница безопасности:

- Researcher и OCR работают на planning side;
- Writer не получает raw search dumps;
- Planner отбирает релевантные факты и source notes;
- Writer пишет документ по curated plan;
- это снижает риск утечки мусора, служебных маркеров и сырого HTML/OCR текста в финальный документ.

## 7. Continuation

Continuation - это не "напиши еще один документ рядом".

Система пытается понять намерение:

- append: продолжить после текущего конца;
- bridge: переписать хвост и продолжить плавно;
- revise in place: улучшить существующий текст;
- expand section: расширить конкретный раздел;
- update references: обновить источники и библиографию;
- restructure: перестроить документ, если это явно попросили.

Для структурированных документов references/appendices считаются terminal sections. Новый body content должен вставляться до них.

## 8. Export

Генерация и экспорт разделены.

Сначала pipeline сохраняет draft. Затем пользователь явно запускает:

- DOCX export;
- PDF export, если доступен LibreOffice/`soffice`;
- download/export for active or archived document.

Export QA проверяет структуру, безопасные пути, имена файлов, базовые Markdown artifacts и conversion status.

## 9. Что Показывать Рекрутеру или Ревьюеру

Самые важные вещи, которые видно без чтения кода:

- project landing page: показывает продуктовую идею и pipeline;
- README: быстрый обзор и запуск;
- `docs/PROJECT_CAPABILITIES.md`: свод реализованных возможностей;
- `docs/ARCHITECTURE.md`: архитектура слоев;
- `docs/ORCHESTRATION.md`: конечный автомат и runtime sequence;
- `docs/AGENTS_AND_TOOLS.md`: агенты, sandbox, export QA;
- `docs/OCR_AND_RESEARCH.md`: research/OCR boundary;
- `docs/CONTINUATION_AND_MERGE.md`: continuation and merge behavior.

Код можно читать уже после этого, когда понятна модель проекта.
