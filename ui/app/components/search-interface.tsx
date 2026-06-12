"use client"

import { useState, useEffect, useRef } from "react"
import { Sidebar } from "./sidebar"
import { SearchBar } from "./search-bar"
import { ConfigEditor } from "./config-editor"
import { FSMMonitor } from "./fsm-monitor"
import { DocumentPreview } from "./document-preview"
import { LiveDocumentCanvas } from "./live-document-canvas"
import { ConsolePanel } from "./console-panel"
import { toast } from "sonner"
import { Sparkles, FileText, ArrowRight, Sun, Moon, XCircle, Terminal } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useTheme } from "next-themes"
import { messages, normalizeLanguage, type Messages, type UiLanguage } from "@/lib/i18n"

export function Search() {
  const { theme, setTheme } = useTheme()
  const [language, setLanguage] = useState<UiLanguage>("en")
  const t: Messages = messages[language]
  const [activeTab, setActiveTab] = useState<string>("workspace")
  const [historyList, setHistoryList] = useState<any[]>([])
  const [selectedPaper, setSelectedPaper] = useState<any>(null)
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

  // Poll intervals
  useEffect(() => {
    fetchHistory()
    fetchStatus()
    fetchLanguage()
    window.addEventListener("ape-config-saved", fetchLanguage)
    return () => window.removeEventListener("ape-config-saved", fetchLanguage)
  }, [])

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
      }
    } catch (e) {
      console.error("Error loading history list:", e)
    }
  }

  const handleStartGeneration = async (topic: string, instructions: string, academicMode: boolean) => {
    notifiedRef.current = false
    
    // Switch to FSM visualization tab immediately; the backend status becomes
    // the source of truth after /api/run accepts the job.
    setActiveTab("fsm")
    setIsConsoleOpen(true)
    setStatus({
      status: "STARTING",
      state: "INIT",
      logs: ["Triggering pipeline..."],
      context: {},
      original_context: {},
      reviewer_feedback: [],
      docx_filename: null,
      export_report: null,
      error: null,
      topic: topic,
      active_section: null
    })
    
    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, instructions, academic_mode: academicMode })
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
        t={t}
      />

      {/* Main Workspace Frame */}
      <main className="flex-1 flex flex-col h-full bg-background overflow-hidden relative">
        {/* Top Navbar */}
        <header className="h-14 border-b border-border/80 bg-card/50 flex items-center justify-between px-6 shrink-0 z-30 select-none">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-muted-foreground capitalize">
              {selectedPaper ? t.nav.archiveViewer : activeTab}
            </span>
            <span className="text-muted-foreground/30 text-xs">/</span>
            <span className="text-xs font-black text-foreground truncate max-w-[200px] md:max-w-md">
              {selectedPaper
                ? selectedPaper.topic
                : status.status === "RUNNING" || status.status === "STARTING"
                ? `${t.nav.running}: ${status.topic}`
                : t.nav.activeWorkspace}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {(status.status === "RUNNING" || status.status === "STARTING") && (
              <>
                <div className="flex items-center gap-2 rounded-full bg-teal-500/10 px-3 py-1 text-[10px] font-bold text-teal-600 dark:text-teal-400 animate-pulse border border-teal-500/20">
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-500" />
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
                    className="h-7 px-3 text-[10px] font-bold uppercase border-red-500/30 text-red-400 hover:bg-red-500/10 hover:border-red-500/50 gap-1.5"
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
                  ? "bg-teal-500/15 border-teal-500/35 text-teal-700 dark:text-teal-400"
                  : "border-border bg-card/40 text-muted-foreground hover:text-foreground hover:bg-accent"
              }`}
              title="Toggle Console"
            >
              <Terminal className="h-4 w-4" />
              <span>{language === "ru" ? "Консоль" : "Console"}</span>
            </button>

            <button
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card/40 text-muted-foreground hover:text-foreground hover:bg-accent transition-all duration-200 cursor-pointer shadow-sm"
              title="Toggle theme"
            >
              <Sun className="h-4.5 w-4.5 dark:hidden" />
              <Moon className="h-4.5 w-4.5 hidden dark:block" />
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
                  </p>
                </div>
                
                <DocumentPreview
                  topic={selectedPaper.topic}
                  context={selectedPaper.context}
                  docxFilename={selectedPaper.filename}
                  runtimeTemplate={selectedPaper?.runtime_template}
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
                
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                  {/* Left Column: FSM Visualizer & Feedbacks */}
                  <div className="lg:col-span-4 w-full">
                    <FSMMonitor status={status} onRetry={() => setActiveTab("workspace")} t={t} />
                  </div>
                  
                  {/* Right Column: Live Document Paper Canvas */}
                  <div className="lg:col-span-8 w-full">
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
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-600/10 text-teal-600 dark:text-teal-400 shadow-[0_4px_20px_rgba(13,148,136,0.1)]">
                    <Sparkles className="h-7 w-7 animate-pulse" />
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
                  <div className="p-4 rounded-xl border border-teal-500/20 bg-teal-500/5 animate-pulse text-xs flex items-center justify-between">
                    <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-500" />
                      </span>
                      <span className="font-semibold">{t.workspace.current}: "{status.topic}"</span>
                    </div>
                    <button
                      onClick={() => setActiveTab("fsm")}
                      className="text-teal-600 dark:text-teal-400 hover:underline font-bold flex items-center gap-1 cursor-pointer bg-transparent border-0"
                    >
                      {t.workspace.viewLogs} <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                )}
                
                {status.status === "COMPLETED" && (
                  <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-xs flex items-center justify-between">
                    <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
                      ✓ {t.workspace.generated}: "{status.topic}"
                    </span>
                    <button
                      onClick={() => {
                        setSelectedPaper(null)
                        setActiveTab("fsm")
                      }}
                      className="text-emerald-600 dark:text-emerald-400 hover:underline font-bold flex items-center gap-1 cursor-pointer bg-transparent border-0"
                    >
                      {t.workspace.viewDocument} <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                )}

                {status.status === "CANCELLED" && (
                  <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs flex items-center justify-between">
                    <span className="text-amber-700 dark:text-amber-400 font-semibold">
                      ⚠ Pipeline was cancelled
                    </span>
                    <button
                      onClick={() => {
                        setSelectedPaper(null)
                        setActiveTab("workspace")
                      }}
                      className="text-amber-600 dark:text-amber-400 hover:underline font-bold flex items-center gap-1 cursor-pointer bg-transparent border-0"
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
      </main>
    </div>
  )
}
