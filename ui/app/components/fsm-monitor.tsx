"use client"

import { Fragment, useState } from "react"
import { Button } from "@/components/ui/button"
import { AlertCircle, CheckCircle, RefreshCw, Layers, XCircle, MessageSquare } from "lucide-react"
import { toast } from "sonner"
import type { Messages } from "@/lib/i18n"

type FSMState = "INIT" | "PLANNING" | "DRAFTING" | "REVIEWING" | "RENDERING" | "DONE" | "FAILED" | "CANCELLED"

interface FSMMonitorProps {
  status: any
  onRetry?: () => void
  t: Messages
}

export function FSMMonitor({ status, onRetry, t }: FSMMonitorProps) {
  const statesList: FSMState[] = ["INIT", "PLANNING", "DRAFTING", "REVIEWING", "RENDERING", "DONE"]
  const activeState = status?.state || "INIT"
  const isFailed = status?.status === "FAILED" || activeState === "FAILED"
  const isCancelled = status?.status === "CANCELLED" || activeState === "CANCELLED"
  const [cancelling, setCancelling] = useState(false)

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
    <div className="space-y-6 w-full lg:h-full">
      {/* Visual Pipeline Flow */}
      <div className="rounded-2xl border border-border/80 bg-card/65 backdrop-blur-sm p-6 shadow-sm transition-all duration-300 hover:shadow-md lg:min-h-full">
        <h2 className="text-sm font-semibold mb-6 flex items-center gap-2 text-foreground/90">
          <Layers className="h-4 w-4 text-sky-500 dark:text-sky-400" />
          {t.fsm.title}
        </h2>

        <div className="relative flex flex-col gap-4 py-2 px-1">
          {statesList.map((state, index) => {
            const nodeStatus = getNodeStatus(state)
            const stateDesc = {
              INIT: t.fsm.initDesc,
              PLANNING: t.fsm.planningDesc,
              DRAFTING: t.fsm.draftingDesc,
              REVIEWING: t.fsm.reviewingDesc,
              RENDERING: t.fsm.renderingDesc,
              DONE: t.fsm.doneDesc,
              FAILED: t.fsm.failedDesc,
              CANCELLED: ""
            }[state] || ""
            
            return (
              <Fragment key={state}>
                {/* Node Row */}
                <div className="flex items-center gap-4 w-full relative group">
                  {/* Status Circle on Left */}
                  <div
                    className={`flex items-center justify-center rounded-full border-2 w-10 h-10 shrink-0 transition-all duration-300 z-10 ${
                      nodeStatus === "completed"
                        ? "border-sky-500 bg-sky-500/10 text-sky-600 dark:text-sky-400 shadow-sm"
                        : nodeStatus === "active"
                        ? "border-cyan-500 bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.25)] scale-105"
                        : nodeStatus === "failed"
                        ? "border-rose-500 bg-rose-500/10 text-rose-600 dark:text-rose-400"
                        : "border-border/60 bg-muted/20 text-muted-foreground/40"
                    }`}
                  >
                    {nodeStatus === "completed" && <CheckCircle className="h-5 w-5 text-sky-500 dark:text-sky-400" />}
                    {nodeStatus === "active" && <span className="h-2.5 w-2.5 rounded-full bg-cyan-500 animate-pulse" />}
                    {nodeStatus === "failed" && <AlertCircle className="h-5 w-5 text-rose-500" />}
                    {nodeStatus === "idle" && <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />}
                  </div>

                  {/* Step Card on Right */}
                  <div
                    className={`flex-1 h-[84px] flex items-center justify-between gap-3 p-4 rounded-xl border transition-all duration-300 ${
                      nodeStatus === "completed"
                        ? "border-sky-500/15 bg-sky-500/5 dark:bg-sky-950/10 text-sky-950 dark:text-sky-100 shadow-xs hover:border-sky-500/25"
                        : nodeStatus === "active"
                        ? "border-cyan-500/35 bg-cyan-500/5 dark:bg-cyan-950/15 text-cyan-950 dark:text-cyan-100 shadow-[0_4px_12px_rgba(6,182,212,0.05)] hover:border-cyan-500/50"
                        : nodeStatus === "failed"
                        ? "border-rose-500/20 bg-rose-500/5 dark:bg-rose-950/10 text-rose-950 dark:text-rose-100"
                        : "border-border/40 bg-muted/5 text-muted-foreground/50 hover:border-border/60"
                    }`}
                  >
                    <div className="flex min-w-0 flex-col text-left space-y-0.5">
                      <span className="text-[9px] uppercase font-mono font-bold tracking-wider opacity-60">
                        {t.fsm.step} {index + 1}
                      </span>
                      <span className="text-xs font-bold tracking-tight text-foreground">{state}</span>
                      <span className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground font-sans max-w-[320px]">
                        {stateDesc}
                      </span>
                    </div>
                    
                    <div className="text-[9px] font-mono tracking-tight shrink-0 self-start mt-1">
                      {nodeStatus === "completed" && <span className="text-sky-600 dark:text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded font-bold uppercase">{t.fsm.done}</span>}
                      {nodeStatus === "active" && <span className="text-cyan-600 dark:text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded font-bold uppercase animate-pulse">{t.fsm.running}</span>}
                      {nodeStatus === "failed" && <span className="text-rose-600 dark:text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded font-bold uppercase">{t.fsm.failed}</span>}
                      {nodeStatus === "idle" && <span className="text-muted-foreground/60 bg-muted/20 px-2 py-0.5 rounded font-medium uppercase">{t.fsm.awaiting}</span>}
                    </div>
                  </div>
                </div>

                {/* Vertical Connector Line (between steps) */}
                {index < statesList.length - 1 && (
                  <div className="w-[2px] h-6 bg-border dark:bg-zinc-800 ml-4.5 -my-2 relative z-0">
                    {nodeStatus === "completed" && (
                      <div className="absolute inset-0 bg-sky-500 transition-all duration-1000" />
                    )}
                    {nodeStatus === "active" && (
                      <div className="absolute inset-0 bg-gradient-to-b from-cyan-500 to-border dark:to-zinc-800" />
                    )}
                  </div>
                )}
              </Fragment>
            )
          })}

          {/* FAILED Alert Overlay box */}
          {(isFailed || isCancelled) && (
            <div className="absolute inset-0 bg-background/80 dark:bg-background/90 z-20 flex flex-col items-center justify-center p-6 rounded-2xl animate-in fade-in duration-300 border border-border/40 backdrop-blur-xs">
              {isCancelled ? (
                <>
                  <XCircle className="h-12 w-12 text-amber-500 mb-2" />
                  <h3 className="text-base font-bold text-amber-500">Pipeline Cancelled</h3>
                  <p className="text-xs text-muted-foreground text-center max-w-md mt-1 mb-4">
                    Pipeline execution was cancelled by user request.
                  </p>
                </>
              ) : (
                <>
                  <AlertCircle className="h-12 w-12 text-red-500 mb-2 animate-bounce" />
                  <h3 className="text-base font-bold text-red-500">Pipeline Execution Failed</h3>
                  <p className="text-xs text-muted-foreground text-center max-w-md mt-1 mb-4">
                    {status?.error || "An unexpected error occurred during execution. Please check the logs below."}
                  </p>
                </>
              )}
              {onRetry && (
                <Button size="sm" onClick={onRetry} className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5 cursor-pointer">
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
        <div className="rounded-2xl border border-border bg-card/65 backdrop-blur-sm p-6 space-y-4 shadow-sm transition-all duration-300 hover:shadow-md">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <MessageSquare className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
            {t.fsm.feedback}
          </h3>
          <div className="space-y-3">
            {status.reviewer_feedback.map((critique: string, idx: number) => {
              const approved = critique.trim().toUpperCase().startsWith("APPROVED")
              return (
                <div
                  key={idx}
                  className={`p-4 rounded-xl border text-xs leading-relaxed transition-all duration-200 ${
                    approved
                      ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-900 dark:text-emerald-300 hover:border-emerald-500/35"
                      : "border-amber-500/25 bg-amber-500/5 text-amber-900 dark:text-amber-300 hover:border-amber-500/40"
                  }`}
                >
                  <div className="font-semibold mb-2 flex items-center justify-between">
                    <span className="font-mono text-[10px] uppercase opacity-75">Feedback Attempt #{idx + 1}</span>
                    <span className={`text-[9px] uppercase font-black px-2 py-0.5 rounded-full ${
                      approved 
                        ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" 
                        : "bg-amber-500/15 text-amber-600 dark:text-amber-400 animate-pulse"
                    }`}>
                      {approved ? "APPROVED" : "CORRECTION REQUIRED"}
                    </span>
                  </div>
                  <div className="font-sans whitespace-pre-line text-zinc-700 dark:text-zinc-300 leading-relaxed text-[11px]">
                    {critique}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
