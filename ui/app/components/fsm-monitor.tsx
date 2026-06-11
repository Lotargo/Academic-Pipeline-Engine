"use client"

import { Fragment, useState } from "react"
import { Button } from "@/components/ui/button"
import { Play, AlertCircle, CheckCircle, Terminal, RefreshCw, Layers, XCircle } from "lucide-react"
import { toast } from "sonner"
import type { Messages } from "@/lib/i18n"

type FSMState = "INIT" | "DRAFTING" | "REVIEWING" | "RENDERING" | "DONE" | "FAILED" | "CANCELLED"

interface FSMMonitorProps {
  status: any
  onRetry?: () => void
  t: Messages
}

export function FSMMonitor({ status, onRetry, t }: FSMMonitorProps) {
  const statesList: FSMState[] = ["INIT", "DRAFTING", "REVIEWING", "RENDERING", "DONE"]
  const activeState = status?.state || "INIT"
  const isFailed = status?.status === "FAILED" || activeState === "FAILED"
  const isCancelled = status?.status === "CANCELLED" || activeState === "CANCELLED"
  const isRunning = status?.status === "RUNNING"
  const [cancelling, setCancelling] = useState(false)

  const handleCancel = async () => {
    setCancelling(true)
    try {
      const res = await fetch("/api/cancel", { method: "POST" })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to cancel pipeline")
      }
      toast.info("Pipeline cancellation requested")
    } catch (e: any) {
      toast.error(e.message || "Failed to cancel")
    } finally {
      setCancelling(false)
    }
  }

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
        <h2 className="text-base font-semibold mb-6 flex items-center gap-2">
          <Layers className="h-4 w-4 text-sky-600 dark:text-sky-300" />
          {t.fsm.title}
        </h2>

        <div className="relative flex flex-col gap-4 py-2 px-1">
          {statesList.map((state, index) => {
            const nodeStatus = getNodeStatus(state)
            const stateDesc = {
              INIT: t.fsm.initDesc,
              DRAFTING: t.fsm.draftingDesc,
              REVIEWING: t.fsm.reviewingDesc,
              RENDERING: t.fsm.renderingDesc,
              DONE: t.fsm.doneDesc,
              FAILED: t.fsm.failedDesc
            }[state] || ""
            
            return (
              <Fragment key={state}>
                {/* Node Row */}
                <div className="flex items-start gap-4 w-full relative group">
                  {/* Status Circle on Left */}
                  <div
                    className={`flex items-center justify-center rounded-full border-2 w-10 h-10 shrink-0 transition-all duration-300 z-10 ${
                      nodeStatus === "completed"
                        ? "border-sky-400 bg-sky-400/10 text-sky-700 dark:text-sky-300"
                        : nodeStatus === "active"
                        ? "border-cyan-400 bg-cyan-400/10 text-cyan-700 dark:text-cyan-300 shadow-sm scale-105"
                        : nodeStatus === "failed"
                        ? "border-rose-400 bg-rose-400/10 text-rose-700 dark:text-rose-300"
                        : "border-border bg-muted/40 text-muted-foreground/60"
                    }`}
                  >
                    {nodeStatus === "completed" && <CheckCircle className="h-5 w-5 text-sky-500" />}
                    {nodeStatus === "active" && <span className="h-2.5 w-2.5 rounded-full bg-cyan-500 animate-pulse" />}
                    {nodeStatus === "failed" && <AlertCircle className="h-5 w-5 text-rose-500" />}
                    {nodeStatus === "idle" && <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />}
                  </div>

                  {/* Step Card on Right */}
                  <div
                    className={`flex-1 flex items-center justify-between p-3.5 rounded-xl border transition-all duration-300 ${
                      nodeStatus === "completed"
                        ? "border-sky-400/25 bg-sky-400/10 dark:bg-sky-400/10 text-sky-800 dark:text-sky-200"
                        : nodeStatus === "active"
                        ? "border-cyan-400/35 bg-cyan-400/10 dark:bg-cyan-400/10 text-cyan-800 dark:text-cyan-200 shadow-sm font-semibold"
                        : nodeStatus === "failed"
                        ? "border-rose-400/25 bg-rose-400/10 dark:bg-rose-400/10 text-rose-800 dark:text-rose-200"
                        : "border-border/60 bg-muted/5 text-muted-foreground/60"
                    }`}
                  >
                    <div className="flex flex-col text-left space-y-0.5">
                      <span className="text-[11px] uppercase font-mono tracking-wider opacity-80">
                        {t.fsm.step} {index + 1}
                      </span>
                      <span className="text-sm font-bold tracking-tight text-foreground">{state}</span>
                      <span className="text-xs leading-snug text-muted-foreground font-sans max-w-[320px]">
                        {stateDesc}
                      </span>
                    </div>
                    
                    <div className="text-[9px] font-mono tracking-tight shrink-0 self-start mt-1">
                      {nodeStatus === "completed" && <span className="text-sky-600 dark:text-sky-300 bg-sky-500/10 px-2 py-1 rounded font-bold uppercase">{t.fsm.done}</span>}
                      {nodeStatus === "active" && <span className="text-cyan-600 dark:text-cyan-300 bg-cyan-500/10 px-2 py-1 rounded font-bold uppercase animate-pulse">{t.fsm.running}</span>}
                      {nodeStatus === "failed" && <span className="text-rose-600 dark:text-rose-300 bg-rose-500/10 px-2 py-1 rounded font-bold uppercase">{t.fsm.failed}</span>}
                      {nodeStatus === "idle" && <span className="text-muted-foreground/60 bg-muted/30 px-2 py-1 rounded font-normal uppercase">{t.fsm.awaiting}</span>}
                    </div>
                  </div>
                </div>

                {/* Vertical Connector Line (between steps) */}
                {index < statesList.length - 1 && (
                  <div className="w-0.5 h-5 bg-border dark:bg-zinc-800 ml-4.5 -my-2 relative z-0">
                    {nodeStatus === "completed" && (
                      <div className="absolute inset-0 bg-sky-400 transition-all duration-1000" />
                    )}
                    {nodeStatus === "active" && (
                      <div className="absolute inset-0 bg-gradient-to-b from-cyan-400 to-border" />
                    )}
                  </div>
                )}
              </Fragment>
            )
          })}

          {/* FAILED Alert Overlay box */}
          {(isFailed || isCancelled) && (
            <div className="absolute inset-0 bg-background/80 dark:bg-background/90 z-20 flex flex-col items-center justify-center p-6 rounded-2xl animate-in fade-in duration-300">
              {isCancelled ? (
                <>
                  <XCircle className="h-12 w-12 text-amber-500 mb-2" />
                  <h3 className="text-lg font-bold text-amber-500">Pipeline Cancelled</h3>
                  <p className="text-xs text-muted-foreground text-center max-w-md mt-1 mb-4">
                    Pipeline execution was cancelled by user request.
                  </p>
                </>
              ) : (
                <>
                  <AlertCircle className="h-12 w-12 text-red-500 mb-2 animate-bounce" />
                  <h3 className="text-lg font-bold text-red-500">Pipeline Execution Failed</h3>
                  <p className="text-xs text-muted-foreground text-center max-w-md mt-1 mb-4">
                    {status?.error || "An unexpected error occurred during execution. Please check the logs below."}
                  </p>
                </>
              )}
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
            {t.fsm.feedback}
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
            <span className="text-xs font-mono font-bold tracking-tight text-zinc-300">{t.fsm.console}</span>
          </div>
          <div className="flex items-center gap-3">
            {isRunning && (
              <Button
                size="sm"
                variant="outline"
                onClick={handleCancel}
                disabled={cancelling}
                className="h-7 px-3 text-[10px] font-bold uppercase border-red-500/30 text-red-400 hover:bg-red-500/10 hover:border-red-500/50 gap-1.5"
              >
                <XCircle className="h-3 w-3" />
                {cancelling ? "Cancelling..." : "Cancel"}
              </Button>
            )}
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  isRunning ? "bg-teal-400" : "bg-zinc-600"
                }`} />
                <span className={`relative inline-flex rounded-full h-2 w-2 ${
                  isRunning ? "bg-teal-500" : "bg-zinc-500"
                }`} />
              </span>
              <span className="text-[10px] font-mono text-zinc-500 uppercase">
                {isRunning ? t.fsm.online : t.fsm.paused}
              </span>
            </div>
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
        </div>
      </div>
    </div>
  )
}
