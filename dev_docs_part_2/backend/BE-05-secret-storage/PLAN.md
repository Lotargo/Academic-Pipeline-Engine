# BE-05 — Secret Storage

## Goal

Безопасно хранить platform и user provider credentials без возврата plaintext во frontend.

## Scope

- Vault/KMS adapter;
- envelope encryption;
- AES-256-GCM или эквивалентный AEAD;
- credential metadata и lifecycle;
- decrypt permission только для нужного worker;
- redaction и audit.

## Not included

- самописная криптография;
- обязательный ML-KEM transport;
- provider selection policy.

## Depends on

- BE-01;
- BE-02.

## Target state

PostgreSQL хранит ciphertext и metadata. RabbitMQ получает только `credential_id`. Plaintext доступен worker только на время вызова провайдера.

## Invariants

- ключ не попадает в logs, traces, exceptions или queue payload;
- admin не видит plaintext user key;
- API не возвращает сохранённый ключ;
- master key не хранится рядом с ciphertext.

## Acceptance

- create/replace/delete/use lifecycle реализован;
- key rotation и rewrap strategy описаны;
- dump БД не раскрывает ключи;
- redaction и permission tests проходят.
