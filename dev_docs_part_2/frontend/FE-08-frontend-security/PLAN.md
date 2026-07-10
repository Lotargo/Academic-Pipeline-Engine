# FE-08 — Frontend Security

## Goal

Снизить риск XSS, утечки session data и небезопасного рендера пользовательского/LLM-контента.

## Scope

- CSP;
- safe Markdown/HTML rendering;
- cookie/token handling;
- CSRF strategy;
- external links и postMessage;
- dependency review;
- security headers.

## Not included

- backend RBAC;
- secret encryption at rest;
- infrastructure firewall.

## Depends on

- FE-композиции, которые рендерят данные или работают с auth.

## Invariants

- refresh/session secrets не хранятся в localStorage;
- unsafe HTML не рендерится без sanitization;
- CSP не допускает ненужные wildcard sources;
- security headers проверяются в production build.

## Acceptance

- CSP и headers включены;
- unsafe-content tests проходят;
- auth/session flows не зависят от доступного JS storage для refresh secrets;
- high-risk dependencies и sinks задокументированы.
