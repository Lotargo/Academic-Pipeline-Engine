# Shared Contracts

Создавать отдельный контракт только когда устойчивый интерфейс используют минимум две композиции.

Контракт должен быть коротким и содержать только поля, состояния, ошибки и совместимость. Не дублировать реализацию или общую архитектуру.

Композиция обязана ссылаться на конкретный контракт в `Required context`; агент не читает весь каталог автоматически.

- [Provider-only auth](provider-auth.md) — shared BE-13/FE-12 identity и BFF boundary.
- [Personal settings API](personal-settings-api.md) — shared FE-09/service preference boundary.
