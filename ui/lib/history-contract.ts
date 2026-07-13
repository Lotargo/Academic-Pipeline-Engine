export type Artifact = {
  id: string
  name: string
  kind: string
  size_bytes: number | null
  checksum: string | null
  created_at: string
  legacy_path?: string
}

export type HistoryItem = {
  id: string
  topic: string
  status: string
  created_at: string
  updated_at: string
  archived_at: string | null
  artifacts: Artifact[]
  legacy?: boolean
}

export type HistoryPage = { items: HistoryItem[]; next_cursor: string | null }
