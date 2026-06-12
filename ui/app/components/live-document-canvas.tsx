import { useState } from "react"
import { FileText, Loader2, CheckCircle2, PenTool, Check, Copy, Eye, PanelTop, Moon, ChevronDown, ChevronUp } from "lucide-react"
import { toast } from "sonner"
import type { Messages } from "@/lib/i18n"
import { useTheme } from "next-themes"
import dynamic from "next/dynamic"

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false })
const MonacoDiffEditor = dynamic(() => import("@monaco-editor/react").then((mod) => mod.DiffEditor), { ssr: false })

interface LiveDocumentCanvasProps {
  status: any
  onStatusUpdate?: (status: any) => void
  t: Messages
}

type CanvasSection = {
  id: string
  title: string
}

export function LiveDocumentCanvas({ status, onStatusUpdate, t }: LiveDocumentCanvasProps) {
  const { theme } = useTheme()
  const editorTheme = theme === "dark" ? "vs-dark" : "light"
  
  const [copied, setCopied] = useState(false)
  const [draftViewMode, setDraftViewMode] = useState<"live" | "banner">("live")
  const [dimDrafting, setDimDrafting] = useState(false)
  const [sectionViewModes, setSectionViewModes] = useState<Record<string, "preview" | "editor" | "diff">>({})
  const [editedContent, setEditedContent] = useState<Record<string, string>>({})
  const [showPlan, setShowPlan] = useState(true)

  const context = status?.context || {}
  const activeState = status?.state || "INIT"
  const isRunning = status?.status === "RUNNING"
  const isCompleted = status?.status === "COMPLETED" || activeState === "DONE"

  const handleSaveSection = async (sectionId: string) => {
    const newText = editedContent[sectionId]
    if (newText === undefined) return
    
    const updatedContext = { ...context, [sectionId]: newText }
    
    if (onStatusUpdate && status) {
      onStatusUpdate({
        ...status,
        context: updatedContext
      })
    }
    
    try {
      const res = await fetch("/api/context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updatedContext)
      })
      if (res.ok) {
        toast.success("Section updated successfully")
        setEditedContent(prev => {
          const next = { ...prev }
          delete next[sectionId]
          return next
        })
      } else {
        throw new Error("Failed to save to server")
      }
    } catch (e: any) {
      toast.error(e.message || "Failed to save changes")
    }
  }

  const copyToClipboard = () => {
    const fullText = allSections
      .filter((s) => !!context[s.id])
      .map((s) => `## ${s.title}\n\n${context[s.id]}`)
      .join("\n\n")
    navigator.clipboard.writeText(fullText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const runtimeSections: CanvasSection[] = Array.isArray(status?.runtime_template?.sections)
    ? status.runtime_template.sections
        .filter((section: any) => section?.name)
        .map((section: any) => ({
          id: section.name,
          title: section.title || section.topic || humanizeSectionName(section.name),
        }))
    : []

  const contextSections: CanvasSection[] = Object.keys(context)
    .filter((key) => key !== "document_plan")
    .map((key) => ({
      id: key,
      title: humanizeSectionName(key),
    }))

  const baseSections = runtimeSections.length > 0 ? runtimeSections : contextSections
  const extraSections = contextSections.filter(
    (section) => !baseSections.some((known) => known.id === section.id)
  )
  const allSections = [...baseSections, ...extraSections]

  // Determine active section index during drafting
  let activeSectionId = ""
  if (activeState === "DRAFTING") {
    if (status?.active_section) {
      activeSectionId = status.active_section
    } else {
      // Active is the first section that hasn't been drafted yet
      const nextToDraft = allSections.find((s) => !context[s.id])
      if (nextToDraft) {
        activeSectionId = nextToDraft.id
      }
    }
  }

  const formatMath = (text: string) => text
    .replace(/\\text\{([^}]+)\}/g, "$1")
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "($1)/($2)")
    .replace(/\\sum/g, "∑")
    .replace(/\\tau/g, "τ")
    .replace(/\\epsilon/g, "ε")
    .replace(/\\alpha/g, "α")
    .replace(/\\beta/g, "β")
    .replace(/\\lambda/g, "λ")
    .replace(/\\_/g, "_")
    .replace(/[{}]/g, "")

  // Inline styling parser (supports bold, italic, and LaTeX blocks)
  const parseInlineStyles = (text: string) => {
    if (!text) return null
    const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|\$.*?\$)/g)

    return parts.map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={index} className="font-bold text-zinc-900 dark:text-zinc-50">{part.slice(2, -2)}</strong>
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={index} className="italic text-zinc-800 dark:text-zinc-200">{part.slice(1, -1)}</em>
      }
      if (part.startsWith("$$") && part.endsWith("$$")) {
        return (
          <span key={index} className="block my-3 py-3 px-4 rounded-md bg-sky-50/70 dark:bg-sky-950/20 font-mono text-center text-sm border border-sky-200/70 dark:border-sky-800/50 select-all text-sky-800 dark:text-sky-200">
            {formatMath(part.slice(2, -2))}
          </span>
        )
      }
      if (part.startsWith("\\[") && part.endsWith("\\]")) {
        return (
          <span key={index} className="block my-3 py-3 px-4 rounded-md bg-sky-50/70 dark:bg-sky-950/20 font-mono text-center text-sm border border-sky-200/70 dark:border-sky-800/50 select-all text-sky-800 dark:text-sky-200">
            {formatMath(part.slice(2, -2))}
          </span>
        )
      }
      if (part.startsWith("\\(") && part.endsWith("\\)")) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-sky-50 dark:bg-sky-950/30 font-mono text-sm text-sky-800 dark:text-sky-200 select-all">
            {formatMath(part.slice(2, -2))}
          </code>
        )
      }
      if (part.startsWith("$") && part.endsWith("$")) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-sky-50 dark:bg-sky-950/30 font-mono text-sm text-sky-800 dark:text-sky-200 select-all">
            {formatMath(part.slice(1, -1))}
          </code>
        )
      }
      return part
    })
  }

  // Render paragraphs and headers
  const renderContent = (text: string) => {
    if (!text) return null
    const lines = text.split("\n")
    const elements: React.ReactNode[] = []
    
    let currentBlockType: "paragraph" | "list" | "table" | "block_math" | "code" | null = null
    let accumulatedLines: string[] = []
    let codeLanguage = ""
    
    const flushBlock = (key: string | number) => {
      if (accumulatedLines.length === 0) return
      
      const blockText = accumulatedLines.join("\n")
      
      if (currentBlockType === "block_math") {
        let mathText = blockText.trim()
        if (mathText.startsWith("$$") && mathText.endsWith("$$")) {
          mathText = mathText.slice(2, -2)
        } else if (mathText.startsWith("\\[") && mathText.endsWith("\\]")) {
          mathText = mathText.slice(2, -2)
        } else if (mathText.startsWith("$$")) {
          mathText = mathText.slice(2)
        } else if (mathText.endsWith("$$")) {
          mathText = mathText.slice(0, -2)
        } else if (mathText.startsWith("\\[")) {
          mathText = mathText.slice(2)
        } else if (mathText.endsWith("\\]")) {
          mathText = mathText.slice(0, -2)
        }
        elements.push(
          <div key={`math-${key}`} className="my-4 rounded-md border border-sky-200/70 dark:border-sky-800/50 bg-sky-50/70 dark:bg-sky-950/20 px-4 py-4 text-center font-mono text-sm text-sky-800 dark:text-sky-100">
            {formatMath(mathText)}
          </div>
        )
      } else if (currentBlockType === "code") {
        elements.push(
          <div key={`code-${key}`} className="my-4 overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-950 shadow-sm">
            {codeLanguage && (
              <div className="border-b border-white/10 px-4 py-1.5 font-mono text-[10px] uppercase tracking-wider text-slate-400">
                {codeLanguage}
              </div>
            )}
            <pre className="overflow-x-auto p-4 text-left font-mono text-[13px] leading-6 text-slate-100 whitespace-pre">
              <code>{blockText}</code>
            </pre>
          </div>
        )
      } else if (currentBlockType === "table") {
        const rows = accumulatedLines.map(line => {
          const cells = line.split("|").map(c => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1)
          return cells
        }).filter(row => row.length > 0 && !row.every(cell => cell.includes("---")))
        
        elements.push(
          <div key={`table-${key}`} className="overflow-x-auto my-3 border border-slate-200 dark:border-slate-800 rounded-md">
            <table className="min-w-full border-collapse text-sm">
              <tbody>
                {rows.map((row, ridx) => (
                  <tr key={ridx} className={ridx === 0 ? "bg-slate-100 dark:bg-slate-900 font-semibold" : "bg-slate-50 dark:bg-slate-900/60"}>
                    {row.map((cell, cidx) => (
                      <td key={cidx} className="border border-slate-200 dark:border-slate-800 px-3 py-2 font-mono text-slate-700 dark:text-slate-300">
                        {parseInlineStyles(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      } else if (currentBlockType === "list") {
        elements.push(
          <ul key={`list-${key}`} className="list-disc pl-6 my-2 text-slate-700 dark:text-slate-300 leading-relaxed space-y-1">
            {accumulatedLines.map((line, lidx) => {
              const match = line.match(/^[-*]\s+(.+)$/)
              const body = match ? match[1] : line
              return <li key={lidx}>{parseInlineStyles(body)}</li>
            })}
          </ul>
        )
      } else if (currentBlockType === "paragraph") {
        const joinedText = accumulatedLines.join(" ")
        elements.push(
          <p key={`p-${key}`} className="indent-6 text-justify text-slate-700 dark:text-slate-300 mb-4 leading-8 text-[16px]">
            {parseInlineStyles(joinedText)}
          </p>
        )
      }
      
      accumulatedLines = []
      currentBlockType = null
      codeLanguage = ""
    }
    
    let inMathBlock = false
    let mathDelimiter: "$$" | "\\]" | null = null
    let inCodeBlock = false
    
    lines.forEach((line, idx) => {
      const stripped = line.trim()

      if (inCodeBlock) {
        if (stripped.endsWith("```")) {
          const closingIndex = line.lastIndexOf("```")
          const beforeFence = line.slice(0, closingIndex)
          if (beforeFence) {
            accumulatedLines.push(beforeFence)
          }
          inCodeBlock = false
          flushBlock(idx)
          return
        }

        accumulatedLines.push(line)
        return
      }
      
      if (!inMathBlock) {
        if (stripped.startsWith("```")) {
          flushBlock(idx)
          currentBlockType = "code"
          const afterFence = stripped.slice(3).trim()
          if (afterFence.endsWith("```")) {
            const singleLineCode = afterFence.slice(0, -3).trimEnd()
            if (singleLineCode) {
              accumulatedLines.push(singleLineCode)
            }
            flushBlock(idx)
            return
          }
          if (afterFence && /^[a-zA-Z0-9_-]+$/.test(afterFence)) {
            codeLanguage = afterFence
          } else if (afterFence) {
            accumulatedLines.push(afterFence)
          }
          inCodeBlock = true
          return
        }

        if (stripped.startsWith("$$")) {
          flushBlock(idx)
          inMathBlock = true
          mathDelimiter = "$$"
          accumulatedLines.push(line)
          currentBlockType = "block_math"
          if (stripped.length > 2 && stripped.endsWith("$$")) {
            inMathBlock = false
            flushBlock(idx)
          }
          return
        } else if (stripped.startsWith("\\[")) {
          flushBlock(idx)
          inMathBlock = true
          mathDelimiter = "\\]"
          accumulatedLines.push(line)
          currentBlockType = "block_math"
          if (stripped.length > 2 && stripped.endsWith("\\]")) {
            inMathBlock = false
            flushBlock(idx)
          }
          return
        }
      } else {
        accumulatedLines.push(line)
        if ((mathDelimiter === "$$" && stripped.endsWith("$$")) || (mathDelimiter === "\\]" && stripped.endsWith("\\]"))) {
          inMathBlock = false
          flushBlock(idx)
        }
        return
      }
      
      if (!stripped) {
        flushBlock(idx)
        return
      }
      
      // Check for standard markdown image: ![alt text](image_path)
      const imgMatch = stripped.match(/^!\[(.*?)\]\((.*?)\)$/)
      if (imgMatch) {
        flushBlock(idx)
        const altText = imgMatch[1]
        let imgUrl = imgMatch[2]
        if (imgUrl.startsWith("exports/")) {
          imgUrl = `/api/exports/${imgUrl.substring(8)}`
        } else if (imgUrl.startsWith("./exports/")) {
          imgUrl = `/api/exports/${imgUrl.substring(10)}`
        }
        elements.push(
          <div key={`img-${idx}`} className="flex flex-col items-center justify-center my-6 space-y-2">
            <img 
              src={imgUrl} 
              alt={altText} 
              className="max-w-full h-auto rounded-lg border border-slate-200 dark:border-slate-800 shadow-sm object-contain max-h-[450px]"
            />
            {altText && (
              <span className="text-xs text-slate-500 dark:text-slate-400 italic font-sans">
                Figure: {altText}
              </span>
            )}
          </div>
        )
        return
      }
      
      if (stripped.startsWith("### ")) {
        flushBlock(idx)
        elements.push(
          <h4 key={`h4-${idx}`} className="text-base font-semibold font-sans tracking-normal pt-2 mb-2 text-slate-800 dark:text-slate-100">
            {stripped.slice(4)}
          </h4>
        )
        return
      }
      if (stripped.startsWith("## ")) {
        flushBlock(idx)
        elements.push(
          <h3 key={`h3-${idx}`} className="text-lg font-bold font-sans tracking-tight pt-3 mb-2 text-slate-800 dark:text-slate-50">
            {stripped.slice(3)}
          </h3>
        )
        return
      }
      if (stripped.startsWith("# ")) {
        flushBlock(idx)
        elements.push(
          <h2 key={`h2-${idx}`} className="text-xl font-bold font-sans tracking-tight border-b border-slate-200 dark:border-slate-800 pb-2 pt-4 mb-3 text-slate-900 dark:text-slate-50">
            {stripped.slice(2)}
          </h2>
        )
        return
      }
      
      if (stripped.startsWith("|")) {
        if (currentBlockType !== "table") {
          flushBlock(idx)
          currentBlockType = "table"
        }
        accumulatedLines.push(line)
        return
      }
      
      if (stripped.startsWith("- ") || stripped.startsWith("* ")) {
        if (currentBlockType !== "list") {
          flushBlock(idx)
          currentBlockType = "list"
        }
        accumulatedLines.push(line)
        return
      }
      
      if (currentBlockType !== "paragraph") {
        flushBlock(idx)
        currentBlockType = "paragraph"
      }
      accumulatedLines.push(line)
    })
    
    flushBlock("final")
    return elements
  }

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      {/* Document Sheet Container */}
      <div className={`relative flex-1 bg-[#fbfaf7] dark:bg-[#191b20] text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-800/80 rounded-xl shadow-sm p-6 md:p-10 font-serif min-h-[650px] lg:h-full lg:max-h-none overflow-y-auto max-h-[80vh] scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-800 transition-colors duration-200 ${dimDrafting && isRunning ? "brightness-75" : ""}`}>
        
        {/* Paper Header / Running Metadata */}
        <div className="sticky top-0 z-20 -mx-6 md:-mx-10 mb-6 flex items-center justify-between border-b border-zinc-200/60 dark:border-zinc-800/60 bg-[#fbfaf7]/95 dark:bg-[#191b20]/95 px-6 md:px-10 py-4 text-[10px] font-mono tracking-widest text-zinc-400 dark:text-zinc-500 uppercase backdrop-blur supports-[backdrop-filter]:bg-[#fbfaf7]/80 dark:supports-[backdrop-filter]:bg-[#191b20]/80">
          <div className="flex items-center gap-1.5">
            <FileText className="h-3 w-3" />
            <span>{t.document.compiler}</span>
          </div>
          <div className="flex items-center gap-2">
            {isRunning && (
              <div className="flex items-center gap-1 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100/80 dark:bg-zinc-900/80 p-1 lowercase tracking-normal font-sans">
                <button
                  onClick={() => setDraftViewMode("live")}
                  className={`h-6 px-2 rounded text-[10px] font-bold flex items-center gap-1 transition-colors cursor-pointer border-0 ${
                    draftViewMode === "live"
                      ? "bg-teal-500/15 text-teal-600 dark:text-teal-300"
                      : "bg-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                  }`}
                  title="Show live generated text"
                >
                  <Eye className="h-3 w-3" />
                  Live
                </button>
                <button
                  onClick={() => setDraftViewMode("banner")}
                  className={`h-6 px-2 rounded text-[10px] font-bold flex items-center gap-1 transition-colors cursor-pointer border-0 ${
                    draftViewMode === "banner"
                      ? "bg-amber-500/15 text-amber-600 dark:text-amber-300"
                      : "bg-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                  }`}
                  title="Show drafting banner"
                >
                  <PanelTop className="h-3 w-3" />
                  Banner
                </button>
                <button
                  onClick={() => setDimDrafting((value) => !value)}
                  className={`h-6 w-6 rounded flex items-center justify-center transition-colors cursor-pointer border-0 ${
                    dimDrafting
                      ? "bg-zinc-800 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                      : "bg-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                  }`}
                  title="Toggle dimmed preview"
                >
                  <Moon className="h-3 w-3" />
                </button>
              </div>
            )}
            {isRunning && (
              <>
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-500" />
                </span>
                <span className="text-amber-600 dark:text-amber-300 font-bold">{t.document.compilingDraft} ({activeState})</span>
              </>
            )}
            {isCompleted && (
              <div className="flex items-center gap-1.5 lowercase tracking-normal font-sans">
                <button
                  onClick={copyToClipboard}
                  className="px-2 py-1 rounded bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors flex items-center gap-1 text-[10px] font-bold text-zinc-600 dark:text-zinc-400 cursor-pointer border-0"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-emerald-500" />
                      {t.document.copied}
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      {t.document.copy}
                    </>
                  )}
                </button>
                <span className="text-emerald-500 font-bold uppercase tracking-widest flex items-center gap-0.5 ml-1.5">
                  <CheckCircle2 className="h-3 w-3 animate-pulse" /> {t.document.ready}
                </span>
              </div>
            )}
            {!isRunning && !isCompleted && <span className="text-zinc-400">{t.document.idle}</span>}
          </div>
        </div>

        {/* Paper Title Block */}
        <div className="text-center space-y-3 mb-10">
          <h1 className="text-2xl md:text-3xl font-extrabold font-sans tracking-tight text-zinc-900 dark:text-zinc-50 leading-tight">
            {status?.topic || "Technical Research Paper Draft"}
          </h1>
          <div className="text-[11px] font-sans text-zinc-400 dark:text-zinc-500 tracking-wide uppercase italic">
            {t.document.subtitle}
          </div>
          <div className="w-20 h-0.5 bg-teal-500/30 mx-auto rounded-full mt-4" />
        </div>

        {/* Document Plan / Outline Card */}
        {context.document_plan && (
          <div className="mb-8 rounded-xl border border-teal-500/20 bg-teal-500/[0.02] dark:bg-teal-500/[0.01] p-5 shadow-xs transition-all duration-300">
            <div className="flex items-center justify-between border-b border-teal-500/10 pb-2 mb-3">
              <h3 className="text-xs font-sans font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-2 select-none">
                <FileText className="h-4 w-4 text-teal-500" />
                {t.document.documentPlanTitle}
              </h3>
              <button
                type="button"
                onClick={() => setShowPlan(!showPlan)}
                className="flex items-center gap-1 px-2 py-0.5 rounded bg-teal-500/10 hover:bg-teal-500/15 text-teal-700 dark:text-teal-400 text-[10px] font-bold uppercase tracking-wider select-none cursor-pointer border-0 transition-colors"
              >
                {showPlan ? (
                  <>
                    <ChevronUp className="h-3 w-3" />
                    {t.document.hidePlan}
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3" />
                    {t.document.showPlan}
                  </>
                )}
              </button>
            </div>

            {showPlan && (
              <div className="text-[13px] leading-relaxed text-zinc-700 dark:text-zinc-300 font-sans border-l-2 border-teal-500/30 pl-4 py-0.5 select-text overflow-x-auto">
                {renderContent(context.document_plan)}
              </div>
            )}
          </div>
        )}

        {/* Sections Content Output */}
        <div className="space-y-8 select-text">
          {allSections.length === 0 && (
            <div className="rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800/60 p-8 flex flex-col items-center justify-center text-center text-zinc-300 dark:text-zinc-700">
              <span className="text-xs font-sans italic">{t.document.awaiting}</span>
            </div>
          )}

          {allSections.map((section, index) => {
            const hasContent = !!context[section.id]
            const isDrafting = activeSectionId === section.id
            const showLiveDraft = isDrafting && draftViewMode === "live"
            const sectionTitle = `${index + 1}. ${section.title}`

            return (
              <div key={section.id} className="relative group transition-all duration-300">
                
                {/* Section Header */}
                <div className="flex items-center justify-between mb-3 border-b border-zinc-150/50 dark:border-zinc-800/30 pb-1.5 flex-wrap gap-2">
                  <h2 className="text-sm font-sans font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                    {sectionTitle}
                  </h2>
                  <div className="flex items-center gap-3">
                    {hasContent && !isDrafting && (
                      <div className="flex items-center gap-0.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100/80 dark:bg-zinc-900/80 p-0.5 font-sans">
                        <button
                          onClick={() => setSectionViewModes(prev => ({ ...prev, [section.id]: "preview" }))}
                          className={`h-5 px-1.5 rounded text-[9px] font-bold cursor-pointer border-0 transition-all ${
                            (sectionViewModes[section.id] || "preview") === "preview"
                              ? "bg-teal-500/15 text-teal-600 dark:text-teal-400"
                              : "bg-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                          }`}
                        >
                          Preview
                        </button>
                        <button
                          onClick={() => setSectionViewModes(prev => ({ ...prev, [section.id]: "editor" }))}
                          className={`h-5 px-1.5 rounded text-[9px] font-bold cursor-pointer border-0 transition-all ${
                            sectionViewModes[section.id] === "editor"
                              ? "bg-teal-500/15 text-teal-600 dark:text-teal-400"
                              : "bg-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                          }`}
                        >
                          Editor
                        </button>
                        <button
                          onClick={() => setSectionViewModes(prev => ({ ...prev, [section.id]: "diff" }))}
                          className={`h-5 px-1.5 rounded text-[9px] font-bold cursor-pointer border-0 transition-all ${
                            sectionViewModes[section.id] === "diff"
                              ? "bg-teal-500/15 text-teal-600 dark:text-teal-400"
                              : "bg-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                          }`}
                        >
                          Diff
                        </button>
                      </div>
                    )}

                    <div className="text-[10px] font-sans">
                      {hasContent && !isDrafting ? (
                        <span className="text-emerald-500 dark:text-emerald-400 font-bold flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" /> {t.document.compiled}
                        </span>
                      ) : isDrafting ? (
                        <span className="text-amber-500 dark:text-amber-400 font-bold flex items-center gap-1 animate-pulse">
                          <Loader2 className="h-3 w-3 animate-spin" /> {t.document.drafting}
                        </span>
                      ) : hasContent ? (
                        <span className="text-emerald-500 dark:text-emerald-400 font-bold flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" /> {t.document.compiled}
                        </span>
                      ) : (
                        <span className="text-zinc-400 dark:text-zinc-500">{t.document.pending}</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Section Content / Loading Card / Placeholder */}
                {hasContent && !isDrafting ? (
                  <div className="animate-in fade-in duration-500">
                    {(sectionViewModes[section.id] || "preview") === "preview" && (
                      renderContent(context[section.id])
                    )}
                    {sectionViewModes[section.id] === "editor" && (
                      <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden bg-white dark:bg-zinc-950 p-2 animate-in fade-in duration-300 font-sans">
                        <MonacoEditor
                          height="350px"
                          language="markdown"
                          theme={editorTheme}
                          value={editedContent[section.id] !== undefined ? editedContent[section.id] : (context[section.id] || "")}
                          onChange={(val) => {
                            setEditedContent(prev => ({ ...prev, [section.id]: val || "" }))
                          }}
                          options={{
                            minimap: { enabled: false },
                            lineNumbers: "on",
                            wordWrap: "on",
                            automaticLayout: true,
                            scrollBeyondLastLine: false,
                            fontSize: 13,
                          }}
                        />
                        {editedContent[section.id] !== undefined && editedContent[section.id] !== context[section.id] && (
                          <div className="flex justify-end pt-2 border-t border-zinc-100 dark:border-zinc-800 mt-2 px-2">
                            <button
                              onClick={() => handleSaveSection(section.id)}
                              className="px-3 py-1 rounded bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs select-none transition-all cursor-pointer border-0"
                            >
                              Save Changes
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                    {sectionViewModes[section.id] === "diff" && (
                      <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden bg-white dark:bg-zinc-950 p-2 animate-in fade-in duration-300 font-sans">
                        <MonacoDiffEditor
                          height="350px"
                          language="markdown"
                          theme={editorTheme}
                          original={status?.original_context?.[section.id] || ""}
                          modified={context[section.id] || ""}
                          options={{
                            renderSideBySide: true,
                            minimap: { enabled: false },
                            readOnly: true,
                            automaticLayout: true,
                            wordWrap: "on",
                          }}
                        />
                      </div>
                    )}
                  </div>
                ) : isDrafting ? (
                  showLiveDraft ? (
                    <div className="animate-in fade-in duration-500 space-y-3">
                      {context[section.id] ? (
                        renderContent(context[section.id])
                      ) : (
                        <div className="rounded-xl border border-dashed border-teal-300/70 dark:border-teal-900/60 bg-teal-50/30 dark:bg-teal-950/10 p-6 text-center">
                          <Loader2 className="h-4 w-4 animate-spin mx-auto mb-2 text-teal-500" />
                          <p className="text-xs font-sans text-zinc-500 dark:text-zinc-400 italic">Waiting for the first streamed tokens...</p>
                        </div>
                      )}
                      <div className="flex items-center justify-between border-t border-teal-500/10 pt-2 mt-2">
                        <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-amber-500">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          <span>Live draft view</span>
                        </div>
                        <button
                          onClick={() => setDraftViewMode("banner")}
                          className="text-[10px] font-bold text-zinc-500 hover:text-zinc-850 dark:hover:text-zinc-200 cursor-pointer bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded border-0"
                        >
                          Show Banner
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="relative rounded-xl border border-dashed border-amber-300 dark:border-amber-900/50 bg-amber-50/10 dark:bg-amber-950/5 p-6 animate-pulse flex flex-col items-center justify-center text-center space-y-3">
                      <button
                        onClick={() => setDraftViewMode("live")}
                        className="absolute top-3 right-3 text-xs font-bold text-amber-600 dark:text-amber-400 hover:underline cursor-pointer bg-transparent border-0"
                      >
                        Show Live Stream
                      </button>
                      <PenTool className="h-5 w-5 text-amber-500 animate-bounce" />
                      <div>
                        <h4 className="text-xs font-sans font-bold text-zinc-800 dark:text-zinc-200">Writer Agent Drafting</h4>
                        <p className="text-xs font-sans text-zinc-500 dark:text-zinc-400 mt-1 max-w-sm">
                          Markdown and LaTeX preview updates as sections arrive from the agent stream.
                        </p>
                      </div>
                    </div>
                  )
                ) : hasContent ? (
                  <div className="animate-in fade-in duration-500">
                    {renderContent(context[section.id])}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800/60 p-6 flex flex-col items-center justify-center text-center text-zinc-300 dark:text-zinc-700">
                    <span className="text-xs font-sans italic">{t.document.awaiting}</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Premium Official Compiled Stamp */}
        {isCompleted && (
          <div className="mt-16 border-t border-zinc-200/50 dark:border-zinc-800/50 pt-8 flex justify-end animate-in zoom-in duration-500">
            <div className="relative border-4 border-dashed border-emerald-500/80 rounded-xl px-5 py-2.5 font-sans font-black tracking-widest text-emerald-500/80 text-[10px] uppercase select-none rotate-[-4deg] flex flex-col items-center justify-center bg-emerald-500/5 shadow-[0_0_15px_rgba(16,185,129,0.05)]">
              <span className="text-[9px] font-normal tracking-wide">Academic PE Engine</span>
              <span className="text-base tracking-widest my-0.5">APPROVED</span>
              <span className="font-mono text-[8px] font-bold opacity-80">
                COMPILED: {new Date().toISOString().slice(0, 10)}
              </span>
              {/* Subtle visual grunge lines for stamp effect */}
              <div className="absolute inset-0 border border-emerald-500/20 pointer-events-none rounded-[6px] m-[1px]" />
            </div>
          </div>
        )}
        
      </div>
    </div>
  )
}

function humanizeSectionName(name: string) {
  return name
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}
