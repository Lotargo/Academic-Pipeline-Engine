# History and artifact API contract

Контракт используется FE-04 и следующей HTTP-адаптацией backend. Каждый
endpoint требует Bearer access token. Workspace определяется backend по
membership; `workspace_id` никогда не передаётся клиентом.

## History

- `GET /api/history?cursor=&limit=25&status=&archived=false` возвращает
  `{ "items": HistoryItem[], "next_cursor": string | null }`. `limit` от 1
  до 100. Сортировка стабильная: newest first по `created_at, id`.
- `GET /api/history/{job_id}` возвращает один `HistoryItem` со всеми
  artifacts. Чужой или отсутствующий ID возвращает `404` без различения.
- `POST /api/history/{job_id}/archive` возвращает обновлённый item.
- `DELETE /api/history/{job_id}` возвращает `204`. Удаляются metadata и
  tenant-scoped artifact objects; действие допускается только после явного
  подтверждения в UI.

## Artifacts

- `POST /api/artifacts/{artifact_id}/download` возвращает
  `{ "url": string, "expires_at": string }`. URL является короткоживущей
  signed URL и не хранится в history response или browser storage.
- При `410` ссылка истекла: UI сообщает об этом и предлагает запросить новую.
  `403` и `404` не раскрывают сведения о чужом artifact.

```ts
type Artifact = {
  id: string; name: string; kind: "upload" | "docx" | "pdf" | "chart" | string
  size_bytes: number | null; checksum: string | null; created_at: string
}
type HistoryItem = {
  id: string; topic: string; status: "succeeded" | "failed" | "cancelled" | string
  created_at: string; updated_at: string; archived_at: string | null
  artifacts: Artifact[]
}
```

Storage keys, bucket names and permanent object URLs are never included in a
response. Authorization is repeated for every list, detail, mutation and
signed-download request.
