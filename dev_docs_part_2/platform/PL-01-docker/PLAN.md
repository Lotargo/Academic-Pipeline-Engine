# PL-01 — Docker

## Goal

Создать воспроизводимые production images для frontend, API и workers.

## Scope

- frontend image;
- shared backend image;
- разные commands для API/workers;
- отдельный export image при необходимости LibreOffice;
- healthchecks;
- non-root runtime и image size.

## Not included

- Render configuration;
- database provisioning;
- application feature implementation.

## Depends on

- реализуемые процессы backend/frontend.

## Invariants

- containers stateless;
- secrets не запекаются в image;
- production command использует `$PORT` где требуется;
- build воспроизводим из Git.

## Acceptance

- images собираются в CI/local;
- каждый process запускается отдельно;
- healthchecks проходят;
- export dependencies не раздувают все backend images.
