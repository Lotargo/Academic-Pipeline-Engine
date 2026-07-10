# BE-05 Secret Storage walkthrough

- Дата и исполнитель: 2026-07-11, Codex.
- Композиция: BE-05 Secret Storage.
- Задачи: BE-05-T001 — BE-05-T008.
- Commit/PR: текущий commit.

## Сделано

Введён provider-neutral `KeyWrapper` для managed KMS/Vault Transit и envelope
encryption AES-256-GCM. Каждый credential получает отдельный data key; БД хранит
только ciphertext, nonce, wrapped key, key ID и version. AAD связывает данные с
credential, workspace и provider.

`CredentialStore` реализует create/replace/delete/use/rewrap. Decrypt разрешён
только generation/OCR workers, admin/API получают отказ. Delete криптографически
уничтожает сохранённый материал. Добавлены audit events и redaction filter для
structured secrets и bearer tokens.

## Проверки

- Lifecycle, ciphertext-at-rest и tenant boundary tests.
- Worker permission, rotation/rewrap, AEAD tamper и redaction tests.
- Полный `pytest -q`.
- Alembic SQLite upgrade/downgrade, `compileall`, `git diff --check`.

## Отклонения и известные проблемы

Конкретный production KMS provider выбирается при deployment; интерфейс не
привязан к cloud vendor. Local AES wrapper предназначен только для development и
tests. Worker integration с очередью относится к BE-06/BE-08.
Credentials, созданные до BE-05 без envelope metadata, миграция безопасно
отключает; владелец должен заменить их перед использованием.

## Следующий шаг

Перейти к BE-06 Queue and Workers.
