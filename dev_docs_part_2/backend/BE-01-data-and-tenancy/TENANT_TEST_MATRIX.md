# BE-01 — Tenant isolation test matrix

The matrix is implementation-neutral. BE-02 and BE-03 should map each case to
repository/database and API tests respectively.

| ID | Actor and operation | Expected result | Layers |
| --- | --- | --- | --- |
| TI-01 | Active member lists own workspace resources | Only rows with the selected `workspace_id` are returned | API, repository, DB |
| TI-02 | Member supplies another workspace ID | Denied without revealing whether the workspace exists | API, repository |
| TI-03 | Member supplies another tenant's job/artifact ID under own workspace | Not found/denied; no cross-tenant row is returned | API, repository, DB |
| TI-04 | Create job with a workspace lacking active membership | Denied and no job/outbox row is committed | API, repository, DB |
| TI-05 | Create artifact whose job belongs to another workspace | Constraint/domain validation rejects the write | repository, DB |
| TI-06 | Create credential or usage event without `workspace_id` | Constraint rejects the write | repository, DB |
| TI-07 | Organization member without workspace membership reads workspace | Denied; organization association is not a grant | API, repository |
| TI-08 | Platform admin uses an ordinary tenant endpoint without membership | Denied; no implicit global tenant access | API, repository |
| TI-09 | Service actor processes a job in its authorized context | Only that job's workspace data is accessible and audited | worker, repository |
| TI-10 | Service actor substitutes another workspace ID | Denied and recorded as a security event | worker, repository |
| TI-11 | Blocked user reuses an existing session | Session rejected; no data or mutation is returned | auth, API |
| TI-12 | Suspended workspace receives a new mutation/job | Rejected; existing data remains isolated and retained | API, repository |
| TI-13 | Membership is removed during an active session | Subsequent request is denied; resources remain owned by workspace | auth, API, repository |
| TI-14 | Last owner attempts to leave an active workspace | Rejected until transfer or deletion starts | API, repository, DB |
| TI-15 | Workspace deletion partially fails in object storage | Retry state is retained; no other workspace objects are touched | worker, DB, storage |
| TI-16 | Two tenants use identical filenames/provider labels | Storage keys and database reads remain distinct | repository, storage |
| TI-17 | Concurrent personal-account provisioning retries | Exactly one personal org/workspace/owner membership exists | service, DB |
| TI-18 | Usage aggregation runs across workspaces | Results are grouped/filtered explicitly and tenant API exposes only own group | service, API, DB |

Every negative case must assert both the response and absence of side effects.
Tests should use two workspaces with deliberately colliding resource names and
IDs passed through request parameters where possible.
