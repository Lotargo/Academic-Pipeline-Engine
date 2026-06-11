"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Search, Sparkles, BookOpen, ChevronRight, HelpCircle } from "lucide-react"
import type { Messages } from "@/lib/i18n"

interface SearchBarProps {
  onSearch?: (topic: string, instructions: string) => void
  disabled?: boolean
  t: Messages
}

export function SearchBar({ onSearch, disabled, t }: SearchBarProps) {
  const [topic, setTopic] = useState("")
  const [instructions, setInstructions] = useState("")
  const [isFocused, setIsFocused] = useState(false)

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!topic.trim()) return
    onSearch?.(topic.trim(), instructions.trim())
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

          {/* Action Footer */}
          <div className="flex items-center justify-between pt-2 border-t border-border/40">
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <Sparkles className="h-3 w-3 text-teal-500 animate-pulse" />
              <span>{t.search.footer}</span>
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
