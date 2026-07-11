"use client"

import { useState, useEffect, useRef, type ChangeEvent, type DragEvent } from "react"
import { Sidebar } from "./sidebar"
import { SearchBar } from "./search-bar"
import { ConfigEditor } from "./config-editor"
import { FSMMonitor } from "./fsm-monitor"
import { DocumentPreview } from "./document-preview"
import { LiveDocumentCanvas } from "./live-document-canvas"
import { ConsolePanel } from "./console-panel"
import { ArchivedWorksModal } from "./archived-works-modal"
import { toast } from "sonner"
import { Archive, Sparkles, FileText, ArrowRight, XCircle, Terminal, FileDown, Loader2, Trash2, PlayCircle, Paperclip, UploadCloud } from "lucide-react"
import { AcademicLogoIcon } from "./academic-logo-icon"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { useTheme } from "next-themes"
import { messages, normalizeLanguage, type Messages, type UiLanguage } from "@/lib/i18n"
import { startEditorRun } from "@/lib/editor-adapter"

const ARTIFACT_OVERRIDE_OPTIONS = [
  { value: "", label: "Auto-Detect" },
  { value: "creative_poem", label: "Poem" },
  { value: "creative_story", label: "Story / Fiction" },
  { value: "school_essay", label: "School Essay" },
  { value: "academic_paper", label: "Academic Paper" },
  { value: "technical_readme", label: "README" },
  { value: "plan_document", label: "Plan" },
  { value: "report", label: "Report" },
  { value: "unknown_freeform", label: "Freeform Fallback" },
]

const CONTINUATION_INTENT_OPTIONS = [
  { value: "", label: "Auto" },
  { value: "continue_append", label: "Continue append" },
  { value: "bridge_and_continue", label: "Bridge and continue" },
  { value: "revise_in_place", label: "Revise in place" },
  { value: "expand_section", label: "Expand section" },
  { value: "complete_missing_section", label: "Complete missing section" },
  { value: "update_references_only", label: "Update references only" },
  { value: "restructure", label: "Restructure" },
]

type AttachmentType = "passive_reference" | "continuation_source"

const REFERENCE_ATTACHMENT_ACCEPT = ".pdf,.docx,.md,.txt,.csv,.xlsx,.pptx"
const CONTINUATION_ATTACHMENT_ACCEPT = ".pdf,.docx,.md,.txt"
const REFERENCE_ATTACHMENT_LABEL = "PDF, DOCX, MD, TXT, CSV, XLSX, PPTX"
const CONTINUATION_ATTACHMENT_LABEL = "PDF, DOCX, TXT, MD"

function formatArtifactLabel(value: unknown) {
  if (typeof value !== "string" || !value.trim()) return ""
  const knownOption = ARTIFACT_OVERRIDE_OPTIONS.find((option) => option.value === value)
  if (knownOption) return knownOption.label
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function artifactDetection(status: any, selectedPaper: any) {
  const source = selectedPaper || status || {}
  const summary = source.decision_summary || source.runtime_prompt_manifest?.metadata?.decision_summary
  const selection = source.manifest_selection || source.runtime_prompt_manifest?.metadata?.manifest_selection
  const contract = source.resolved_contract || source.runtime_prompt_manifest?.metadata?.resolved_contract
  const manifest = source.resolved_manifest || source.runtime_prompt_manifest?.metadata?.resolved_manifest
  const override = source.artifact_override || source.runtime_prompt_manifest?.metadata?.artifact_override

  const artifact = summary?.artifact || summary?.selected_manifest || contract?.artifact || manifest?.artifact_type || manifest?.id
  const mode = summary?.mode || contract?.execution_mode
  const confidence = typeof summary?.confidence === "number"
    ? summary.confidence
    : typeof selection?.confidence === "number"
      ? selection.confidence
      : null
  const summaryText = typeof summary?.summary === "string" ? summary.summary : ""

  if (!artifact && !mode && confidence === null && !override) return null

  return {
    artifact: formatArtifactLabel(artifact),
    mode: formatArtifactLabel(mode),
    confidence,
    summary: summaryText,
    override: formatArtifactLabel(override),
    lowConfidence: confidence !== null && confidence < 0.65,
  }
}

function inferContinuationIntentLabel(source: any) {
  const metadataIntent = source?.runtime_prompt_manifest?.metadata?.continuation_intent?.intent
  if (typeof metadataIntent === "string" && metadataIntent.trim()) {
    return metadataIntent
  }

  const context = source?.context || {}
  const hardEnding = Object.entries(context).some(([name, value]) => {
    const sectionName = String(name || "").toLowerCase()
    const text = String(value || "").slice(-1200).toLowerCase()
    return (
      ["conclusion", "summary", "ending", "finale"].some((alias) => sectionName.includes(alias)) ||
      /\b(the end|in conclusion|to conclude|overall|therefore)\b/.test(text) ||
      /в\s+заключение|подведем\s+итог|в\s+итоге/i.test(text)
    )
  })

  return hardEnding ? "bridge_and_continue" : "continue_append"
}

export function Search() {
  const { theme, setTheme } = useTheme()
  const [language, setLanguage] = useState<UiLanguage>("en")
  const t: Messages = messages[language]
  const [nickname, setNickname] = useState("")
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<string>("workspace")
  const [historyList, setHistoryList] = useState<any[]>([])
  const [selectedPaper, setSelectedPaper] = useState<any>(null)
  const [viewedPaperIds, setViewedPaperIds] = useState<string[]>([])
  const [archivedWorksOpen, setArchivedWorksOpen] = useState(false)
  const [exportingDocx, setExportingDocx] = useState(false)
  const [exportingPdf, setExportingPdf] = useState(false)
  const [paperPendingDelete, setPaperPendingDelete] = useState<any>(null)
  const [continuationSource, setContinuationSource] = useState<any>(null)
  const [isConsoleOpen, setIsConsoleOpen] = useState<boolean>(false)
  const [consoleHeight, setConsoleHeight] = useState<number>(240)
  const [showDebugInfo, setShowDebugInfo] = useState<boolean>(false)
  const [artifactOverride, setArtifactOverride] = useState<string>("")
  const [continuationIntentOverride, setContinuationIntentOverride] = useState<string>("")
  const [activeAttachments, setActiveAttachments] = useState<any[]>([])
  const [uploadAttachmentType, setUploadAttachmentType] = useState<AttachmentType>("passive_reference")
  const [uploadingFile, setUploadingFile] = useState(false)
  const [isDraggingAttachment, setIsDraggingAttachment] = useState(false)
  const notifiedRef = useRef(false)
  const fsmScrollRef = useRef<HTMLDivElement | null>(null)
  const lastFsmScrollResetKeyRef = useRef<string>("")
  
  // Pipeline status state
  const [status, setStatus] = useState<any>({
    status: "IDLE",
    state: "INIT",
    logs: [],
    context: {},
    reviewer_feedback: [],
    docx_filename: null,
    pdf_filename: null,
    export_report: null,
    error: null,
    topic: "",
    active_section: null
  })

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/status")
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
        return data
      }
    } catch (e) {
      console.error("Error fetching pipeline status on mount:", e)
    }
    return null
  }

  const fetchLanguage = async () => {
    try {
      const res = await fetch("/api/config")
      if (res.ok) {
        const data = await res.json()
        setLanguage(normalizeLanguage(data?.ui?.language || data?.pipeline?.language))
      }
    } catch (e) {
      console.error("Error loading UI language:", e)
    }
  }

  const handleLanguageChange = async (nextLanguage: UiLanguage) => {
    setLanguage(nextLanguage)
    try {
      const res = await fetch("/api/config")
      if (!res.ok) throw new Error("Failed to read current config")
      const currentConfig = await res.json()
      const nextConfig = {
        ...currentConfig,
        ui: {
          ...(currentConfig.ui || {}),
          language: nextLanguage,
        },
      }
      const saveRes = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: nextConfig }),
      })
      if (!saveRes.ok) {
        const err = await saveRes.json()
        throw new Error(err.detail || "Failed to save language")
      }
      window.dispatchEvent(new CustomEvent("ape-config-saved"))
    } catch (e: any) {
      toast.error(e.message || "Failed to save language")
      fetchLanguage()
      throw e
    }
  }

  // Poll intervals
  useEffect(() => {
    fetchHistory()
    fetchStatus()
    fetchLanguage()
    setNickname(window.localStorage.getItem("ape.profile.nickname") || "")
    setAvatarUrl(window.localStorage.getItem("ape.profile.avatar"))
    
    // Load viewed paper IDs on mount
    const stored = window.localStorage.getItem("ape.viewed-papers")
    if (stored) {
      try {
        setViewedPaperIds(JSON.parse(stored))
      } catch (e) {
        console.error("Failed to parse viewed papers:", e)
      }
    }
    
    const handleReset = () => {
      fetchHistory()
      setSelectedPaper(null)
    }
    window.addEventListener("ape-config-saved", fetchLanguage)
    window.addEventListener("ape-history-reset", handleReset)
    return () => {
      window.removeEventListener("ape-config-saved", fetchLanguage)
      window.removeEventListener("ape-history-reset", handleReset)
    }
  }, [])

  useEffect(() => {
    if (selectedPaper?.id) {
      setViewedPaperIds((prev) => {
        if (!prev.includes(selectedPaper.id)) {
          const next = [...prev, selectedPaper.id]
          window.localStorage.setItem("ape.viewed-papers", JSON.stringify(next))
          return next
        }
        return prev
      })
    }
  }, [selectedPaper])

  useEffect(() => {
    let interval: any
    let events: EventSource | null = null

    const handleStatusUpdate = (data: any) => {
      setStatus(data)
      if (data.status === "COMPLETED" && !notifiedRef.current) {
        notifiedRef.current = true
        fetchHistory()
        toast.success(t.workspace.generated)
        events?.close()
      } else if (data.status === "FAILED" && !notifiedRef.current) {
        notifiedRef.current = true
        toast.error(t.fsm.failed)
        events?.close()
      } else if (data.status === "CANCELLED" && !notifiedRef.current) {
        notifiedRef.current = true
        toast.info("Pipeline was cancelled")
        events?.close()
      }
    }

    if (status.status === "RUNNING") {
      if (typeof window !== "undefined" && "EventSource" in window) {
        events = new EventSource("/api/status/stream")
        events.onmessage = (event) => {
          handleStatusUpdate(JSON.parse(event.data))
        }
        events.onerror = () => {
          console.warn("SSE stream connection error; HTTP polling remains active.")
          events?.close()
        }
      }

      interval = setInterval(async () => {
        try {
          const res = await fetch("/api/status")
          if (res.ok) {
            handleStatusUpdate(await res.json())
          }
        } catch (e) {
          console.error("HTTP status polling error:", e)
        }
      }, 1000)
    } else {
      notifiedRef.current = false
    }

    return () => {
      clearInterval(interval)
      events?.close()
    }
  }, [status.status, language])

  useEffect(() => {
    if (activeTab !== "fsm" || selectedPaper) return

    requestAnimationFrame(() => {
      fsmScrollRef.current?.scrollTo({ top: 0 })
    })
  }, [activeTab, selectedPaper])

  useEffect(() => {
    if (activeTab !== "fsm" || selectedPaper) return
    if (status.status !== "STARTING" && status.status !== "RUNNING") return

    const resetKey = status.run_id || `${status.status}:${status.topic}`
    if (!resetKey || lastFsmScrollResetKeyRef.current === resetKey) return

    lastFsmScrollResetKeyRef.current = resetKey
    requestAnimationFrame(() => {
      fsmScrollRef.current?.scrollTo({ top: 0 })
    })
  }, [activeTab, selectedPaper, status.run_id, status.status, status.topic])

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/history")
      if (res.ok) {
        const data = await res.json()
        setHistoryList(data)

        // Initialize viewedPaperIds with all existing paper IDs on first load
        // if no viewed papers list has been tracked yet.
        const stored = window.localStorage.getItem("ape.viewed-papers")
        if (!stored && data.length > 0) {
          const allIds = data.map((p: any) => p.id).filter(Boolean)
          setViewedPaperIds(allIds)
          window.localStorage.setItem("ape.viewed-papers", JSON.stringify(allIds))
        }
      }
    } catch (e) {
      console.error("Error loading history list:", e)
    }
  }

  const currentExportableContext = Object.fromEntries(
    Object.entries(status?.context || {}).filter(([key, value]) => key !== "document_plan" && Boolean(value))
  )
  const currentDraftReady =
    !selectedPaper &&
    (status?.status === "COMPLETED" || status?.state === "DONE") &&
    Object.keys(currentExportableContext).length > 0
  const detectedArtifact = artifactDetection(status, selectedPaper)
  const inferredContinuationIntent = continuationSource
    ? inferContinuationIntentLabel(continuationSource)
    : ""
  const detectedConfidenceLabel = typeof detectedArtifact?.confidence === "number"
    ? `${Math.round(detectedArtifact.confidence * 100)}%`
    : ""
  const artifactSource = selectedPaper || status || {}
  const artifactSummary = artifactSource.decision_summary || artifactSource.runtime_prompt_manifest?.metadata?.decision_summary
  const artifactSelection = artifactSource.manifest_selection || artifactSource.runtime_prompt_manifest?.metadata?.manifest_selection
  const artifactContract = artifactSource.resolved_contract || artifactSource.runtime_prompt_manifest?.metadata?.resolved_contract
  const artifactManifest = artifactSource.resolved_manifest || artifactSource.runtime_prompt_manifest?.metadata?.resolved_manifest

  const handleDownloadCurrentDocx = () => {
    if (!status?.docx_filename) return
    window.open(`/api/download/${status.docx_filename}`, "_blank")
  }

  const handleDownloadCurrentPdf = () => {
    if (!status?.pdf_filename) return
    window.open(`/api/download/${status.pdf_filename}`, "_blank")
  }

  const handleExportCurrentDocx = async () => {
    if (!currentDraftReady) return
    setExportingDocx(true)
    try {
      const res = await fetch("/api/export/docx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context: currentExportableContext,
          topic: status?.topic || "Untitled",
          runtime_template: status?.runtime_template,
          author: nickname.trim() || undefined,
          run_id: status?.run_id || undefined,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Export failed")
      }
      setStatus((prev: any) => ({
        ...prev,
        docx_filename: data.filename,
        export_report: data,
      }))

      const downloadUrl = `/api/download/${data.filename}`
      const link = document.createElement("a")
      link.href = downloadUrl
      link.setAttribute("download", data.filename)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      if (data.status === "passed") {
        toast.success("DOCX export passed quality checks")
      } else {
        toast.warning("DOCX exported with QA issues")
      }
      await fetchHistory()
    } catch (e: any) {
      toast.error(e.message || "Failed to export DOCX")
    } finally {
      setExportingDocx(false)
    }
  }

  const handleExportCurrentPdf = async () => {
    if (!currentDraftReady) return
    setExportingPdf(true)
    try {
      const res = await fetch("/api/export/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context: currentExportableContext,
          topic: status?.topic || "Untitled",
          runtime_template: status?.runtime_template,
          author: nickname.trim() || undefined,
          run_id: status?.run_id || undefined,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "PDF export failed")
      }
      setStatus((prev: any) => ({
        ...prev,
        pdf_filename: data.filename,
        export_report: data,
      }))

      const downloadUrl = `/api/download/${data.filename}`
      const link = document.createElement("a")
      link.href = downloadUrl
      link.setAttribute("download", data.filename)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      toast.success("PDF export completed")
      await fetchHistory()
    } catch (e: any) {
      toast.error(e.message || "Failed to export PDF")
    } finally {
      setExportingPdf(false)
    }
  }

  const handleArchivePaper = async (paper: any) => {
    if (!paper?.id) {
      toast.error("History item is missing metadata id")
      return
    }
    try {
      const res = await fetch(`/api/history/${encodeURIComponent(paper.id)}/archive`, { method: "POST" })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to archive work")
      }
      if (selectedPaper?.id === paper.id) {
        setSelectedPaper(null)
        setActiveTab("workspace")
      }
      await fetchHistory()
      toast.success(language === "ru" ? "Работа перемещена в архив" : "Work archived")
    } catch (e: any) {
      toast.error(e.message || "Failed to archive work")
    }
  }

  const handleDeletePaper = async (paper: any) => {
    if (!paper?.id) {
      toast.error("History item is missing metadata id")
      return
    }
    try {
      const res = await fetch(`/api/history/${encodeURIComponent(paper.id)}`, { method: "DELETE" })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to delete work")
      }
      if (selectedPaper?.id === paper.id) {
        setSelectedPaper(null)
        setActiveTab("workspace")
      }
      await fetchHistory()
      toast.success(language === "ru" ? "Работа удалена" : "Work deleted")
    } catch (e: any) {
      toast.error(e.message || "Failed to delete work")
    }
  }

  const buildContinuationSource = (paper: any) => {
    const context = Object.fromEntries(
      Object.entries(paper?.context || {}).filter(([_, value]) => Boolean(value))
    )
    return {
      source_type: "generated",
      topic: paper?.topic || "Untitled",
      instructions: paper?.instructions || undefined,
      previous_prompt: paper?.previous_prompt || [
        paper?.topic ? `Topic: ${paper.topic}` : "",
        paper?.instructions ? `Instructions: ${paper.instructions}` : "",
      ].filter(Boolean).join("\n") || undefined,
      context,
      document_plan: paper?.document_plan || paper?.context?.document_plan || undefined,
      runtime_template: paper?.runtime_template || undefined,
      runtime_prompt_manifest: paper?.runtime_prompt_manifest || undefined,
      template_mode: paper?.template_mode || undefined,
      template_id: paper?.template_id || undefined,
      metadata_id: paper?.id || undefined,
      run_id: paper?.run_id || undefined,
    }
  }

  const handleContinuePaper = (paper: any) => {
    if (!paper?.context || Object.keys(paper.context).length === 0) {
      toast.error(language === "ru" ? "У этой работы нет сохранённого текста для продолжения" : "This work has no saved text to continue")
      return
    }
    setContinuationSource(buildContinuationSource(paper))
    setContinuationIntentOverride("")
    setSelectedPaper(null)
    setArchivedWorksOpen(false)
    setActiveTab("workspace")
    toast.info(language === "ru" ? "Режим продолжения включён" : "Continuation mode enabled")
  }

  const uploadAttachmentFile = async (file: File) => {
    setUploadingFile(true)
    const formData = new FormData()
    formData.append("file", file)
    formData.append("attachment_type", uploadAttachmentType)
    try {
      const res = await fetch("/api/attachments/upload", {
        method: "POST",
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Upload failed")
      }
      const data = await res.json()
      if (data.attachment_type === "continuation_source") {
        setActiveAttachments(prev => [
          ...prev.map(a => ({ ...a, attachment_type: "passive_reference" })),
          data,
        ])
      } else {
        setActiveAttachments(prev => [...prev, data])
      }
      toast.success(language === "ru" ? `Файл '${data.filename}' успешно прикреплен` : `File '${data.filename}' attached successfully`)
    } catch (err: any) {
      toast.error(err.message || "Failed to process document")
    } finally {
      setUploadingFile(false)
    }
  }

  const handleAttachmentInputChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    await uploadAttachmentFile(file)
    event.target.value = ""
  }

  const handleAttachmentDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    event.stopPropagation()
    if (!uploadingFile) {
      event.dataTransfer.dropEffect = "copy"
      setIsDraggingAttachment(true)
    }
  }

  const handleAttachmentDrop = async (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDraggingAttachment(false)
    if (uploadingFile) return
    const file = event.dataTransfer.files?.[0]
    if (!file) return
    await uploadAttachmentFile(file)
  }

  const handleStartGeneration = async (
    topic: string,
    instructions: string,
    academicMode: boolean,
    artifactOverride?: string,
    webSearchEnabled: boolean = false
  ) => {
    notifiedRef.current = false
    
    // Switch to FSM visualization tab immediately; the backend status becomes
    // the source of truth after /api/run accepts the job.
    setActiveTab("fsm")
    setStatus({
      status: "STARTING",
      state: "INIT",
      logs: ["Triggering pipeline..."],
      context: {},
      original_context: {},
      reviewer_feedback: [],
      docx_filename: null,
      pdf_filename: null,
      export_report: null,
      error: null,
      topic: topic,
      author: nickname.trim() || null,
      active_section: null,
      artifact_override: artifactOverride || null,
    })
    
    try {
      const started = await startEditorRun({ topic, instructions, editorOptions: {
        academic_mode: academicMode,
        artifact_override: artifactOverride || undefined,
        author: nickname.trim() || undefined,
        continuation_source: continuationSource ? { ...continuationSource, intent_override: continuationIntentOverride || undefined } : undefined,
        web_search_enabled: webSearchEnabled,
        attachments: activeAttachments.length > 0 ? activeAttachments : undefined,
      } })
      if (started.profile !== "local") throw new Error("Legacy editor is available only in local profile")
      const serverStatus = await fetchStatus()
      if (!serverStatus || serverStatus.status !== "RUNNING") {
        setStatus((prev: any) => ({
          ...prev,
          status: "RUNNING",
          state: serverStatus?.state || "INIT",
          logs: serverStatus?.logs || prev.logs,
          topic: serverStatus?.topic || topic,
        }))
      }
      setContinuationSource(null)
      setContinuationIntentOverride("")
      setActiveAttachments([])
      toast.info(t.nav.pipelineDrafting)
    } catch (e: any) {
      toast.error(e.message || "Failed to start execution")
      setStatus((prev: any) => ({
        ...prev,
        status: "FAILED",
        error: e.message || "Execution start failed"
      }))
    }
  }

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        historyList={historyList}
        selectedPaper={selectedPaper}
        setSelectedPaper={setSelectedPaper}
        viewedPaperIds={viewedPaperIds}
        t={t}
        language={language}
        onLanguageChange={handleLanguageChange}
        theme={theme}
        onThemeChange={setTheme}
        nickname={nickname}
        onNicknameChange={setNickname}
        avatarUrl={avatarUrl}
        onAvatarChange={setAvatarUrl}
        onArchivePaper={handleArchivePaper}
        onDeletePaper={handleDeletePaper}
        onOpenArchivedWorks={() => setArchivedWorksOpen(true)}
      />

      {/* Main Workspace Frame */}
      <main className="flex-1 min-w-0 flex flex-col h-full bg-background overflow-hidden relative">
        {/* Top Navbar */}
        <header className="h-14 border-b border-border/80 bg-card/60 flex items-center justify-between px-6 shrink-0 z-30 select-none backdrop-blur">
          <div className="flex min-w-0 items-center gap-2">
            <span className="ape-control-text shrink-0 font-bold text-muted-foreground capitalize">
              {selectedPaper ? t.nav.archiveViewer : activeTab}
            </span>
            <span className="shrink-0 text-xs text-muted-foreground/30">/</span>
            <span className="min-w-0 max-w-[200px] truncate text-[13px] font-black text-foreground md:max-w-md">
              {selectedPaper
                ? selectedPaper.topic
                : status.status === "RUNNING" || status.status === "STARTING"
                ? `${t.nav.running}: ${status.topic}`
                : t.nav.activeWorkspace}
            </span>
            {detectedArtifact && (
              <span
                title={detectedArtifact.summary || "Artifact detection"}
                className={`hidden shrink-0 items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide md:inline-flex ${
                  detectedArtifact.lowConfidence && !detectedArtifact.override
                    ? "ape-status-warning animate-pulse border-ape-warning/40"
                    : "border-ape-primary/25 bg-ape-primary-soft/60 text-ape-primary-text"
                }`}
              >
                <span>Detected:</span>
                {detectedArtifact.artifact && <span>{detectedArtifact.artifact}</span>}
                {detectedArtifact.mode && <span>/ {detectedArtifact.mode}</span>}
                {detectedConfidenceLabel && <span>/ {detectedConfidenceLabel}</span>}
              </span>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {selectedPaper && (
              <>
                <Button
                  size="sm"
                  onClick={() => handleContinuePaper(selectedPaper)}
                  className="h-8 gap-1.5 bg-ape-primary px-3 text-[11px] font-bold uppercase text-white hover:bg-ape-primary/90"
                >
                  <PlayCircle className="h-3.5 w-3.5" />
                  {language === "ru" ? "Продолжить" : "Continue"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleArchivePaper(selectedPaper)}
                  className="h-8 gap-1.5 px-3 text-[11px] font-bold uppercase"
                >
                  <Archive className="h-3.5 w-3.5" />
                  {language === "ru" ? "Архивировать" : "Archive"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setPaperPendingDelete(selectedPaper)}
                  className="h-8 gap-1.5 border-destructive/30 px-3 text-[11px] font-bold uppercase text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {language === "ru" ? "Удалить" : "Delete"}
                </Button>
              </>
            )}

            {currentDraftReady && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={status?.pdf_filename ? handleDownloadCurrentPdf : handleExportCurrentPdf}
                  disabled={exportingPdf}
                  className="h-8 gap-1.5 px-3 text-[11px] font-bold uppercase"
                >
                  {exportingPdf ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
                  {status?.pdf_filename
                    ? ((t.document as any).downloadPdf || t.document.downloadDocx.replace("DOCX", "PDF"))
                    : ((t.document as any).exportPdf || t.document.exportDocx.replace("DOCX", "PDF"))}
                </Button>
                <Button
                  size="sm"
                  onClick={status?.docx_filename ? handleDownloadCurrentDocx : handleExportCurrentDocx}
                  disabled={exportingDocx}
                  className="h-8 gap-1.5 bg-ape-primary px-3 text-[11px] font-bold uppercase text-white hover:bg-ape-primary/90"
                >
                  {exportingDocx ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
                  {status?.docx_filename ? t.document.downloadDocx : t.document.exportDocx}
                </Button>
              </>
            )}

            {(status.status === "RUNNING" || status.status === "STARTING") && (
              <>
                <div className="flex items-center gap-2 rounded-full ape-status-primary px-3 py-1 text-[11px] font-bold animate-pulse border">
                  <span className="h-1.5 w-1.5 rounded-full bg-ape-primary" />
                  <span>{t.nav.pipelineDrafting}</span>
                </div>
                {status.status === "RUNNING" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={async () => {
                      try {
                        const res = await fetch("/api/cancel", { method: "POST" })
                        if (!res.ok) {
                          const err = await res.json()
                          throw new Error(err.detail || "Failed to cancel pipeline")
                        }
                        toast.info("Pipeline cancellation requested")
                      } catch (e: any) {
                        toast.error(e.message || "Failed to cancel")
                      }
                    }}
                    className="h-7 px-3 text-[11px] font-bold uppercase border-ape-danger/30 text-ape-danger-text hover:bg-ape-danger-soft hover:border-ape-danger/50 gap-1.5"
                  >
                    <XCircle className="h-3 w-3" />
                    Cancel
                  </Button>
                )}
              </>
            )}
            
            <button
              onClick={() => setIsConsoleOpen(!isConsoleOpen)}
              className={`flex h-8 items-center justify-center gap-1.5 px-3 rounded-lg border transition-all duration-200 cursor-pointer shadow-sm text-xs font-semibold ${
                isConsoleOpen
                  ? "bg-ape-primary-soft border-ape-primary/35 text-ape-primary-text"
                  : "border-border bg-card/40 text-muted-foreground hover:text-foreground hover:bg-accent"
              }`}
              title="Toggle Console"
            >
              <Terminal className="h-4 w-4" />
              <span>{language === "ru" ? "Консоль" : "Console"}</span>
            </button>

          </div>
        </header>

        {/* Tab Switchboard */}
        <div className="flex-1 w-full overflow-hidden relative">
          
          {/* Historical Paper Reviewer */}
          {selectedPaper && (
            <div className="h-full w-full overflow-y-auto px-6 py-6 md:px-8">
              <div className="mx-auto max-w-5xl space-y-6">
                <div className="border-b pb-4">
                  <h1 className="text-xl md:text-2xl font-bold tracking-tight text-foreground">
                    {selectedPaper.topic}
                  </h1>
                  <p className="text-xs text-muted-foreground mt-1">
                    Generated on {selectedPaper.timestamp} · Status: COMPLETED
                    {selectedPaper.author ? ` · Author: ${selectedPaper.author}` : ""}
                  </p>
                </div>
                
                <DocumentPreview
                  topic={selectedPaper.topic}
                  context={selectedPaper.context}
                  docxFilename={selectedPaper.filename}
                  runId={selectedPaper?.run_id}
                  runtimeTemplate={selectedPaper?.runtime_template}
                  author={selectedPaper?.author}
                  t={t}
                  language={language}
                  metadata={selectedPaper}
                />
              </div>
            </div>
          )}

          {/* Config Editor Tab */}
          {!selectedPaper && activeTab === "config" && <ConfigEditor language={language} />}

          {/* Pipeline Monitor / Log Tab */}
          {!selectedPaper && activeTab === "fsm" && (
            <div ref={fsmScrollRef} className="h-full w-full overflow-y-auto px-6 pt-8 pb-6 md:px-8 md:pt-10">
              <div className="mx-auto max-w-7xl w-full space-y-6">
                <div className="border-b pb-4">
                  <h1 className="text-xl md:text-2xl font-bold tracking-tight text-foreground">
                    Pipeline Execution Monitor
                  </h1>
                  <p className="text-xs text-muted-foreground mt-1">
                    Watch the real-time agent workflow execution and log console output.
                  </p>
                </div>
                
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start lg:items-stretch">
                  {/* Left Column: FSM Visualizer & Feedbacks */}
                  <div className="lg:col-span-4 w-full lg:h-full">
                    <FSMMonitor status={status} onRetry={() => setActiveTab("workspace")} t={t} />
                  </div>
                  
                  {/* Right Column: Live Document Paper Canvas */}
                  <div className="lg:col-span-8 w-full lg:h-full">
                    <LiveDocumentCanvas status={status} onStatusUpdate={setStatus} t={t} />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Standard Input Workspace Tab */}
          {!selectedPaper && activeTab === "workspace" && (
            <div className="h-full w-full overflow-y-auto flex justify-center px-4 pb-10 pt-12 md:pt-16">
              <div className="w-full max-w-3xl space-y-7">
                
                {/* Visual Intro */}
                <div className="text-center space-y-3">
                  <div className="mx-auto flex items-center justify-center mb-1">
                    <AcademicLogoIcon className="h-16 w-16" animate={true} />
                  </div>
                  <div className="space-y-1">
                    <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-foreground">
                      Academic Pipeline Engine
                    </h1>
                    <p className="text-xs md:text-sm text-muted-foreground max-w-lg mx-auto leading-relaxed">
                      {t.workspace.subtitle}
                    </p>
                  </div>
                </div>

                {/* Input Panel */}
                <SearchBar
                  onSearch={handleStartGeneration}
                  onEnhance={(data) => {
                    setStatus((prev: any) => ({
                      ...prev,
                      resolved_manifest: data.resolved_manifest,
                      resolved_contract: data.resolved_contract,
                      manifest_selection: data.manifest_selection,
                      decision_summary: data.decision_summary,
                      artifact_override: data.artifact_override || null,
                    }))
                  }}
                  onArtifactOverrideChange={(value) => {
                    setArtifactOverride(value)
                    setStatus((prev: any) => ({
                      ...prev,
                      artifact_override: value || null,
                    }))
                  }}
                  disabled={status.status === "RUNNING" || status.status === "STARTING"}
                  t={t}
                  artifactOverride={artifactOverride}
                  detectedConfidence={detectedArtifact?.confidence ?? null}
                  initialTopic={continuationSource?.topic || ""}
                  initialInstructions={
                    continuationSource
                      ? (language === "ru"
                          ? "Продолжи эту работу на основе уточнений: "
                          : "Continue this work based on these clarifications: ")
                      : ""
                  }
                />

                {/* Document Attachments Upload Section */}
                <div className="rounded-xl border border-border/50 bg-card p-4 shadow-sm space-y-4">
                  <div className="flex items-center justify-between border-b border-border/40 pb-2">
                    <div className="flex items-center gap-1.5">
                      <Paperclip className="h-4.5 w-4.5 text-ape-primary-text" />
                      <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
                        {language === "ru" ? "Прикрепленные файлы" : "Document Attachments"}
                      </h3>
                    </div>
                    {uploadingFile && (
                      <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                        <Loader2 className="h-3 w-3 animate-spin text-ape-primary" />
                        {language === "ru" ? "Обработка..." : "Parsing..."}
                      </span>
                    )}
                  </div>

                  <div className="space-y-2">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                      {language === "ru" ? "Тип загрузки" : "Upload as"}
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        disabled={uploadingFile}
                        onClick={() => setUploadAttachmentType("passive_reference")}
                        className={`rounded-lg border px-3 py-2 text-left text-[11px] font-semibold transition-all ${
                          uploadAttachmentType === "passive_reference"
                            ? "ape-status-primary border-ape-primary/30"
                            : "bg-muted/40 dark:bg-ape-surface-subtle/30 border-border/50 text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        <span className="block">{language === "ru" ? "Справка" : "Reference"}</span>
                        <span className="block text-[10px] font-normal opacity-80">
                          {language === "ru" ? "Для планировщика" : "Planner background"}
                        </span>
                      </button>
                      <button
                        type="button"
                        disabled={uploadingFile}
                        onClick={() => setUploadAttachmentType("continuation_source")}
                        className={`rounded-lg border px-3 py-2 text-left text-[11px] font-semibold transition-all ${
                          uploadAttachmentType === "continuation_source"
                            ? "ape-status-primary border-ape-primary/30"
                            : "bg-muted/40 dark:bg-ape-surface-subtle/30 border-border/50 text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        <span className="block">{language === "ru" ? "Продолжение" : "Continuation"}</span>
                        <span className="block text-[10px] font-normal opacity-80">
                          {language === "ru" ? "Основа для новой версии" : "Base for new version"}
                        </span>
                      </button>
                    </div>
                  </div>

                  {/* Drag-and-drop / Upload Area */}
                  <label
                    onDragEnter={handleAttachmentDragOver}
                    onDragOver={handleAttachmentDragOver}
                    onDragLeave={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setIsDraggingAttachment(false)
                    }}
                    onDrop={handleAttachmentDrop}
                    className={`flex flex-col items-center justify-center border-2 border-dashed rounded-lg py-4 px-6 cursor-pointer transition-all group ${
                      isDraggingAttachment
                        ? "border-ape-primary/70 bg-ape-primary-soft/40"
                        : "border-border/60 bg-muted/20 hover:border-ape-primary/40 hover:bg-muted/40 dark:bg-ape-surface-subtle/20"
                    }`}
                  >
                    <UploadCloud className="h-8 w-8 text-muted-foreground group-hover:text-ape-primary transition-colors" />
                    <span className="mt-2 text-xs font-bold text-foreground">
                      {language === "ru"
                        ? `Загрузить документ (${uploadAttachmentType === "passive_reference" ? REFERENCE_ATTACHMENT_LABEL : CONTINUATION_ATTACHMENT_LABEL})`
                        : `Upload document (${uploadAttachmentType === "passive_reference" ? REFERENCE_ATTACHMENT_LABEL : CONTINUATION_ATTACHMENT_LABEL})`}
                    </span>
                    <span className="mt-1 text-[10px] text-muted-foreground">
                      {language === "ru" ? "Лимит: 20k токенов на файл" : "Limit: 20k tokens per file"}
                    </span>
                    <input
                      type="file"
                      accept={uploadAttachmentType === "passive_reference" ? REFERENCE_ATTACHMENT_ACCEPT : CONTINUATION_ATTACHMENT_ACCEPT}
                      disabled={uploadingFile}
                      className="hidden"
                      onChange={handleAttachmentInputChange}
                    />
                  </label>

                  {/* Active Attachments list */}
                  {activeAttachments.length > 0 && (
                    <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                      {activeAttachments.map((att, idx) => (
                        <div key={idx} className="flex items-center justify-between gap-3 p-2.5 rounded-lg border border-border/40 bg-muted/40 dark:bg-ape-surface-subtle/30 text-xs">
                          <div className="min-w-0 flex-1 space-y-1">
                            <p className="font-semibold text-foreground truncate break-words">
                              {att.filename}
                            </p>
                            <p className="text-[10px] text-muted-foreground flex items-center gap-1.5 flex-wrap">
                              <span>Size: {(att.token_count).toLocaleString()} tokens</span>
                              <span className="h-1 w-1 rounded-full bg-border" />
                              <span className="font-semibold text-ape-primary-text">
                                {att.attachment_type === "continuation_source"
                                  ? (language === "ru" ? "Источник продолжения" : "Continuation Source")
                                  : (language === "ru" ? "Справочный материал" : "Reference Material")}
                              </span>
                            </p>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {/* Toggle type button */}
                            <button
                              type="button"
                              onClick={() => {
                                const newType = att.attachment_type === "continuation_source" ? "passive_reference" : "continuation_source";
                                setActiveAttachments(prev => prev.map((a, i) => {
                                  if (i === idx) {
                                    return { ...a, attachment_type: newType };
                                  }
                                  // Ensure there is only at most one continuation source active
                                  if (newType === "continuation_source" && a.attachment_type === "continuation_source") {
                                    return { ...a, attachment_type: "passive_reference" };
                                  }
                                  return a;
                                }));
                              }}
                              className="px-2 py-1 rounded text-[10px] font-bold border border-border hover:bg-muted dark:hover:bg-ape-surface-subtle transition-colors cursor-pointer bg-card text-foreground"
                            >
                              {language === "ru" ? "Сменить тип" : "Change Type"}
                            </button>

                            {/* Delete button */}
                            <button
                              type="button"
                              onClick={() => {
                                setActiveAttachments(prev => prev.filter((_, i) => i !== idx));
                                toast.info(language === "ru" ? "Файл удален из списка" : "Attachment removed");
                              }}
                              className="p-1 rounded text-muted-foreground hover:text-ape-danger transition-colors cursor-pointer border-0 bg-transparent"
                              title="Delete attachment"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {continuationSource && (
                  <div className="rounded-xl border border-ape-primary/25 bg-ape-primary-soft/60 p-4 text-xs text-ape-primary-text">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-bold uppercase tracking-wide">
                          {language === "ru" ? "Режим продолжения" : "Continuation mode"}
                        </p>
                        <p className="mt-1 break-words">
                          {language === "ru" ? "Источник" : "Source"}: {continuationSource.topic || "Untitled"}
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setContinuationSource(null)
                          setContinuationIntentOverride("")
                        }}
                        className="h-7 shrink-0 px-2 text-[11px] font-bold"
                      >
                        {language === "ru" ? "Сбросить" : "Clear"}
                      </Button>
                    </div>
                    <div className="mt-3 grid gap-2 border-t border-ape-primary/20 pt-3 sm:grid-cols-2">
                      <div className="min-w-0 rounded-lg bg-background/55 px-3 py-2">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                          Inferred intent
                        </p>
                        <p className="mt-0.5 truncate font-mono text-[11px] font-semibold">
                          {inferredContinuationIntent || "auto"}
                        </p>
                      </div>
                      <label className="min-w-0 rounded-lg bg-background/55 px-3 py-2">
                        <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                          Override intent
                        </span>
                        <select
                          value={continuationIntentOverride}
                          onChange={(event) => setContinuationIntentOverride(event.target.value)}
                          className="mt-1 h-8 w-full rounded-md border border-border bg-background px-2 font-mono text-[11px] text-foreground outline-none"
                        >
                          {CONTINUATION_INTENT_OPTIONS.map((option) => (
                            <option key={option.value || "auto"} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  </div>
                )}

                {detectedArtifact && (
                  <div className="rounded-xl border border-border/70 bg-card/70 p-4 text-xs shadow-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-bold uppercase tracking-wide text-muted-foreground">
                        Artifact routing
                      </span>
                      {detectedArtifact.artifact && (
                        <span className="rounded-full bg-ape-primary-soft px-2.5 py-1 font-bold text-ape-primary-text">
                          {detectedArtifact.artifact}
                        </span>
                      )}
                      {detectedArtifact.mode && (
                        <span className="rounded-full bg-muted px-2.5 py-1 font-semibold text-muted-foreground">
                          {detectedArtifact.mode}
                        </span>
                      )}
                      {detectedConfidenceLabel && (
                        <span className="rounded-full bg-muted px-2.5 py-1 font-semibold text-muted-foreground">
                          {detectedConfidenceLabel}
                        </span>
                      )}
                      {detectedArtifact.override && (
                        <span className="rounded-full border border-ape-primary/25 bg-ape-primary-soft px-2.5 py-1 font-bold text-ape-primary-text">
                          Override: {detectedArtifact.override}
                        </span>
                      )}
                    </div>
                    {detectedArtifact.summary && (
                      <p className="mt-2 text-muted-foreground">{detectedArtifact.summary}</p>
                    )}
                    {detectedArtifact.lowConfidence && !detectedArtifact.override && (
                      <p className="mt-2 rounded-lg border border-ape-warning/40 bg-ape-warning-soft px-3 py-2 font-semibold text-ape-warning-text">
                        Low confidence. Correct the artifact type before generating if this detection looks wrong.
                      </p>
                    )}
                    
                    <div className="mt-3 border-t border-border/40 pt-2.5">
                      <div className="mb-2.5 flex flex-wrap items-center gap-2">
                        <span className="text-[10px] font-bold uppercase text-muted-foreground">
                          Correct type
                        </span>
                        <select
                          value={artifactOverride}
                          onChange={(event) => {
                            const value = event.target.value
                            setArtifactOverride(value)
                            setStatus((prev: any) => ({
                              ...prev,
                              artifact_override: value || null,
                            }))
                          }}
                          disabled={status.status === "RUNNING" || status.status === "STARTING"}
                          className={`rounded-lg border bg-background px-2 py-1 text-[11px] font-bold text-foreground focus:outline-none ${
                            detectedArtifact.lowConfidence && !artifactOverride
                              ? "border-ape-warning/50 text-ape-warning-text"
                              : "border-border/60"
                          }`}
                        >
                          {ARTIFACT_OVERRIDE_OPTIONS.map((option) => (
                            <option key={option.value || "auto"} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <button
                        type="button"
                        onClick={() => setShowDebugInfo(!showDebugInfo)}
                        className="text-[10px] font-bold uppercase text-muted-foreground hover:text-foreground flex items-center gap-1 cursor-pointer bg-transparent border-0 p-0"
                      >
                        {showDebugInfo
                          ? (language === "ru" ? "Скрыть отладку" : "Hide debug info")
                          : (language === "ru" ? "Показать отладку" : "Show debug info")}
                      </button>
                      
                      {showDebugInfo && (
                        <div className="mt-2 space-y-2 rounded bg-muted/30 p-2.5 font-mono text-[10px] border border-border/30 text-muted-foreground">
                          <div>
                            <span className="font-bold text-foreground">Manifest ID:</span>{" "}
                            {artifactManifest?.id || artifactContract?.artifact || artifactSummary?.selected_manifest || "N/A"}
                          </div>
                          <div>
                            <span className="font-bold text-foreground">Version:</span>{" "}
                            {artifactManifest?.version || "N/A"}
                          </div>
                          <div>
                            <span className="font-bold text-foreground">Matched Cues:</span>{" "}
                            {JSON.stringify(artifactSummary?.matched_phrases || artifactSelection?.matched_phrases || [])}
                          </div>
                          <div>
                            <span className="font-bold text-foreground">Forbid List:</span>{" "}
                            {JSON.stringify(artifactManifest?.forbid || artifactContract?.forbid || [])}
                          </div>
                          <div>
                            <span className="font-bold text-foreground">Override:</span>{" "}
                            {artifactSource.artifact_override || "N/A"}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Active compilation summary card */}
                {(status.status === "RUNNING" || status.status === "STARTING") && (
                  <div className="p-4 rounded-xl ape-status-primary animate-pulse text-xs flex items-center justify-between border">
                    <div className="flex items-center gap-2 text-ape-primary-text">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ape-primary opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-ape-primary" />
                      </span>
                      <span className="font-semibold">{t.workspace.current}: "{status.topic}"</span>
                    </div>
                    <button
                      onClick={() => setActiveTab("fsm")}
                      className="text-ape-primary-text hover:underline font-bold flex items-center gap-1 cursor-pointer bg-transparent border-0"
                    >
                      {t.workspace.viewLogs} <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                )}
                
                {status.status === "COMPLETED" && (
                  <div className="rounded-xl ape-status-success p-4 text-xs flex items-center justify-between border">
                    <span className="text-ape-success-text font-semibold">
                      ✓ {t.workspace.generated}: "{status.topic}"
                    </span>
                    <button
                      onClick={() => {
                        setSelectedPaper(null)
                        setActiveTab("fsm")
                      }}
                      className="text-ape-success-text hover:underline font-bold flex items-center gap-1 cursor-pointer bg-transparent border-0"
                    >
                      {t.workspace.viewDocument} <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                )}

                {status.status === "CANCELLED" && (
                  <div className="rounded-xl ape-status-warning p-4 text-xs flex items-center justify-between border">
                    <span className="text-ape-warning-text font-semibold">
                      ⚠ Pipeline was cancelled
                    </span>
                    <button
                      onClick={() => {
                        setSelectedPaper(null)
                        setActiveTab("workspace")
                      }}
                      className="text-ape-warning-text hover:underline font-bold flex items-center gap-1 cursor-pointer bg-transparent border-0"
                    >
                      Start New Run <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Collapsible, Resizable Bottom Console */}
        <ConsolePanel
          status={status}
          isOpen={isConsoleOpen}
          onClose={() => setIsConsoleOpen(false)}
          height={consoleHeight}
          setHeight={setConsoleHeight}
          t={t}
        />
        <ArchivedWorksModal
          open={archivedWorksOpen}
          onOpenChange={setArchivedWorksOpen}
          language={language}
          onRestored={fetchHistory}
          onContinueWork={handleContinuePaper}
        />
        <AlertDialog open={Boolean(paperPendingDelete)} onOpenChange={(open) => !open && setPaperPendingDelete(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{language === "ru" ? "Удалить работу?" : "Delete this work?"}</AlertDialogTitle>
              <AlertDialogDescription>
                {language === "ru"
                  ? "Это действие навсегда удалит запись и связанные файлы экспорта."
                  : "This permanently removes the history record and related export files."}
                {paperPendingDelete?.topic ? ` "${paperPendingDelete.topic}"` : ""}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{language === "ru" ? "Отмена" : "Cancel"}</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={async () => {
                  const target = paperPendingDelete
                  setPaperPendingDelete(null)
                  if (target) await handleDeletePaper(target)
                }}
              >
                {language === "ru" ? "Удалить" : "Delete"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </main>
    </div>
  )
}
