"use client"

import { Fragment } from "react"
import { Button } from "@/components/ui/button"
import { AlertCircle, CheckCircle2, Circle, Loader2, RefreshCw, Layers, XCircle, MessageSquare } from "lucide-react"
import type { Messages } from "@/lib/i18n"
import { Win11Loader } from "./win11-loader"

type FSMState = "INIT" | "PLANNING" | "DRAFTING" | "REVIEWING" | "RENDERING" | "DONE" | "FAILED" | "CANCELLED"

interface FSMMonitorProps {
  status: any
  onRetry?: () => void
  t: Messages
}

export function FSMMonitor({ status, onRetry, t }: FSMMonitorProps) {
  const statesList: FSMState[] = ["INIT", "PLANNING", "DRAFTING", "REVIEWING", "RENDERING", "DONE"]
  const activeState = status?.state || "INIT"
  const runStatus = status?.status || "IDLE"
  const hasPipelineActivity = runStatus !== "IDLE"
  const isFailed = status?.status === "FAILED" || activeState === "FAILED"
  const isCancelled = status?.status === "CANCELLED" || activeState === "CANCELLED"

  // Get status color for each node
  const getNodeStatus = (state: FSMState) => {
    if (!hasPipelineActivity) return "idle"
    if (status?.status === "COMPLETED") return "completed"
    if (isFailed && activeState === state) return "failed"
    if (activeState === state) return "active"
    
    const currentIndex = statesList.indexOf(activeState as FSMState)
    const nodeIndex = statesList.indexOf(state)
    
    if (currentIndex === -1 && state === "DONE") return "idle" // if failed, done is idle
    if (nodeIndex < currentIndex) return "completed"
    return "idle"
  }

  const getStepDetail = (state: FSMState, nodeStatus: string) => {
    const context = status?.context && typeof status.context === "object" ? status.context : {}
    const draftedSections = Object.keys(context).filter((key) => key !== "document_plan" && context[key]).length
    const activeSection = status?.active_section
      ? humanizeLabel(String(status.active_section))
      : ""
    const feedbackCount = Array.isArray(status?.reviewer_feedback) ? status.reviewer_feedback.length : 0
    const templateLabel = status?.template_id || status?.template_mode || status?.runtime_template?.name

    if (nodeStatus === "failed") {
      return status?.error || "Check console for the failure details."
    }

    if (nodeStatus === "idle") {
      if (!hasPipelineActivity) return state === "INIT" ? "Waiting for a generation request." : "Pipeline has not started."
      return state === "DONE" ? "Waiting for draft approval." : "Waiting for previous step."
    }

    if (state === "INIT") {
      if (nodeStatus === "active") return status?.topic ? `Preparing run for "${status.topic}".` : "Preparing pipeline settings."
      return templateLabel ? `Template resolved: ${templateLabel}.` : "Run settings initialized."
    }

    if (state === "PLANNING") {
      if (nodeStatus === "active") return "Planner is shaping the document outline."
      return status?.document_plan || context.document_plan ? "Document outline is ready." : "Planning completed."
    }

    if (state === "DRAFTING") {
      if (nodeStatus === "active") {
        return activeSection ? `Writing section: ${activeSection}.` : `${draftedSections} section(s) drafted so far.`
      }
      return draftedSections > 0 ? `${draftedSections} section(s) drafted.` : "Draft sections prepared."
    }

    if (state === "REVIEWING") {
      if (nodeStatus === "active") return feedbackCount > 0 ? `Reviewer pass ${feedbackCount + 1} in progress.` : "Reviewer is checking quality."
      return feedbackCount > 0 ? `${feedbackCount} reviewer feedback item(s).` : "Review completed."
    }

    if (state === "RENDERING") {
      if (nodeStatus === "active") return "DOCX export stage is available on demand."
      return status?.export_report ? `Export QA: ${status.export_report.status || "recorded"}.` : "Export stage ready."
    }

    if (state === "DONE") {
      return status?.docx_filename ? `DOCX ready: ${status.docx_filename}.` : "Draft ready for preview and export."
    }

    return ""
  }

  const getStatusIcon = (nodeStatus: string) => {
    if (nodeStatus === "completed") {
      return <CheckCircle2 className="h-5 w-5 text-ape-info-text" />
    }
    if (nodeStatus === "active") {
      return <Win11Loader size="md" className="text-ape-primary" />
    }
    if (nodeStatus === "failed") {
      return <AlertCircle className="h-5 w-5 text-ape-danger-text" />
    }
    return <Circle className="h-4 w-4 text-muted-foreground/35" />
  }

  return (
    <div className="space-y-6 w-full lg:h-full">
      {/* Visual Pipeline Flow */}
      <div className="rounded-2xl border border-border/80 bg-card/65 backdrop-blur-sm p-6 shadow-sm transition-all duration-300 hover:shadow-md lg:min-h-full">
        <h2 className="text-sm font-semibold mb-6 flex items-center gap-2 text-foreground/90">
          <Layers className="h-4 w-4 text-ape-info-text" />
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
            const stepDetail = getStepDetail(state, nodeStatus)
            
            return (
              <Fragment key={state}>
                {/* Node Row */}
                <div className="flex items-center gap-4 w-full relative group">
                  {/* Status Indicator on Left */}
                  <div
                    className={`flex items-center justify-center rounded-full border w-10 h-10 shrink-0 transition-all duration-300 z-10 ${
                      nodeStatus === "completed"
                        ? "border-ape-info/35 bg-ape-info-soft text-ape-info-text shadow-sm"
                      : nodeStatus === "active"
                        ? "border-ape-primary/45 bg-ape-primary-soft text-ape-primary-text shadow-sm scale-105"
                      : nodeStatus === "failed"
                        ? "border-ape-danger/45 bg-ape-danger-soft text-ape-danger-text"
                        : "border-border/60 bg-muted/20 text-muted-foreground/40"
                    }`}
                  >
                    {getStatusIcon(nodeStatus)}
                  </div>

                  {/* Step Card on Right */}
                  <div
                    className={`flex-1 min-h-[92px] flex items-center justify-between gap-3 p-4 rounded-xl border transition-all duration-300 ${
                      nodeStatus === "completed"
                        ? "border-ape-info/20 bg-ape-info-soft/60 text-foreground shadow-xs hover:border-ape-info/30"
                        : nodeStatus === "active"
                        ? "border-ape-primary/35 bg-ape-primary-soft text-foreground shadow-sm hover:border-ape-primary/50"
                        : nodeStatus === "failed"
                        ? "border-ape-danger/25 bg-ape-danger-soft text-foreground"
                        : "border-border/40 bg-muted/5 text-muted-foreground/50 hover:border-border/60"
                    }`}
                  >
                    <div className="flex min-w-0 flex-col text-left space-y-0.5">
                      <span className="text-[10px] uppercase font-mono font-bold tracking-wider opacity-65">
                        {t.fsm.step} {index + 1}
                      </span>
                      <span className="text-[13px] font-bold tracking-tight text-foreground">{state}</span>
                      <span className="line-clamp-2 text-[12px] leading-relaxed text-muted-foreground font-sans max-w-[320px]">
                        {stateDesc}
                      </span>
                      <span
                        className={`line-clamp-1 text-[11px] leading-relaxed font-sans ${
                          nodeStatus === "active"
                            ? "text-ape-primary-text"
                            : nodeStatus === "completed"
                            ? "text-ape-info-text"
                            : nodeStatus === "failed"
                            ? "text-ape-danger-text"
                            : "text-muted-foreground/60"
                        }`}
                      >
                        {stepDetail}
                      </span>
                    </div>
                    
                    <div className="text-[10px] font-mono tracking-tight shrink-0 self-start mt-1">
                      {nodeStatus === "completed" && <span className="bg-ape-info-soft text-ape-info-text px-2 py-0.5 rounded font-bold uppercase">{t.fsm.done}</span>}
                      {nodeStatus === "active" && <span className="bg-ape-primary-soft text-ape-primary-text px-2 py-0.5 rounded font-bold uppercase animate-pulse">{t.fsm.running}</span>}
                      {nodeStatus === "failed" && <span className="bg-ape-danger-soft text-ape-danger-text px-2 py-0.5 rounded font-bold uppercase">{t.fsm.failed}</span>}
                      {nodeStatus === "idle" && <span className="text-muted-foreground/60 bg-muted/20 px-2 py-0.5 rounded font-medium uppercase">{t.fsm.awaiting}</span>}
                    </div>
                  </div>
                </div>

                {/* Vertical Connector Line (between steps) */}
                {index < statesList.length - 1 && (
                  <div className="w-[2px] h-6 bg-border dark:bg-zinc-800 ml-4.5 -my-2 relative z-0">
                    {nodeStatus === "completed" && (
                      <div className="absolute inset-0 bg-ape-info transition-all duration-1000" />
                    )}
                    {nodeStatus === "active" && (
                      <div className="absolute inset-0 bg-gradient-to-b from-ape-primary to-border dark:to-zinc-800" />
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
                  <XCircle className="h-12 w-12 text-ape-warning-text mb-2" />
                  <h3 className="text-base font-bold text-ape-warning-text">Pipeline Cancelled</h3>
                  <p className="text-xs text-muted-foreground text-center max-w-md mt-1 mb-4">
                    Pipeline execution was cancelled by user request.
                  </p>
                </>
              ) : (
                <>
                  <AlertCircle className="h-12 w-12 text-ape-danger-text mb-2 animate-bounce" />
                  <h3 className="text-base font-bold text-ape-danger-text">Pipeline Execution Failed</h3>
                  <p className="text-xs text-muted-foreground text-center max-w-md mt-1 mb-4">
                    {status?.error || "An unexpected error occurred during execution. Please check the logs below."}
                  </p>
                </>
              )}
              {onRetry && (
                <Button size="sm" onClick={onRetry} className="bg-ape-primary hover:bg-ape-primary/90 text-white gap-1.5 cursor-pointer">
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
            <MessageSquare className="h-3.5 w-3.5 text-ape-primary-text" />
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
                      ? "ape-status-success hover:border-ape-success/35"
                      : "ape-status-warning hover:border-ape-warning/40"
                  }`}
                >
                  <div className="font-semibold mb-2 flex items-center justify-between">
                    <span className="font-mono text-[10px] uppercase opacity-75">Feedback Attempt #{idx + 1}</span>
                    <span className={`text-[10px] uppercase font-black px-2 py-0.5 rounded-full ${
                      approved 
                        ? "bg-ape-success-soft text-ape-success-text"
                        : "bg-ape-warning-soft text-ape-warning-text animate-pulse"
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

function humanizeLabel(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}
