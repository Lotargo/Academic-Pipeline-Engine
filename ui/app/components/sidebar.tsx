"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Clock,
  Plus,
  Sliders,
  Play,
  FileText,
  Workflow,
  Sparkles,
  ChevronLeft,
  ChevronRight
} from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Messages } from "@/lib/i18n"

interface SidebarProps {
  activeTab: string
  setActiveTab: (tab: string) => void
  historyList: any[]
  selectedPaper: any
  setSelectedPaper: (paper: any) => void
  t: Messages
}

export function Sidebar({
  activeTab,
  setActiveTab,
  historyList,
  selectedPaper,
  setSelectedPaper,
  t
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

  const handleNewRun = () => {
    setSelectedPaper(null)
    setActiveTab("workspace")
  }

  const handleNavigate = (tab: string) => {
    setSelectedPaper(null)
    setActiveTab(tab)
  }

  const handleSelectPaper = (paper: any) => {
    setSelectedPaper(paper)
    setActiveTab("history_preview")
  }

  const historyKey = (paper: any) =>
    [paper?.filename || "draft", paper?.topic || "", paper?.timestamp || ""].join("|")

  return (
    <div
      className={`relative flex flex-col border-r border-border bg-background py-4 transition-[width] duration-200 ease-out z-50 h-screen shrink-0 select-none overflow-hidden ${
        collapsed ? "w-16" : "w-[260px]"
      }`}
    >
      {/* Collapse Toggle Button */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute top-1/2 -right-3 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground shadow-sm hover:scale-105 active:scale-95 cursor-pointer z-50"
      >
        {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
      </button>

      {/* Header Logo */}
      <div className={`flex items-center px-4 mb-5 ${collapsed ? "justify-center" : "gap-2"}`}>
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-600/10 text-teal-600 dark:text-teal-400">
          <Sparkles className="h-5 w-5 animate-pulse" />
        </div>
        {!collapsed && (
          <div className="flex flex-col">
            <span className="text-[13px] font-black tracking-tight text-foreground uppercase">Academic PE</span>
            <span className="text-[9px] font-medium text-muted-foreground uppercase leading-none">Pipeline Engine</span>
          </div>
        )}
      </div>

      {/* New Generation Button */}
      <div className="px-3 mb-4">
        <Button
          onClick={handleNewRun}
          variant="outline"
          className={`w-full justify-start gap-2 text-xs font-bold border-teal-500/20 hover:border-teal-500/40 hover:bg-teal-500/5 text-teal-600 dark:text-teal-400 h-9 rounded-lg transition-all ${
            collapsed ? "px-2 justify-center" : "px-3"
          }`}
        >
          <Plus className="h-4 w-4 shrink-0" />
          {!collapsed && <span>{t.nav.newGeneration}</span>}
        </Button>
      </div>

      {/* Main Navigation */}
      <nav className="flex flex-col gap-1 px-2 mb-4">
        <button
          onClick={() => handleNavigate("workspace")}
          className={`flex items-center gap-3 px-3 py-2 text-xs font-bold rounded-lg border transition-all cursor-pointer ${
            activeTab === "workspace" && !selectedPaper
              ? "border-teal-500 bg-teal-500/5 text-teal-600 dark:text-teal-400 font-semibold"
              : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground"
          } ${collapsed ? "justify-center px-0" : ""}`}
          title="Workspace Dashboard"
        >
          <Play className="h-4.5 w-4.5 shrink-0" />
          {!collapsed && <span>{t.nav.workspace}</span>}
        </button>

        <button
          onClick={() => handleNavigate("fsm")}
          className={`flex items-center gap-3 px-3 py-2 text-xs font-bold rounded-lg border transition-all cursor-pointer ${
            activeTab === "fsm" && !selectedPaper
              ? "border-teal-500 bg-teal-500/5 text-teal-600 dark:text-teal-400 font-semibold"
              : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground"
          } ${collapsed ? "justify-center px-0" : ""}`}
          title="FSM Flow Monitor"
        >
          <Workflow className="h-4.5 w-4.5 shrink-0" />
          {!collapsed && <span>{t.nav.pipeline}</span>}
        </button>

        <button
          onClick={() => handleNavigate("config")}
          className={`flex items-center gap-3 px-3 py-2 text-xs font-bold rounded-lg border transition-all cursor-pointer ${
            activeTab === "config" && !selectedPaper
              ? "border-teal-500 bg-teal-500/5 text-teal-600 dark:text-teal-400 font-semibold"
              : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground"
          } ${collapsed ? "justify-center px-0" : ""}`}
          title="Engine Configuration"
        >
          <Sliders className="h-4.5 w-4.5 shrink-0" />
          {!collapsed && <span>{t.nav.settings}</span>}
        </button>
      </nav>

      {/* History section divider */}
      {!collapsed && (
        <div className="px-4 py-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <Clock className="h-3 w-3" />
            {t.nav.recent}
          </span>
        </div>
      )}

      {/* Dynamic History List */}
      <ScrollArea className="flex-1 px-2">
        <div className="space-y-0.5 pb-4">
          {historyList.map((paper, index) => {
            const isSelected = selectedPaper === paper
            return (
              <button
                key={`${historyKey(paper)}|${index}`}
                onClick={() => handleSelectPaper(paper)}
                className={`group w-full text-left px-3 py-2 text-xs leading-tight rounded-lg border transition-all relative flex items-center gap-2 cursor-pointer ${
                  isSelected
                    ? "border-teal-500 bg-teal-500/5 text-teal-600 dark:text-teal-400 font-semibold"
                    : "border-transparent text-foreground hover:bg-accent"
                }`}
                title={paper.topic}
              >
                <FileText className="h-4 w-4 text-muted-foreground shrink-0 group-hover:text-teal-500" />
                {!collapsed ? (
                  <div className="flex flex-col truncate pr-2">
                    <span className="font-semibold truncate text-[11px]">{paper.topic}</span>
                    <span className="text-[9px] text-muted-foreground">{paper.timestamp}</span>
                  </div>
                ) : (
                  <div className="w-1.5 h-1.5 rounded-full bg-teal-500 absolute bottom-1 right-1" />
                )}
              </button>
            )
          })}
          
          {historyList.length === 0 && !collapsed && (
            <div className="px-3 py-4 text-center text-xs text-muted-foreground italic border border-dashed rounded-lg border-border/60 mx-1">
              {t.nav.emptyHistory}
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Footer / User Profile */}
      <div className={`mt-auto border-t border-border pt-4 px-3 flex items-center ${collapsed ? "justify-center" : "gap-3"}`}>
        <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full overflow-hidden bg-teal-600/10 ring-2 ring-teal-500/20 text-teal-600 font-bold text-xs uppercase">
          PE
        </div>
        {!collapsed && (
          <div className="flex flex-col overflow-hidden leading-tight">
            <span className="text-[11px] font-bold text-foreground">{t.nav.user}</span>
            <span className="text-[9px] text-muted-foreground truncate">pe-engine@lotargo.org</span>
          </div>
        )}
      </div>
    </div>
  )
}
