# BE-03 — Authentication and RBAC

## Goal

Добавить пользовательскую регистрацию, вход, сессии и серверную авторизацию по ролям и workspace membership.

## Scope

- password hashing;
- access JWT;
- refresh sessions и revocation;
- RBAC;
- auth dependencies для FastAPI;
- защита user/admin endpoints.

## Not included

- bootstrap первого администратора;
- frontend-страницы;
- billing и paid roles.

## Depends on

- BE-01;
- BE-02.

## Target state

Публичная регистрация создаёт обычного пользователя и personal workspace. Административная роль выдаётся только через BE-04.

## Invariants

- JWT не используется как invite token;
- refresh token можно отозвать;
- blocked user не запускает jobs;
- role checks выполняются на backend;
- пароли никогда не хранятся в plaintext.

## Acceptance

- registration/login/refresh/logout работают;
- admin endpoints отклоняют user JWT;
- tenant membership проверяется на каждом защищённом ресурсе;
- auth security tests проходят.
