"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Search, Sparkles, BookOpen, ChevronRight, HelpCircle, RotateCw } from "lucide-react"
import type { Messages } from "@/lib/i18n"
import { toast } from "sonner"

interface SearchBarProps {
  onSearch?: (topic: string, instructions: string, academicMode: boolean) => void
  disabled?: boolean
  t: Messages
}

export function SearchBar({ onSearch, disabled, t }: SearchBarProps) {
  const [topic, setTopic] = useState("")
  const [instructions, setInstructions] = useState("")
  const [isFocused, setIsFocused] = useState(false)
  const [academicMode, setAcademicMode] = useState(false)
  const [examples, setExamples] = useState<{ topic: string; instructions: string }[]>([])
  const [ttl, setTtl] = useState<number>(0)
  const [refreshing, setRefreshing] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = "auto"
    textarea.style.height = `${textarea.scrollHeight}px`
  }, [instructions])

  const handleManualRefresh = async () => {
    if (refreshing) return
    setRefreshing(true)
    try {
      const res = await fetch("/api/examples/refresh", { method: "POST" })
      if (res.ok) {
        const data = await res.json()
        setExamples(data.examples || [])
        setTtl(data.ttl || 0)
        toast.success("Examples refreshed successfully!")
      } else {
        toast.error("Failed to refresh examples.")
      }
    } catch (e) {
      console.error("Error refreshing examples manually:", e)
      toast.error("Failed to refresh examples.")
    } finally {
      setRefreshing(false)
    }
  }

  const fetchExamples = async () => {
    try {
      const res = await fetch(`/api/examples?client_time=${Date.now()}`)
      if (res.ok) {
        const data = await res.json()
        setExamples(data.examples || [])
        setTtl(data.ttl || 0)
      }
    } catch (e) {
      console.error("Error fetching dynamic examples:", e)
    }
  }

  useEffect(() => {
    fetchExamples()

    const handleConfigSaved = () => {
      fetchExamples()
    }
    window.addEventListener("ape-config-saved", handleConfigSaved)

    return () => {
      window.removeEventListener("ape-config-saved", handleConfigSaved)
    }
  }, [])

  useEffect(() => {
    if (ttl <= 0) return

    const timer = setInterval(() => {
      setTtl(prev => {
        if (prev <= 1) {
          clearInterval(timer)
          fetch(`/api/examples?client_time=${Date.now()}`)
            .then(res => {
              if (res.ok) return res.json()
            })
            .then(data => {
              if (data) {
                setExamples(data.examples || [])
                setTtl(data.ttl || 0)
              }
            })
            .catch(err => console.error("Error refreshing examples:", err))
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [ttl])

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!topic.trim()) return
    onSearch?.(topic.trim(), instructions.trim(), academicMode)
  }

  const loadSuggestion = (sTopic: string, sInst: string) => {
    setTopic(sTopic)
    setInstructions(sInst)
  }

  return (
    <div className="space-y-5 w-full">
      <form
        onSubmit={handleGenerate}
        className={`animate-in fade-in slide-in-from-bottom-4 duration-500 rounded-xl border bg-card p-4 shadow-sm transition-all hover:shadow-md ${
          isFocused ? "border-ape-primary/50 ring-1 ring-ape-primary/20" : "border-ape-primary/20 hover:border-ape-primary/30"
        }`}
      >
        <div className="space-y-3">
          {/* Primary Topic Input */}
          <div className="flex items-center gap-2 border-b border-border/60 pb-2">
            <BookOpen className="h-5 w-5 text-ape-primary-text shrink-0" />
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              disabled={disabled}
              placeholder={t.search.topicPlaceholder}
              className="w-full border-0 bg-transparent text-[15px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none py-1.5"
              required
            />
          </div>

          {/* Guidelines Textarea */}
          <div className="pt-1">
            <textarea
              ref={textareaRef}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              disabled={disabled}
              placeholder={t.search.instructionsPlaceholder}
              rows={2}
              className="w-full border-0 bg-transparent text-[13px] text-foreground placeholder:text-muted-foreground/55 focus:outline-none resize-none leading-relaxed py-1 transition-[height] duration-200 ease-out overflow-hidden"
            />
          </div>

          {/* Sandbox Status Banner */}
          {academicMode && (
            <div className="animate-in fade-in slide-in-from-top-1 duration-300 flex items-center gap-1.5 px-3 py-1.5 rounded-lg ape-status-warning border text-[10px] font-sans font-bold uppercase tracking-wider select-none">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ape-warning opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-ape-warning" />
              </span>
              <span>{t.search.sandboxEnabled}</span>
            </div>
          )}

          {/* Action Footer */}
          <div className="flex items-center justify-between pt-2 border-t border-border/40 gap-4 flex-wrap">
            <div className="flex items-center gap-1.5 ape-micro">
              <Sparkles className="h-3 w-3 text-ape-primary animate-pulse" />
              <span>{t.search.footer}</span>
            </div>
            
            {/* Mode Switcher */}
            <div className="flex items-center gap-1 bg-muted/60 dark:bg-ape-surface-subtle p-1 rounded-xl border border-border/50 text-[11px] font-bold">
              <button
                type="button"
                onClick={() => setAcademicMode(false)}
                className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer border-0 flex items-center gap-1 ${
                  !academicMode
                    ? "ape-status-primary border"
                    : "text-muted-foreground hover:text-foreground bg-transparent"
                }`}
              >
                {t.search.modeStandard}
              </button>
              <button
                type="button"
                onClick={() => setAcademicMode(true)}
                className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer border-0 flex items-center gap-1 ${
                  academicMode
                    ? "ape-status-warning border"
                    : "text-muted-foreground hover:text-foreground bg-transparent"
                }`}
              >
                {t.search.modeAcademic}
              </button>
            </div>
            
            <Button
              type="submit"
              disabled={disabled || !topic.trim()}
              className="h-9 px-4 rounded-xl bg-ape-primary hover:bg-ape-primary/90 text-white font-bold text-xs gap-1.5 select-none transition-all active:scale-95 shadow-sm disabled:opacity-50 disabled:scale-100"
            >
              <span>{t.search.compile}</span>
              <ChevronRight className="h-4.5 w-4.5" />
            </Button>
          </div>
        </div>
      </form>

      {/* Suggested Templates */}
      <div className="animate-in fade-in slide-in-from-bottom-5 duration-600 space-y-3">
        <h3 className="ape-label flex items-center gap-1.5 flex-wrap">
          <HelpCircle className="h-3 w-3 shrink-0" />
          <span>{t.search.templates}</span>
          {ttl > 0 && (
            <span className="px-1.5 py-0.5 text-[9px] bg-ape-primary-soft text-ape-primary-text rounded-full font-mono font-bold uppercase tracking-wider animate-pulse border border-ape-primary/15">
              Refresh in {Math.floor(ttl / 60)}:{(ttl % 60).toString().padStart(2, '0')}
            </span>
          )}
          <button
            type="button"
            onClick={handleManualRefresh}
            disabled={refreshing}
            className="ml-auto md:ml-2 p-1 text-ape-primary-text hover:bg-ape-primary-soft rounded transition-all cursor-pointer border-0 bg-transparent flex items-center justify-center disabled:opacity-50"
            title="Generate new templates now"
          >
            <RotateCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
          </button>
        </h3>
        <div className="flex flex-wrap gap-x-2 gap-y-3">
          {examples.map((example, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => loadSuggestion(example.topic, example.instructions)}
              className="px-3 py-2 rounded-lg border border-border/60 bg-card hover:bg-accent/40 text-[13px] leading-snug text-foreground font-semibold hover:border-ape-primary/30 transition-all cursor-pointer text-left"
            >
              {example.topic}
            </button>
          ))}
          {examples.length === 0 && (
            <span className="text-xs text-muted-foreground animate-pulse">Loading examples...</span>
          )}
        </div>
      </div>
    </div>
  )
}
