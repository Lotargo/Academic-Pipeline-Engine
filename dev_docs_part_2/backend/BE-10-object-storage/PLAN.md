# BE-10 — Object Storage

## Goal

Вынести uploads и экспортированные артефакты из файловой системы контейнера в object storage.

## Scope

- ArtifactStorage interface;
- uploads, DOCX, PDF и charts;
- storage metadata;
- signed URLs;
- temporary files в `/tmp`;
- cleanup и checksums.

## Not included

- export rendering logic;
- frontend history UI;
- database schema вне artifact metadata.

## Depends on

- BE-01;
- BE-02.

## Target state

Object storage — source of truth для файлов. Контейнеры stateless и не требуют persistent disk.

## Invariants

- storage key tenant-scoped;
- приватный artifact не доступен без membership check;
- signed URL имеет короткий срок;
- временные файлы удаляются после upload или failure cleanup.

## Acceptance

- local и object storage adapters проходят общий contract test;
- upload/download/delete работают;
- signed access защищён;
- redeploy не уничтожает артефакты.
