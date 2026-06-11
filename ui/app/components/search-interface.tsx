"use client"

import { useState, useEffect } from "react"
import { Sidebar } from "./sidebar"
import { SearchBar } from "./search-bar"
import { ConfigEditor } from "./config-editor"
import { FSMMonitor } from "./fsm-monitor"
import { DocumentPreview } from "./document-preview"
import { toast } from "sonner"
import { Sparkles, FileText, ArrowRight } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"

export function Search() {
  const [activeTab, setActiveTab] = useState<string>("workspace")
  const [historyList, setHistoryList] = useState<any[]>([])
  const [selectedPaper, setSelectedPaper] = useState<any>(null)
  
  // Pipeline status state
  const [status, setStatus] = useState<any>({
    status: "IDLE",
    state: "INIT",
    logs: [],
    context: {},
    reviewer_feedback: [],
    docx_filename: null,
    error: null,
    topic: ""
  })

  // Poll intervals
  useEffect(() => {
    fetchHistory()
  }, [])

  useEffect(() => {
    let interval: any
    if (status.status === "RUNNING") {
      interval = setInterval(async () => {
        try {
          const res = await fetch("/api/status")
          if (res.ok) {
            const data = await res.json()
            setStatus(data)
            
            // If completed, fetch history list to refresh sidebar
            if (data.status === "COMPLETED") {
              fetchHistory()
              toast.success("Document compilation complete!")
            } else if (data.status === "FAILED") {
              toast.error("Pipeline compilation failed")
            }
          }
        } catch (e) {
          console.error("Error fetching pipeline status:", e)
        }
      }, 1000)
    }
    return () => clearInterval(interval)
  }, [status.status])

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

  const handleStartGeneration = async (topic: string, instructions: string) => {
    // Reset local state first
    setStatus({
      status: "RUNNING",
      state: "INIT",
      logs: ["Triggering pipeline..."],
      context: {},
      reviewer_feedback: [],
      docx_filename: null,
      error: null,
      topic: topic
    })
    
    // Switch to FSM visualization tab
    setActiveTab("fsm")
    
    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, instructions })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to start pipeline")
      }
      toast.info("Document generation pipeline initiated...")
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
      />

      {/* Main Workspace Frame */}
      <main className="flex-1 flex flex-col h-full bg-background overflow-hidden relative">
        {/* Top Navbar */}
        <header className="h-14 border-b border-border/80 bg-card/50 flex items-center justify-between px-6 shrink-0 z-30 select-none">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-muted-foreground capitalize">
              {selectedPaper ? "Archive Viewer" : activeTab}
            </span>
            <span className="text-muted-foreground/30 text-xs">/</span>
            <span className="text-xs font-black text-foreground truncate max-w-[200px] md:max-w-md">
              {selectedPaper
                ? selectedPaper.topic
                : status.status === "RUNNING"
                ? `Running: ${status.topic}`
                : "Active Workspace"}
            </span>
          </div>

          {status.status === "RUNNING" && (
            <div className="flex items-center gap-2 rounded-full bg-teal-500/10 px-3 py-1 text-[10px] font-bold text-teal-600 dark:text-teal-400 animate-pulse border border-teal-500/20">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-500" />
              <span>Pipeline Compiling</span>
            </div>
          )}
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
                />
              </div>
            </div>
          )}

          {/* Config Editor Tab */}
          {!selectedPaper && activeTab === "config" && <ConfigEditor />}

          {/* Pipeline Monitor / Log Tab */}
          {!selectedPaper && activeTab === "fsm" && (
            <div className="h-full w-full overflow-y-auto px-6 py-6 md:px-8">
              <div className="mx-auto max-w-4xl space-y-6">
                <div className="border-b pb-4">
                  <h1 className="text-xl md:text-2xl font-bold tracking-tight text-foreground">
                    Pipeline Execution Monitor
                  </h1>
                  <p className="text-xs text-muted-foreground mt-1">
                    Watch the real-time agent workflow execution and log console output.
                  </p>
                </div>
                
                <FSMMonitor status={status} onRetry={() => setActiveTab("workspace")} />
                
                {status.status === "COMPLETED" && (
                  <div className="border-t pt-6 space-y-4">
                    <h3 className="text-sm font-semibold flex items-center gap-1.5 text-teal-600">
                      <FileText className="h-4 w-4" />
                      Generated Document Preview
                    </h3>
                    <DocumentPreview
                      topic={status.topic}
                      context={status.context}
                      docxFilename={status.docx_filename}
                    />
                  </div>
                )}
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
                      Deploy cooperative AI agent loops to automatically draft, peer-review, and format publication-grade scientific and technical documents.
                    </p>
                  </div>
                </div>

                {/* Input Panel */}
                <SearchBar
                  onSearch={handleStartGeneration}
                  disabled={status.status === "RUNNING"}
                />

                {/* Active compilation summary card */}
                {status.status === "RUNNING" && (
                  <div className="p-4 rounded-xl border border-teal-500/20 bg-teal-500/5 animate-pulse text-xs flex items-center justify-between">
                    <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-500" />
                      </span>
                      <span className="font-semibold">Currently generating paper: "{status.topic}"</span>
                    </div>
                    <button
                      onClick={() => setActiveTab("fsm")}
                      className="text-teal-600 dark:text-teal-400 hover:underline font-bold flex items-center gap-1 cursor-pointer bg-transparent border-0"
                    >
                      View Logs <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                )}
                
                {status.status === "COMPLETED" && (
                  <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-xs flex items-center justify-between">
                    <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
                      ✓ Successfully generated "{status.topic}"
                    </span>
                    <button
                      onClick={() => {
                        setSelectedPaper(null)
                        setActiveTab("fsm")
                      }}
                      className="text-emerald-600 dark:text-emerald-400 hover:underline font-bold flex items-center gap-1 cursor-pointer bg-transparent border-0"
                    >
                      View Generated Document <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
