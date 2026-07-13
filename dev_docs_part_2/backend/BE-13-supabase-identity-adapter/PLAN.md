# BE-13 — Supabase Identity Adapter

## Goal

Сделать Supabase Auth единственной identity boundary для service profiles, не
ломая legacy local-first и не смешивая два формата bearer token в одном режиме.

## Scope

- интерфейс проверки external identity и его mock implementation;
- безопасная проверка Supabase access token (issuer, audience, signature,
  expiry и key rotation);
- mapping стабильного `auth.users.id` в внутреннего пользователя APE;
- транзакционное создание personal workspace и привязки identity при первом
  успешном входе;
- server-side RBAC и workspace checks после resolution identity;
- отказ от password/register/refresh endpoints в Supabase service profile.

## Not included

- регистрация OAuth applications и provider secrets;
- реальный Google/Яндекс OAuth E2E до постоянного HTTPS deployment;
- удаление legacy BE-03 auth router;
- изменение Supabase Auth schema вручную.

## Depends on

- BE-01;
- BE-02;
- BE-04;
- BE-11;
- PL-04.

## Invariants

- `auth.users.id` является внешним immutable identity key; email сам по себе
  не используется как ключ связывания;
- service profile принимает только токены выбранного identity adapter;
- проверка JWT выполняется backend, а не UI;
- provisioning user/workspace идемпотентен и tenant-scoped;
- legacy password JWT остаётся доступен только в явно выбранном legacy режиме.

## Acceptance

- mock Supabase identity создаёт и повторно находит один app user/workspace;
- invalid, expired, wrong-issuer и wrong-audience токены отклоняются;
- privileged endpoints по-прежнему проверяют application RBAC;
- local-first regression и backend contract tests проходят;
- создан walkthrough с явно отмеченным production OAuth gate.
