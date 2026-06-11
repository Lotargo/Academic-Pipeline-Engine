"use client"

import { useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Play, AlertCircle, CheckCircle, Terminal, RefreshCw, Layers } from "lucide-react"

type FSMState = "INIT" | "DRAFTING" | "REVIEWING" | "RENDERING" | "DONE" | "FAILED"

interface FSMMonitorProps {
  status: any
  onRetry?: () => void
}

export function FSMMonitor({ status, onRetry }: FSMMonitorProps) {
  const terminalEndRef = useRef<HTMLDivElement>(null)

  // Auto scroll terminal to bottom on new logs
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [status?.logs])

  const statesList: FSMState[] = ["INIT", "DRAFTING", "REVIEWING", "RENDERING", "DONE"]
  const activeState = status?.state || "INIT"
  const isFailed = status?.status === "FAILED" || activeState === "FAILED"

  // Get status color for each node
  const getNodeStatus = (state: FSMState) => {
    if (isFailed && activeState === state) return "failed"
    if (activeState === state) return "active"
    
    const currentIndex = statesList.indexOf(activeState as FSMState)
    const nodeIndex = statesList.indexOf(state)
    
    if (currentIndex === -1 && state === "DONE") return "idle" // if failed, done is idle
    if (nodeIndex < currentIndex) return "completed"
    return "idle"
  }

  return (
    <div className="space-y-6 w-full">
      {/* Visual Pipeline Flow */}
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <h2 className="text-sm font-semibold mb-6 flex items-center gap-2">
          <Layers className="h-4 w-4 text-teal-600 dark:text-teal-400" />
          Execution Pipeline (Finite State Machine)
        </h2>

        <div className="relative flex flex-col md:flex-row items-center justify-between gap-4 py-4 md:px-4">
          {statesList.map((state, index) => {
            const nodeStatus = getNodeStatus(state)
            
            return (
              <div key={state} className="flex flex-col md:flex-row items-center flex-1 w-full md:w-auto relative">
                {/* Node Box */}
                <div
                  className={`flex flex-col items-center justify-center p-3 rounded-xl border-2 w-32 md:w-36 h-20 transition-all duration-500 z-10 ${
                    nodeStatus === "completed"
                      ? "border-emerald-500 bg-emerald-500/5 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.1)]"
                      : nodeStatus === "active"
                      ? "border-teal-500 bg-teal-500/5 dark:bg-teal-500/10 text-teal-600 dark:text-teal-400 animate-pulse shadow-[0_0_20px_rgba(14,148,136,0.3)] font-semibold scale-105"
                      : nodeStatus === "failed"
                      ? "border-red-500 bg-red-500/5 dark:bg-red-500/10 text-red-600 dark:text-red-400 shadow-[0_0_20px_rgba(239,68,68,0.3)] font-semibold"
                      : "border-border bg-muted/20 text-muted-foreground"
                  }`}
                >
                  <span className="text-[10px] uppercase font-mono tracking-wider mb-1 opacity-70">
                    Step {index + 1}
                  </span>
                  <span className="text-xs font-bold tracking-tight text-center">{state}</span>
                  {nodeStatus === "completed" && <CheckCircle className="h-4 w-4 mt-1 text-emerald-500" />}
                  {nodeStatus === "active" && (
                    <div className="flex items-center gap-1 mt-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-teal-500 animate-ping" />
                      <span className="text-[9px] font-mono">Running...</span>
                    </div>
                  )}
                  {nodeStatus === "failed" && <AlertCircle className="h-4 w-4 mt-1 text-red-500" />}
                </div>

                {/* Connector Line (except for last element) */}
                {index < statesList.length - 1 && (
                  <div className="hidden md:block flex-1 h-0.5 bg-border relative w-full mx-2 z-0">
                    {nodeStatus === "completed" && (
                      <div className="absolute inset-0 bg-emerald-500 transition-all duration-1000" />
                    )}
                    {nodeStatus === "active" && (
                      <div className="absolute inset-0 bg-gradient-to-r from-teal-500 to-border animate-shimmer" 
                           style={{
                             backgroundSize: "200% 100%",
                             animation: "shimmer 1.5s infinite linear"
                           }}
                      />
                    )}
                  </div>
                )}
              </div>
            )
          })}

          {/* FAILED Alert Overlay box */}
          {isFailed && (
            <div className="absolute inset-0 bg-background/80 dark:bg-background/90 z-20 flex flex-col items-center justify-center p-6 rounded-2xl animate-in fade-in duration-300">
              <AlertCircle className="h-12 w-12 text-red-500 mb-2 animate-bounce" />
              <h3 className="text-lg font-bold text-red-500">Pipeline Execution Failed</h3>
              <p className="text-xs text-muted-foreground text-center max-w-md mt-1 mb-4">
                {status?.error || "An unexpected error occurred during execution. Please check the logs below."}
              </p>
              {onRetry && (
                <Button size="sm" onClick={onRetry} className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5">
                  <RefreshCw className="h-3.5 w-3.5" />
                  Configure & Restart Run
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Critiques history */}
      {status?.reviewer_feedback?.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-5 space-y-3 shadow-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Reviewer Audit Feedback
          </h3>
          <div className="space-y-2.5">
            {status.reviewer_feedback.map((critique: string, idx: number) => {
              const approved = critique.trim().toUpperCase().startsWith("APPROVED")
              return (
                <div
                  key={idx}
                  className={`p-3 rounded-lg border text-xs leading-relaxed ${
                    approved
                      ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-800 dark:text-emerald-400"
                      : "border-amber-500/30 bg-amber-500/5 text-amber-800 dark:text-amber-400"
                  }`}
                >
                  <div className="font-semibold mb-1 flex items-center justify-between">
                    <span>Attempt #{idx + 1}</span>
                    <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                      approved ? "bg-emerald-500/20" : "bg-amber-500/20"
                    }`}>
                      {approved ? "APPROVED" : "REJECTED"}
                    </span>
                  </div>
                  {critique}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Terminal Log Console */}
      <div className="rounded-2xl border border-zinc-800 bg-[#0c0c0e] text-zinc-100 p-5 shadow-2xl space-y-3">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-teal-400" />
            <span className="text-xs font-mono font-bold tracking-tight text-zinc-400">Live Agent Console Stream</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                status?.status === "RUNNING" ? "bg-teal-400" : "bg-zinc-600"
              }`} />
              <span className={`relative inline-flex rounded-full h-2 w-2 ${
                status?.status === "RUNNING" ? "bg-teal-500" : "bg-zinc-500"
              }`} />
            </span>
            <span className="text-[10px] font-mono text-zinc-500 uppercase">
              {status?.status === "RUNNING" ? "Online" : "Paused"}
            </span>
          </div>
        </div>

        <div className="h-64 md:h-80 overflow-y-auto font-mono text-xs space-y-1.5 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
          {status?.logs?.map((log: string, idx: number) => {
            let color = "text-zinc-300"
            if (log.includes("ERROR") || log.includes("[Error]")) color = "text-red-400 font-semibold"
            else if (log.includes("WARNING") || log.includes("[FSM] Exiting")) color = "text-amber-400"
            else if (log.includes("[FSM] Entering") || log.includes("approved")) color = "text-emerald-400 font-semibold"
            else if (log.includes("[Reviewer Feedback]")) color = "text-teal-400"
            
            return (
              <div key={idx} className={`${color} leading-relaxed break-all`}>
                {log}
              </div>
            )
          })}
          {status?.logs?.length === 0 && (
            <div className="text-zinc-600 italic">No execution logs logged. Trigger pipeline to start...</div>
          )}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  )
}
