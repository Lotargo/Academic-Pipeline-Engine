"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Search, Sparkles, BookOpen, ChevronRight, HelpCircle } from "lucide-react"
import type { Messages } from "@/lib/i18n"

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
        className={`animate-in fade-in slide-in-from-bottom-4 duration-500 rounded-2xl border-2 bg-card p-4 shadow-sm transition-all hover:shadow-md ${
          isFocused ? "border-teal-500/50 ring-1 ring-teal-500/20" : "border-teal-500/20 hover:border-teal-500/30"
        }`}
      >
        <div className="space-y-3">
          {/* Primary Topic Input */}
          <div className="flex items-center gap-2 border-b border-border/60 pb-2">
            <BookOpen className="h-5 w-5 text-teal-600/70 dark:text-teal-400/70 shrink-0" />
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              disabled={disabled}
              placeholder={t.search.topicPlaceholder}
              className="w-full border-0 bg-transparent text-[14px] md:text-[15px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none py-1.5"
              required
            />
          </div>

          {/* Guidelines Textarea */}
          <div className="pt-1">
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              disabled={disabled}
              placeholder={t.search.instructionsPlaceholder}
              rows={2}
              className="w-full border-0 bg-transparent text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none resize-none leading-relaxed py-1"
            />
          </div>

          {/* Sandbox Status Banner */}
          {academicMode && (
            <div className="animate-in fade-in slide-in-from-top-1 duration-300 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/5 border border-amber-500/10 text-[9px] font-sans font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider select-none">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-500" />
              </span>
              <span>{t.search.sandboxEnabled}</span>
            </div>
          )}

          {/* Action Footer */}
          <div className="flex items-center justify-between pt-2 border-t border-border/40 gap-4 flex-wrap">
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <Sparkles className="h-3 w-3 text-teal-500 animate-pulse" />
              <span>{t.search.footer}</span>
            </div>
            
            {/* Mode Switcher */}
            <div className="flex items-center gap-1 bg-muted/60 dark:bg-zinc-900/50 p-1 rounded-xl border border-border/50 text-[10px] font-bold">
              <button
                type="button"
                onClick={() => setAcademicMode(false)}
                className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer border-0 flex items-center gap-1 ${
                  !academicMode
                    ? "bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/15"
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
                    ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/15"
                    : "text-muted-foreground hover:text-foreground bg-transparent"
                }`}
              >
                {t.search.modeAcademic}
              </button>
            </div>
            
            <Button
              type="submit"
              disabled={disabled || !topic.trim()}
              className="h-8.5 px-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs gap-1.5 select-none transition-all active:scale-95 shadow-sm disabled:opacity-50 disabled:scale-100"
            >
              <span>{t.search.compile}</span>
              <ChevronRight className="h-4.5 w-4.5" />
            </Button>
          </div>
        </div>
      </form>

      {/* Suggested Templates */}
      <div className="animate-in fade-in slide-in-from-bottom-5 duration-600 space-y-2">
        <h3 className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
          <HelpCircle className="h-3 w-3" />
          {t.search.templates}
        </h3>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => loadSuggestion("Finite State Machines", "Structure it with detailed H2/H3 headers. Discuss state transit guards.")}
            className="px-3 py-1.5 rounded-lg border border-border/60 bg-card hover:bg-accent/40 text-xs text-foreground font-semibold hover:border-teal-500/30 transition-all cursor-pointer"
          >
            {t.search.fsm}
          </button>
          <button
            onClick={() => loadSuggestion("Algorithmic Complexity Metrics", "Include LaTeX inline math e.g. $O(n \\log n)$ and display equations.")}
            className="px-3 py-1.5 rounded-lg border border-border/60 bg-card hover:bg-accent/40 text-xs text-foreground font-semibold hover:border-teal-500/30 transition-all cursor-pointer"
          >
            {t.search.complexity}
          </button>
          <button
            onClick={() => loadSuggestion("AI Agent Design Principles", "Discuss multi-agent cooperation, writer agents, and quality gates.")}
            className="px-3 py-1.5 rounded-lg border border-border/60 bg-card hover:bg-accent/40 text-xs text-foreground font-semibold hover:border-teal-500/30 transition-all cursor-pointer"
          >
            {t.search.agents}
          </button>
        </div>
      </div>
    </div>
  )
}
