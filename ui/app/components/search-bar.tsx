"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Search, Sparkles, BookOpen, ChevronRight, HelpCircle, RotateCw, Loader2 } from "lucide-react"
import type { Messages } from "@/lib/i18n"
import { toast } from "sonner"

interface SearchBarProps {
  onSearch?: (topic: string, instructions: string, academicMode: boolean, artifactOverride: string) => void
  onEnhance?: (data: any) => void
  onArtifactOverrideChange?: (artifactOverride: string) => void
  disabled?: boolean
  t: Messages
  initialTopic?: string
  initialInstructions?: string
  artifactOverride?: string
  detectedConfidence?: number | null
}

export function SearchBar({
  onSearch,
  onEnhance,
  onArtifactOverrideChange,
  disabled,
  t,
  initialTopic = "",
  initialInstructions = "",
  artifactOverride = "",
  detectedConfidence = null,
}: SearchBarProps) {
  const [topic, setTopic] = useState(initialTopic)
  const [instructions, setInstructions] = useState(initialInstructions)
  const [isFocused, setIsFocused] = useState(false)
  const [academicMode, setAcademicMode] = useState(false)
  const [examples, setExamples] = useState<{ topic: string; instructions: string }[]>([])
  const [ttl, setTtl] = useState<number>(0)
  const [refreshing, setRefreshing] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [isEnhancing, setIsEnhancing] = useState(false)
  const isLowConfidenceDetection = typeof detectedConfidence === "number" && detectedConfidence < 0.65 && !artifactOverride

  useEffect(() => {
    setTopic(initialTopic)
    setInstructions(initialInstructions)
  }, [initialTopic, initialInstructions])

  const handleEnhance = async () => {
    if (isEnhancing || !topic.trim()) return
    setIsEnhancing(true)
    try {
      const res = await fetch("/api/prompt/enhance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic.trim(),
          instructions: instructions.trim(),
          academic_mode: academicMode,
          artifact_override: artifactOverride || undefined,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const nextTopic = typeof data.topic === "string" && data.topic.trim() ? data.topic.trim() : topic.trim()
        const nextInstructions = (
          typeof data.instructions === "string" && data.instructions.trim()
            ? data.instructions.trim()
            : instructions.trim()
        )
        setTopic(nextTopic)
        setInstructions(nextInstructions)
        onEnhance?.({
          ...data,
          topic: nextTopic,
          instructions: nextInstructions,
          artifact_override: artifactOverride || null,
        })
        toast.success(t.search.enhanceSuccess)
      } else {
        let errMsg = t.search.enhanceError
        try {
          const err = await res.json()
          errMsg = err.detail || errMsg
        } catch {
          try {
            const text = await res.text()
            if (text) errMsg = text
          } catch {}
        }
        toast.error(errMsg)
      }
    } catch (e) {
      console.error("Error enhancing prompt:", e)
      toast.error(t.search.enhanceError)
    } finally {
      setIsEnhancing(false)
    }
  }

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = "auto"
    const nextHeight = Math.min(textarea.scrollHeight, 200)
    textarea.style.height = `${nextHeight}px`
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
    onSearch?.(topic.trim(), instructions.trim(), academicMode, artifactOverride)
  }

  const handleArtifactOverrideChange = (value: string) => {
    onArtifactOverrideChange?.(value)
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
              disabled={disabled || isEnhancing}
              placeholder={t.search.topicPlaceholder}
              className="w-full border-0 bg-transparent text-[15px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none py-1.5"
              required
            />
            {/* Enhance Button */}
            <Button
              type="button"
              onClick={handleEnhance}
              disabled={disabled || isEnhancing || !topic.trim()}
              className="h-8 px-2.5 rounded-lg bg-ape-primary-soft hover:bg-ape-primary-soft/80 text-ape-primary-text font-bold text-xs gap-1 cursor-pointer transition-all border-0 shadow-none"
            >
              {isEnhancing ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5 text-ape-primary" />
              )}
              <span>{isEnhancing ? t.search.enhancing : t.search.enhanceBtn}</span>
            </Button>
          </div>

          {/* Guidelines Textarea */}
          <div className="pt-1">
            <textarea
              ref={textareaRef}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              disabled={disabled || isEnhancing}
              placeholder={t.search.instructionsPlaceholder}
              rows={2}
              className="w-full border-0 bg-transparent text-[13px] text-foreground placeholder:text-muted-foreground/55 focus:outline-none resize-none leading-relaxed py-1 transition-[height] duration-200 ease-out overflow-y-auto max-h-[200px]"
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

          {isLowConfidenceDetection && (
            <div className="animate-in fade-in slide-in-from-top-1 duration-300 rounded-lg border border-ape-warning/40 bg-ape-warning-soft px-3 py-2 text-[11px] font-semibold text-ape-warning-text">
              Low confidence detection. Use Type to correct the artifact before generating.
            </div>
          )}

          {/* Action Footer */}
          <div className="flex items-center justify-between pt-2 border-t border-border/40 gap-4 flex-wrap">
            <div className="flex items-center gap-1.5 ape-micro">
              <Sparkles className="h-3 w-3 text-ape-primary animate-pulse" />
              <span>{t.search.footer}</span>
            </div>
            
            <div className="flex items-center gap-2 flex-wrap">
              {/* Artifact Type Selector */}
              <div
                className={`flex items-center gap-1 px-2.5 py-1 rounded-xl border text-[11px] font-bold ${
                  isLowConfidenceDetection
                    ? "ape-status-warning border-ape-warning/50 animate-pulse"
                    : "bg-muted/60 dark:bg-ape-surface-subtle border-border/50"
                }`}
              >
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider px-0.5">
                  {t.search.modeStandard === "Стандартный" ? "Тип:" : "Type:"}
                </span>
                <select
                  value={artifactOverride}
                  onChange={(e) => handleArtifactOverrideChange(e.target.value)}
                  disabled={disabled || isEnhancing}
                  className="bg-transparent text-[11px] font-bold text-foreground focus:outline-none border-0 cursor-pointer pr-1"
                  title="Override detected artifact type"
                >
                  <option value="" className="bg-card font-semibold text-foreground">
                    {t.search.modeStandard === "Стандартный" ? "Автоопределение" : "Auto-Detect"}
                  </option>
                  <option value="creative_poem" className="bg-card font-semibold text-foreground">
                    {t.search.modeStandard === "Стандартный" ? "Стихотворение" : "Poem"}
                  </option>
                  <option value="creative_story" className="bg-card font-semibold text-foreground">
                    {t.search.modeStandard === "Стандартный" ? "Рассказ / Сказка" : "Story / Fiction"}
                  </option>
                  <option value="school_essay" className="bg-card font-semibold text-foreground">
                    {t.search.modeStandard === "Стандартный" ? "Сочинение" : "School Essay"}
                  </option>
                  <option value="academic_paper" className="bg-card font-semibold text-foreground">
                    {t.search.modeStandard === "Стандартный" ? "Статья" : "Academic Paper"}
                  </option>
                  <option value="technical_readme" className="bg-card font-semibold text-foreground">
                    {t.search.modeStandard === "Стандартный" ? "README" : "README"}
                  </option>
                  <option value="plan_document" className="bg-card font-semibold text-foreground">
                    {t.search.modeStandard === "Стандартный" ? "План" : "Plan"}
                  </option>
                  <option value="report" className="bg-card font-semibold text-foreground">
                    {t.search.modeStandard === "Стандартный" ? "Отчет" : "Report"}
                  </option>
                  <option value="unknown_freeform" className="bg-card font-semibold text-foreground">
                    {t.search.modeStandard === "Стандартный" ? "Свободный" : "Freeform Fallback"}
                  </option>
                </select>
              </div>

              {/* Mode Switcher */}
              <div className="flex items-center gap-1 bg-muted/60 dark:bg-ape-surface-subtle p-1 rounded-xl border border-border/50 text-[11px] font-bold">
                <button
                  type="button"
                  onClick={() => setAcademicMode(false)}
                  disabled={disabled || isEnhancing}
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
                  disabled={disabled || isEnhancing}
                  className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer border-0 flex items-center gap-1 ${
                    academicMode
                      ? "ape-status-warning border"
                      : "text-muted-foreground hover:text-foreground bg-transparent"
                  }`}
                >
                  {t.search.modeAcademic}
                </button>
              </div>
            </div>
            
            <Button
              type="submit"
              disabled={disabled || isEnhancing || !topic.trim()}
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
              disabled={disabled || isEnhancing}
              className="px-3 py-2 rounded-lg border border-border/60 bg-card hover:bg-accent/40 text-[13px] leading-snug text-foreground font-semibold hover:border-ape-primary/30 transition-all cursor-pointer text-left disabled:opacity-50"
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
