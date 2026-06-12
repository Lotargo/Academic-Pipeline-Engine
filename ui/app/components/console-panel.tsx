"use client"

import React, { useState, useEffect, useRef, useCallback } from "react"
import { Terminal, XCircle, Trash2, Copy, Check, ChevronDown, ChevronUp, GripHorizontal } from "lucide-react"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import type { Messages } from "@/lib/i18n"

interface ConsolePanelProps {
  status: any
  isOpen: boolean
  onClose: () => void
  height: number
  setHeight: (height: number) => void
  t: Messages
}

export function ConsolePanel({ status, isOpen, onClose, height, setHeight, t }: ConsolePanelProps) {
  const [copied, setCopied] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [isResizing, setIsResizing] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const activeState = status?.state || "INIT"
  const isRunning = status?.status === "RUNNING"
  const logs = status?.logs || []

  // Auto-scroll to bottom of logs on update
  useEffect(() => {
    if (isOpen) {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }, [logs.length, isOpen])

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

  const handleCopyLogs = () => {
    if (logs.length === 0) return
    const text = logs.join("\n")
    navigator.clipboard.writeText(text)
    setCopied(true)
    toast.success("Logs copied to clipboard")
    setTimeout(() => setCopied(false), 2000)
  }

  // Handle drag-resizing
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
  }, [])

  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      // Delta height from the bottom of the window
      const newHeight = window.innerHeight - e.clientY
      // Clamp height between 120px and 80% of window height
      const clampedHeight = Math.max(120, Math.min(newHeight, window.innerHeight * 0.8))
      setHeight(clampedHeight)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
    }

    document.addEventListener("mousemove", handleMouseMove)
    document.addEventListener("mouseup", handleMouseUp)

    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isResizing, setHeight])

  if (!isOpen) return null

  return (
    <div
      ref={containerRef}
      className={`relative w-full bg-zinc-50/95 dark:bg-[#0c0c0e]/95 border-t border-zinc-200 dark:border-zinc-800 shadow-lg flex flex-col z-40 shrink-0 transition-shadow duration-300 ${
        isResizing ? "select-none" : ""
      }`}
      style={{ height: `${height}px` }}
    >
      {/* Resizing Handle & Header */}
      <div
        className="h-10 border-b border-zinc-200 dark:border-zinc-800/80 px-4 md:px-6 flex items-center justify-between cursor-row-resize relative select-none shrink-0 group/handle hover:bg-zinc-100/50 dark:hover:bg-zinc-900/30 transition-colors"
        onMouseDown={handleMouseDown}
      >
        {/* Resize Grip Visual */}
        <div className="absolute top-0.5 left-1/2 -translate-x-1/2 flex items-center justify-center opacity-40 group-hover/handle:opacity-85 transition-opacity">
          <GripHorizontal className="h-3.5 w-3.5 text-zinc-500" />
        </div>

        {/* Panel Title */}
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-teal-600 dark:text-teal-400" />
          <span className="text-xs font-mono font-bold tracking-tight text-zinc-700 dark:text-zinc-300">
            {t.fsm.console}
          </span>
          
          {/* Status Indicator */}
          <div className="flex items-center gap-1.5 ml-4">
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  isRunning ? "bg-teal-400" : "bg-zinc-400 dark:bg-zinc-600"
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  isRunning ? "bg-teal-500" : "bg-zinc-500"
                }`}
              />
            </span>
            <span className="text-[10px] font-mono text-zinc-500 uppercase">
              {isRunning ? t.fsm.online : t.fsm.paused}
            </span>
          </div>
        </div>

        {/* Console Controls */}
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {isRunning && (
            <Button
              size="sm"
              variant="outline"
              onClick={handleCancel}
              disabled={cancelling}
              className="h-7 px-3 text-[10px] font-bold uppercase border-red-500/20 text-red-600 dark:text-red-400 hover:bg-red-500/10 hover:border-red-500/40 gap-1.5 cursor-pointer"
            >
              <XCircle className="h-3 w-3" />
              {cancelling ? "Cancelling..." : "Cancel"}
            </Button>
          )}

          <button
            onClick={handleCopyLogs}
            disabled={logs.length === 0}
            className="p-1.5 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors disabled:opacity-40 cursor-pointer border-0"
            title="Copy Logs"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
          </button>

          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors cursor-pointer border-0"
            title="Hide Console"
          >
            <ChevronDown className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Log Output Area */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 md:p-6 font-mono text-[11px] md:text-xs space-y-1 bg-white/50 dark:bg-black/20">
        <div className="max-w-7xl mx-auto space-y-1.5">
          {logs.map((log: string, idx: number) => {
            let color = "text-zinc-600 dark:text-zinc-350"
            if (log.includes("ERROR") || log.includes("[Error]")) color = "text-rose-600 dark:text-red-400 font-semibold"
            else if (log.includes("WARNING") || log.includes("[FSM] Exiting")) color = "text-amber-600 dark:text-amber-400 font-medium"
            else if (log.includes("[FSM] Entering") || log.includes("approved")) color = "text-emerald-600 dark:text-emerald-400 font-semibold"
            else if (log.includes("[Reviewer Feedback]")) color = "text-teal-600 dark:text-teal-400 font-medium"

            return (
              <div key={idx} className={`${color} leading-relaxed break-all font-mono whitespace-pre-wrap`}>
                {log}
              </div>
            )
          })}
          {logs.length === 0 && (
            <div className="text-zinc-400 dark:text-zinc-650 italic">
              No logs registered. Start the pipeline process to see execution logs here.
            </div>
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  )
}
