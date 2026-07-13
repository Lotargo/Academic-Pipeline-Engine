# Временный deployment в OpenShift Sandbox

## Статус

Активное временное решение, 2026-07-13. Это окружение `service-demo`, а не
замена постоянного target из `PL-02`.

## Решение

После появления воспроизводимых images и отдельных commands frontend, API и
worker из `PL-01` использовать уже выделенный Red Hat Developer Sandbox /
OpenShift project для ограниченного public deployment.

## Причины

- Доступный путь Render free не запускает continuous worker и one-off migration
  job, требуемые текущей process matrix.
- Текущий Vercel path не является host для полной matrix Python API и
  long-running Celery worker.
- Sandbox имеет пустой project, достаточную на текущий момент quota для
  отдельных workloads и проверенные разрешения на Deployment, Route и Secret.

## Границы

- Деплой выполняется через OpenShift manifests и `oc`; OpenShift Dev Spaces не
  используется как deployment mechanism.
- Frontend, API и worker остаются отдельными workloads; containers stateless и
  не используют container filesystem для пользовательских данных.
- Runtime credentials создаются только как OpenShift Secrets из защищённого
  локального operator environment. Не коммитить values, login commands или
  kubeconfig.
- Migrations выполняются явным single-purpose job, никогда не несколькими app
  replicas одновременно.
- Public Route временный: не настраивать его как canonical production OAuth
  redirect и не заявлять production E2E provider-auth.
- В sandbox walkthrough фиксировать quota, deploy, health и rollback без токенов
  и пользовательских данных.

## Это не production acceptance

Developer Sandbox — shared environment с ограниченным сроком. Успешный smoke
доказывает лишь совместимость manifests и end-to-end path. Он не закрывает
`PL-02`, production observability, backup/retention, rollback или production
OAuth gates.

## Условия выхода

Заменить Sandbox, когда появится одно из следующего:

1. self-managed home server с надёжным uptime и явным owner backup и updates;
2. VPS с тем же operational owner; или
3. другой managed provider, поддерживающий нужную process matrix frontend,
   API, worker, migration и secrets.

До отметки `PL-02` complete постоянный target получает новую environment/secrets
matrix, canonical HTTPS URL, migration и rollback acceptance, а также отдельный
walkthrough.
