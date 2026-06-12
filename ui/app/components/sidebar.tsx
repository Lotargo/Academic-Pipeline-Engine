"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Clock,
  Plus,
  Sliders,
  Play,
  FileText,
  Workflow,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Archive,
  Trash2
} from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { ProfileModal } from "./profile-modal"
import { AcademicLogo } from "./academic-logo"
import type { Messages, UiLanguage } from "@/lib/i18n"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

interface SidebarProps {
  activeTab: string
  setActiveTab: (tab: string) => void
  historyList: any[]
  selectedPaper: any
  setSelectedPaper: (paper: any) => void
  t: Messages
  language: UiLanguage
  onLanguageChange: (language: UiLanguage) => Promise<void> | void
  theme?: string
  onThemeChange: (theme: string) => void
  nickname: string
  onNicknameChange: (nickname: string) => void
  avatarUrl: string | null
  onAvatarChange: (avatarUrl: string | null) => void
  onArchivePaper: (paper: any) => Promise<void> | void
  onDeletePaper: (paper: any) => Promise<void> | void
  onOpenArchivedWorks: () => void
}

const SIDEBAR_WIDTH_KEY = "ape.sidebar.width"
const COLLAPSED_WIDTH = 64
const DEFAULT_WIDTH = 260
const MIN_WIDTH = 220
const MAX_WIDTH = 420
const RESIZE_STEP = 16

const clampSidebarWidth = (width: number) => Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, width))

export function Sidebar({
  activeTab,
  setActiveTab,
  historyList,
  selectedPaper,
  setSelectedPaper,
  t,
  language,
  onLanguageChange,
  theme,
  onThemeChange,
  nickname,
  onNicknameChange,
  avatarUrl,
  onAvatarChange,
  onArchivePaper,
  onDeletePaper,
  onOpenArchivedWorks
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_WIDTH)
  const [isResizing, setIsResizing] = useState(false)
  const [paperPendingDelete, setPaperPendingDelete] = useState<any>(null)
  const sidebarRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const storedWidth = window.localStorage.getItem(SIDEBAR_WIDTH_KEY)
    if (!storedWidth) return

    const parsedWidth = Number(storedWidth)
    if (Number.isFinite(parsedWidth)) {
      setSidebarWidth(clampSidebarWidth(parsedWidth))
    }
  }, [])

  useEffect(() => {
    if (collapsed) return
    window.localStorage.setItem(SIDEBAR_WIDTH_KEY, String(Math.round(sidebarWidth)))
  }, [collapsed, sidebarWidth])

  useEffect(() => {
    if (!isResizing) return

    const previousCursor = document.body.style.cursor
    const previousUserSelect = document.body.style.userSelect
    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"

    const handlePointerMove = (event: PointerEvent) => {
      const sidebarLeft = sidebarRef.current?.getBoundingClientRect().left ?? 0
      setSidebarWidth(clampSidebarWidth(event.clientX - sidebarLeft))
    }

    const stopResizing = () => {
      setIsResizing(false)
    }

    window.addEventListener("pointermove", handlePointerMove)
    window.addEventListener("pointerup", stopResizing)
    window.addEventListener("pointercancel", stopResizing)

    return () => {
      document.body.style.cursor = previousCursor
      document.body.style.userSelect = previousUserSelect
      window.removeEventListener("pointermove", handlePointerMove)
      window.removeEventListener("pointerup", stopResizing)
      window.removeEventListener("pointercancel", stopResizing)
    }
  }, [isResizing])

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

  const startResizing = () => {
    setIsResizing(true)
  }

  const displayName = nickname.trim() || t.nav.user
  const initials = displayName.slice(0, 2).toUpperCase()
  const archiveLabel = language === "ru" ? "Архивировать" : "Archive"
  const deleteLabel = language === "ru" ? "Удалить" : "Delete"
  const cancelLabel = language === "ru" ? "Отмена" : "Cancel"
  const deleteTitle = language === "ru" ? "Удалить работу?" : "Delete this work?"
  const deleteDescription =
    language === "ru"
      ? "Это навсегда удалит metadata и связанный DOCX-файл, если он есть."
      : "This permanently removes the metadata record and its DOCX export when present."
  const profileCaption = language === "ru" ? "Локальный профиль" : "Local profile"

  return (
    <div
      ref={sidebarRef}
      className={`relative flex flex-col border-r border-border bg-background z-50 h-screen shrink-0 select-none overflow-hidden ${
        isResizing ? "" : "transition-[width] duration-200 ease-out"
      }`}
      style={{ width: collapsed ? COLLAPSED_WIDTH : sidebarWidth }}
    >
      {!collapsed && (
        <div
          role="separator"
          aria-label="Resize sidebar"
          aria-orientation="vertical"
          tabIndex={0}
          onPointerDown={(event) => {
            event.preventDefault()
            startResizing()
          }}
          onMouseDown={(event) => {
            event.preventDefault()
            startResizing()
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") {
              event.preventDefault()
              setSidebarWidth((width) => clampSidebarWidth(width - RESIZE_STEP))
            } else if (event.key === "ArrowRight") {
              event.preventDefault()
              setSidebarWidth((width) => clampSidebarWidth(width + RESIZE_STEP))
            } else if (event.key === "Home") {
              event.preventDefault()
              setSidebarWidth(MIN_WIDTH)
            } else if (event.key === "End") {
              event.preventDefault()
              setSidebarWidth(MAX_WIDTH)
            }
          }}
          className="absolute inset-y-0 right-0 z-40 w-2 cursor-col-resize touch-none outline-none transition-colors hover:bg-ape-primary/15 focus-visible:bg-ape-primary/20"
        >
          <span className="absolute inset-y-4 right-0 w-px bg-border" />
        </div>
      )}

      {/* Collapse Toggle Button */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="absolute top-1/2 -right-3 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground shadow-sm hover:scale-105 active:scale-95 cursor-pointer z-50"
      >
        {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
      </button>

      {/* Header Logo */}
      <div className={`px-3 pt-4 mb-5 ${collapsed ? "flex justify-center" : ""}`}>
        <AcademicLogo compact={collapsed} className={collapsed ? "h-12 w-12 shrink-0" : "h-[76px] w-full"} />
      </div>

      {/* New Generation Button */}
      <div className="px-3 mb-4">
        <Button
          onClick={handleNewRun}
          variant="outline"
          className={`w-full justify-start gap-2 ape-control-text font-bold border-ape-primary/20 hover:border-ape-primary/40 hover:bg-ape-primary-soft text-ape-primary-text h-9 rounded-lg transition-all ${
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
          className={`flex items-center gap-3 px-3 py-2 ape-control-text font-bold rounded-lg border transition-all cursor-pointer ${
            activeTab === "workspace" && !selectedPaper
              ? "ape-status-primary font-semibold"
              : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground"
          } ${collapsed ? "justify-center px-0" : ""}`}
          title="Workspace Dashboard"
        >
          <Play className="h-4.5 w-4.5 shrink-0" />
          {!collapsed && <span>{t.nav.workspace}</span>}
        </button>

        <button
          onClick={() => handleNavigate("fsm")}
          className={`flex items-center gap-3 px-3 py-2 ape-control-text font-bold rounded-lg border transition-all cursor-pointer ${
            activeTab === "fsm" && !selectedPaper
              ? "ape-status-primary font-semibold"
              : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground"
          } ${collapsed ? "justify-center px-0" : ""}`}
          title="FSM Flow Monitor"
        >
          <Workflow className="h-4.5 w-4.5 shrink-0" />
          {!collapsed && <span>{t.nav.pipeline}</span>}
        </button>

        <button
          onClick={() => handleNavigate("config")}
          className={`flex items-center gap-3 px-3 py-2 ape-control-text font-bold rounded-lg border transition-all cursor-pointer ${
            activeTab === "config" && !selectedPaper
              ? "ape-status-primary font-semibold"
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
          <span className="ape-label flex items-center gap-1.5">
            <Clock className="h-3 w-3" />
            {t.nav.recent}
          </span>
        </div>
      )}

      {/* Dynamic History List */}
      <ScrollArea className="min-h-0 flex-1 px-2">
        <div className="space-y-0.5 pb-4">
          {historyList.map((paper, index) => {
            const isSelected = selectedPaper === paper
            return (
              <div
                key={`${historyKey(paper)}|${index}`}
                className={`group w-full text-left ape-control-text rounded-lg border transition-all relative flex items-center gap-1 ${
                  isSelected
                    ? "ape-status-primary font-semibold"
                    : "border-transparent text-foreground hover:bg-accent"
                }`}
              >
                <button
                  onClick={() => handleSelectPaper(paper)}
                  className={`flex min-w-0 flex-1 items-center gap-2 bg-transparent px-3 py-2 text-left cursor-pointer border-0 ${
                    collapsed ? "justify-center px-0" : ""
                  }`}
                  title={paper.topic}
                >
                  <FileText className="h-4 w-4 text-muted-foreground shrink-0 group-hover:text-ape-primary" />
                  {!collapsed ? (
                    <div className="flex min-w-0 flex-col truncate pr-1">
                      <span className="truncate text-[12px] font-semibold leading-snug">{paper.topic}</span>
                      <span className="ape-micro">{paper.timestamp}</span>
                    </div>
                  ) : (
                    <div className="w-1.5 h-1.5 rounded-full bg-ape-primary absolute bottom-1 right-1" />
                  )}
                </button>
                {!collapsed && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        aria-label="History item actions"
                        className="mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-opacity hover:bg-background/80 hover:text-foreground group-hover:opacity-100 focus-visible:opacity-100"
                      >
                        <MoreHorizontal className="h-3.5 w-3.5" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem onSelect={() => onArchivePaper(paper)}>
                        <Archive className="h-3.5 w-3.5" />
                        {archiveLabel}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        onSelect={(event) => {
                          event.preventDefault()
                          setPaperPendingDelete(paper)
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {deleteLabel}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            )
          })}

          <AlertDialog open={Boolean(paperPendingDelete)} onOpenChange={(open) => !open && setPaperPendingDelete(null)}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{deleteTitle}</AlertDialogTitle>
                <AlertDialogDescription>
                  {deleteDescription}
                  {paperPendingDelete?.topic ? ` "${paperPendingDelete.topic}"` : ""}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{cancelLabel}</AlertDialogCancel>
                <AlertDialogAction
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  onClick={async () => {
                    const target = paperPendingDelete
                    setPaperPendingDelete(null)
                    if (target) await onDeletePaper(target)
                  }}
                >
                  {deleteLabel}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          
          {historyList.length === 0 && !collapsed && (
            <div className="px-3 py-4 text-center text-xs text-muted-foreground italic border border-dashed rounded-lg border-border/60 mx-1">
              {t.nav.emptyHistory}
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Footer / User Profile */}
      <div className="mt-auto flex h-[88px] shrink-0 items-center justify-center border-t border-border px-3">
        <ProfileModal
          language={language}
          onLanguageChange={onLanguageChange}
          theme={theme}
          onThemeChange={onThemeChange}
          nickname={nickname}
          onNicknameChange={onNicknameChange}
          avatarUrl={avatarUrl}
          onAvatarChange={onAvatarChange}
          onOpenArchivedWorks={onOpenArchivedWorks}
        >
          <button
            type="button"
            className={`flex w-full items-center rounded-lg border border-border/70 bg-card/50 shadow-sm transition-all hover:border-ape-primary/30 hover:bg-accent cursor-pointer ${
              collapsed ? "justify-center p-1.5" : "min-h-11 gap-3 px-2.5 py-2"
            }`}
            title={displayName}
          >
            <Avatar className="size-8 ring-2 ring-ape-primary/20">
              {avatarUrl && <AvatarImage src={avatarUrl} alt={displayName} />}
              <AvatarFallback className="bg-ape-primary-soft text-ape-primary-text font-bold text-xs uppercase">
                {initials}
              </AvatarFallback>
            </Avatar>
            {!collapsed && (
              <div className="flex min-w-0 flex-col overflow-hidden text-left leading-tight">
                <span className="truncate text-[12px] font-bold text-foreground">{displayName}</span>
                <span className="ape-micro truncate">{profileCaption}</span>
              </div>
            )}
          </button>
        </ProfileModal>
      </div>
    </div>
  )
}
