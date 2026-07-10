# BE-01 — Tenant data model

## Tenant boundary

`workspace` is the unit of isolation. Every tenant-owned query receives an
explicit `workspace_id` derived from the authenticated actor's membership; a
client-supplied identifier is never sufficient authorization.

An `organization` groups one or more workspaces. It is not an authorization
boundary by itself: organization membership does not grant access to all of
its workspaces.

## Core entities

| Entity | Required fields | Constraints and purpose |
| --- | --- | --- |
| `users` | `id`, `email`, `actor_role`, `status`, timestamps | Unique normalized email. Represents human users and narrowly scoped service actors. |
| `sessions` | `id`, `user_id`, `token_hash`, `expires_at`, `revoked_at`, timestamps | Never stores a plaintext session token. Revocation or user blocking invalidates access. |
| `organizations` | `id`, `kind`, `name`, `status`, timestamps | `kind` is `personal` or `team`. A personal organization has exactly one owner. |
| `workspaces` | `id`, `organization_id`, `name`, `status`, timestamps | Tenant root for all application data. Every user receives one personal workspace. |
| `memberships` | `id`, `workspace_id`, `user_id`, `membership_role`, `status`, timestamps | Unique `(workspace_id, user_id)`. The only ordinary grant of workspace access. |

Identifiers are immutable UUIDs. Mutable display names and emails are not
foreign keys. Status values are explicit; absence of a row is not overloaded
to mean blocked or suspended.

Personal account creation is atomic: create `user`, personal `organization`,
personal `workspace`, and active owner `membership` in one transaction.

## Relationships

```text
user 1 ── * session
user 1 ── * membership * ── 1 workspace * ── 1 organization
workspace 1 ── * job/artifact/credential/usage_event
```

Team organizations may contain multiple workspaces. A user can belong to many
workspaces, including workspaces belonging to different organizations.
Organization ownership is metadata for lifecycle administration; access to
tenant data still requires a workspace membership.

## Roles and authorization

`users.actor_role` describes the platform actor:

- `user`: ordinary interactive account;
- `admin`: platform operator, provisioned only by the admin bootstrap flow;
- `service`: non-interactive worker or internal automation identity.

`memberships.membership_role` describes authority inside one workspace:

- `owner`: workspace lifecycle and membership administration;
- `member`: normal application operations.

Platform `admin` does not imply tenant membership. Tenant-data support access
must use an explicit, audited elevation flow to be designed with auth/RBAC;
ordinary repositories continue to require `workspace_id`. A `service` actor
has no public login and receives only memberships or capabilities required by
its job. The worker should normally act on a recorded workspace/job context,
not obtain unrestricted cross-tenant access.

## Ownership of application records

| Record | Tenant owner | Actor/audit reference | Rules |
| --- | --- | --- | --- |
| `jobs` | required `workspace_id` | required `created_by_user_id` for interactive creation | All state transitions retain the original workspace. |
| `artifacts` | required `workspace_id` | optional `created_by_user_id`; required `job_id` when job-produced | `artifact.workspace_id` must equal its job's workspace. Storage keys are workspace-prefixed, opaque identifiers. |
| `credentials` | required `workspace_id` | required `created_by_user_id` | Secret material is stored only through the credential store; listing exposes metadata, never plaintext. |
| `usage_events` | required `workspace_id` | nullable `actor_user_id`; optional `job_id` | Append-only accounting/audit event. System events keep workspace ownership even when actor is absent. |

Foreign keys should include or validate the tenant key so that cross-workspace
relations cannot be created accidentally. Repositories must filter by
`workspace_id` before applying resource identifiers. ORM details and concrete
constraints belong to BE-02.

## Status and lifecycle policy

`users.status`: `active`, `blocked`, `deleted`.

- Blocking revokes active sessions and prevents new sessions and job creation.
- Blocking does not delete memberships or tenant data.
- Deleted users retain a tombstone ID for audit references; PII is anonymized
  after the applicable retention window.

`organizations.status` and `workspaces.status`: `active`, `suspended`,
`deleting`, `deleted`.

- A suspended workspace is readable only where policy explicitly permits and
  rejects mutations/new jobs. It is not physically removed.
- Deletion is asynchronous: mark `deleting`, reject new work, cancel or drain
  jobs, delete storage objects, then remove/anonymize database records and mark
  `deleted`.
- Personal-workspace deletion follows account deletion. Team-workspace
  deletion requires an owner and must not cascade to user accounts.
- The last active owner membership cannot be removed until ownership is
  transferred or the workspace enters deletion.

Hard cascading deletion is not used for jobs, artifacts, credentials, or usage
records while retention/audit obligations exist. Credentials are disabled and
their encrypted payloads destroyed during workspace deletion. Artifact rows
are removed only after object deletion succeeds or a retryable deletion marker
has been recorded.

## Orphan prevention

- Tenant-owned rows cannot have a null `workspace_id`.
- A job-produced artifact cannot outlive its workspace or reference a job from
  another workspace.
- Removing a membership never changes or deletes resource ownership.
- Removing a user uses `SET NULL` only for optional actor/audit references;
  tenant ownership remains intact.
- Organization deletion is rejected while non-deleted workspaces exist.
- Background cleanup is idempotent and operates by workspace ID; partial
  storage cleanup remains visible as retryable state, not a silent orphan.

## Handoff to BE-02

BE-02 may choose table/index names and implement SQLAlchemy/Alembic details,
but must preserve immutable UUID identifiers, explicit statuses, non-null
tenant ownership, membership-based access, same-workspace relations, and the
non-cascading audit/deletion rules above.
