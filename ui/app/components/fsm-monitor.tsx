"use client"

import { useEffect, useRef, Fragment } from "react"
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
    if (status?.status === "COMPLETED") return "completed"
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

        <div className="relative flex flex-col gap-4 py-2 px-1">
          {statesList.map((state, index) => {
            const nodeStatus = getNodeStatus(state)
            const stateDesc = {
              INIT: "Initializing compilation pipeline and overrides",
              DRAFTING: "Cooperative Writer Agent generating draft sections",
              REVIEWING: "Strict Reviewer Agent auditing academic quality",
              RENDERING: "Formatting and compiling draft to Microsoft Word",
              DONE: "Academic document compiled and ready for preview",
              FAILED: "Pipeline compilation failed due to check issues"
            }[state] || ""
            
            return (
              <Fragment key={state}>
                {/* Node Row */}
                <div className="flex items-start gap-4 w-full relative group">
                  {/* Status Circle on Left */}
                  <div
                    className={`flex items-center justify-center rounded-full border-2 w-9 h-9 shrink-0 transition-all duration-500 z-10 ${
                      nodeStatus === "completed"
                        ? "border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.15)]"
                        : nodeStatus === "active"
                        ? "border-teal-500 bg-teal-500/10 text-teal-600 dark:text-teal-400 animate-pulse shadow-[0_0_15px_rgba(14,148,136,0.3)] scale-105"
                        : nodeStatus === "failed"
                        ? "border-red-500 bg-red-500/10 text-red-600 dark:text-red-400 shadow-[0_0_15px_rgba(239,68,68,0.3)]"
                        : "border-border bg-muted/40 text-muted-foreground/60"
                    }`}
                  >
                    {nodeStatus === "completed" && <CheckCircle className="h-4.5 w-4.5 text-emerald-500" />}
                    {nodeStatus === "active" && <span className="h-2 w-2 rounded-full bg-teal-500 animate-ping" />}
                    {nodeStatus === "failed" && <AlertCircle className="h-4.5 w-4.5 text-red-500" />}
                    {nodeStatus === "idle" && <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />}
                  </div>

                  {/* Step Card on Right */}
                  <div
                    className={`flex-1 flex items-center justify-between p-3.5 rounded-xl border transition-all duration-300 ${
                      nodeStatus === "completed"
                        ? "border-emerald-500/20 bg-emerald-500/5 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                        : nodeStatus === "active"
                        ? "border-teal-500/30 bg-teal-500/5 dark:bg-teal-500/10 text-teal-600 dark:text-teal-400 shadow-sm font-semibold scale-[1.01]"
                        : nodeStatus === "failed"
                        ? "border-red-500/20 bg-red-500/5 dark:bg-red-500/10 text-red-700 dark:text-red-400"
                        : "border-border/60 bg-muted/5 text-muted-foreground/60"
                    }`}
                  >
                    <div className="flex flex-col text-left space-y-0.5">
                      <span className="text-[9px] uppercase font-mono tracking-wider opacity-60">
                        Step {index + 1}
                      </span>
                      <span className="text-xs font-bold tracking-tight text-foreground">{state}</span>
                      <span className="text-[10px] leading-tight text-muted-foreground font-sans line-clamp-2 max-w-[280px]">
                        {stateDesc}
                      </span>
                    </div>
                    
                    <div className="text-[9px] font-mono tracking-tight shrink-0 self-start mt-1">
                      {nodeStatus === "completed" && <span className="text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded font-bold uppercase">Done</span>}
                      {nodeStatus === "active" && <span className="text-teal-500 bg-teal-500/10 px-1.5 py-0.5 rounded font-bold uppercase animate-pulse">Running</span>}
                      {nodeStatus === "failed" && <span className="text-red-500 bg-red-500/10 px-1.5 py-0.5 rounded font-bold uppercase">Failed</span>}
                      {nodeStatus === "idle" && <span className="text-muted-foreground/50 bg-muted/20 px-1.5 py-0.5 rounded font-normal uppercase">Awaiting</span>}
                    </div>
                  </div>
                </div>

                {/* Vertical Connector Line (between steps) */}
                {index < statesList.length - 1 && (
                  <div className="w-0.5 h-5 bg-border dark:bg-zinc-800 ml-4.5 -my-2 relative z-0">
                    {nodeStatus === "completed" && (
                      <div className="absolute inset-0 bg-emerald-500 transition-all duration-1000" />
                    )}
                    {nodeStatus === "active" && (
                      <div className="absolute inset-0 bg-gradient-to-b from-teal-500 to-border" />
                    )}
                  </div>
                )}
              </Fragment>
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
