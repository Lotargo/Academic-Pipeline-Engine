# BE-10 Object Storage — Walkthrough

## Tasks

`BE-10-T001`–`BE-10-T008`.

## Result

- Добавлен единый `ArtifactStorage` contract для upload/download/delete/signed URL.
- `LocalArtifactStorage` сохранён как local-first adapter с атомарной записью.
- `ObjectArtifactStorage` использует S3-compatible client boundary для внешнего source of truth.
- Ключи имеют вид `workspaces/{workspace_id}/artifacts/{uuid}/{filename}`.
- Upload вычисляет SHA-256, размер и сохраняет media type metadata.
- Cross-tenant keys отклоняются до обращения к backend storage.
- Signed URL выдаётся только после membership check, максимум на 15 минут.
- Local signed token защищён HMAC, проверяет tampering и expiration.
- `temporary_artifact` удаляет worker-файл после успеха и исключения, включая Windows.

## Migration notes

Новая миграция не нужна: существующая ORM-модель `Artifact` уже содержит storage key, filename, media type, size и checksum.

## Tests

- `poetry run pytest tests/storage -q` — 6 passed.
- `poetry run pytest -q` — 538 passed, 3 skipped.
- `git diff --check` — passed.

## Deviations and issues

Нет. Конкретный S3/R2/MinIO SDK client конфигурируется platform composition через `ObjectClient` boundary.

## Next step

BE-11 Local-First Compatibility.
