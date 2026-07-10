# Local-to-cloud migration

1. Остановить локальные записи и определить каталог SQLite/exports.
2. Запустить `migrate_local_data(source, backup, importer)`. Backup обязан находиться вне source.
3. Helper создаёт ZIP с SHA-256 manifest до вызова importer.
4. Importer идемпотентно переносит registry rows и artifacts через cloud adapters.
5. Сверить количество импортированных jobs/artifacts и выборочно checksum файлов.
6. Переключить `APE_RUNTIME_PROFILE=cloud` только после проверки.

Rollback: остановить записи, вернуть local profile и вызвать
`rollback_local_data(backup, source)`. Restore сначала проверяет все checksums,
распаковывает в staging и только затем атомарно заменяет исходный каталог.
Повреждённый или path-traversal backup отклоняется без изменения source.
