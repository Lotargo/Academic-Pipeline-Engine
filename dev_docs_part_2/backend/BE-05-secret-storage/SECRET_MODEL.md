# BE-05 secret storage model

## Provider choice

Production boundary — managed KMS/Vault Transit через `KeyWrapper`; приложение не
владеет master key. Конкретный cloud provider откладывается до deployment.
`LocalAesKeyWrapper` предназначен только для development/tests и принимает key
из внешней конфигурации, не из PostgreSQL.

## Envelope format

Для каждого credential генерируется случайный 256-bit data key. Payload
шифруется AES-256-GCM с отдельным 96-bit nonce. Data key оборачивается KMS.
PostgreSQL хранит ciphertext+tag, nonce, wrapped data key, KMS key ID и version.

AAD: `ape:credential:v1:{credential_id}:{workspace_id}:{provider}`. Поэтому
перенос ciphertext между credentials, tenants или providers не проходит AEAD
verification.

## Lifecycle and permissions

- Create и replace всегда создают новый data key; plaintext не возвращается API.
- Delete помечает запись deleted и уничтожает ciphertext/wrapped key случайными
  байтами.
- Decrypt разрешён только generation/OCR worker purpose и только внутри вызова
  `use`; queue должна передавать исключительно `credential_id`.
- Admin/API purpose не имеют decrypt permission.
- Все lifecycle/use/rewrap операции аудируются без plaintext.

## Rotation

KMS rotation выполняется `rewrap`: старый adapter unwraps только data key, новый
adapter wraps его заново; payload не расшифровывается и не меняется. Ротацию
следует запускать батчами с retry по credential ID. До завершения батча workers
маршрутизируют unwrap по сохранённому `encryption_key_id`; старый KMS key
отключается только после проверки отсутствия ссылок на него.
