# Job API and events contract

Используется FE-03 и последующей HTTP-адаптацией BE-07. Все endpoints требуют
Bearer access token; backend определяет workspace из membership, а не из
клиентского `workspace_id`.

## HTTP

- `POST /api/jobs` принимает `{ "kind": "pipeline", "topic": string,
  "instructions"?: string }`, возвращает `201` и job snapshot.
- `GET /api/jobs?active=true` возвращает `{ "jobs": Job[] }`, newest first.
- `GET /api/jobs/{job_id}` возвращает job snapshot с `stages`.
- `POST /api/jobs/{job_id}/cancel` возвращает `202` и актуальный snapshot.
  Это только запрос отмены: terminal `cancelled` выставляет worker.
- `GET /api/jobs/{job_id}/events` — SSE. Каждый `data` содержит `JobEvent`.
  Поддерживается `Last-Event-ID` (proxy также принимает `last_event_id` query
  parameter); повторное событие с тем же `id` клиент игнорирует.

`Job.status`: `pending`, `queued`, `running`, `succeeded`, `failed`,
`cancelled`. `progress` находится в диапазоне 0–100 и не придумывается UI.

## Payloads

```ts
type Job = {
  id: string; kind: "pipeline"; topic: string; instructions?: string
  status: JobStatus; current_stage: string | null; progress: number
  active_attempt: number; cancel_requested_at: string | null
  error_code: string | null; error_message: string | null
  created_at: string; updated_at: string
  stages: Array<{ name: string; status: string; progress: number }>
}
type JobEvent = { id: string; type: string; created_at: string; job: Job }
```

## Recovery and errors

При открытии jobs UI читает active jobs, сохраняет последний нетерминальный ID
в `sessionStorage` и после reload возобновляет snapshot + SSE. При ошибке SSE
клиент закрывает поток, делает polling каждые 5 секунд и повторяет подключение
с экспоненциальной задержкой 1–30 секунд. `401/403` не повторяются; `404`
очищает сохранённый ID. Ошибки API имеют `{ "detail": string }`.
