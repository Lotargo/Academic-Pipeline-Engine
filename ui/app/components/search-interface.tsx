"use client"

import { useState, useEffect, useRef } from "react"
import { Sidebar } from "./sidebar"
import { SearchBar } from "./search-bar"
import { ConfigEditor } from "./config-editor"
import { FSMMonitor } from "./fsm-monitor"
import { DocumentPreview } from "./document-preview"
import { LiveDocumentCanvas } from "./live-document-canvas"
import { ConsolePanel } from "./console-panel"
import { ArchivedWorksModal } from "./archived-works-modal"
import { toast } from "sonner"
import { Sparkles, FileText, ArrowRight, XCircle, Terminal, FileDown, Loader2 } from "lucide-react"
import { AcademicLogoIcon } from "./academic-logo-icon"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useTheme } from "next-themes"
import { messages, normalizeLanguage, type Messages, type UiLanguage } from "@/lib/i18n"

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
  const [isConsoleOpen, setIsConsoleOpen] = useState<boolean>(false)
  const [consoleHeight, setConsoleHeight] = useState<number>(240)
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
    
    window.addEventListener("ape-config-saved", fetchLanguage)
    return () => window.removeEventListener("ape-config-saved", fetchLanguage)
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

  const handleStartGeneration = async (topic: string, instructions: string, academicMode: boolean) => {
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
      active_section: null
    })
    
    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          instructions,
          academic_mode: academicMode,
          author: nickname.trim() || undefined,
        })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to start pipeline")
      }
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
          <div className="flex items-center gap-2">
            <span className="ape-control-text font-bold text-muted-foreground capitalize">
              {selectedPaper ? t.nav.archiveViewer : activeTab}
            </span>
            <span className="text-muted-foreground/30 text-xs">/</span>
            <span className="text-[13px] font-black text-foreground truncate max-w-[200px] md:max-w-md">
              {selectedPaper
                ? selectedPaper.topic
                : status.status === "RUNNING" || status.status === "STARTING"
                ? `${t.nav.running}: ${status.topic}`
                : t.nav.activeWorkspace}
            </span>
          </div>

          <div className="flex items-center gap-3">
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
                  runtimeTemplate={selectedPaper?.runtime_template}
                  author={selectedPaper?.author}
                  t={t}
                />
              </div>
            </div>
          )}

          {/* Config Editor Tab */}
          {!selectedPaper && activeTab === "config" && <ConfigEditor />}

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
            <div className="h-full w-full overflow-y-auto flex items-center justify-center px-4 py-8">
              <div className="w-full max-w-3xl space-y-8">
                
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
                  disabled={status.status === "RUNNING" || status.status === "STARTING"}
                  t={t}
                />

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
        />
      </main>
    </div>
  )
}
