"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { FileDown, FileText, Check, Eye, Loader2 } from "lucide-react"
import { toast } from "sonner"
import type { Messages } from "@/lib/i18n"

interface DocumentPreviewProps {
  topic: string
  context: Record<string, string>
  docxFilename?: string | null
  runtimeTemplate?: any
  t: Messages
  author?: string | null
}

export function DocumentPreview({ topic, context, docxFilename, runtimeTemplate, t, author }: DocumentPreviewProps) {
  const runtimeSections = Array.isArray(runtimeTemplate?.sections)
    ? runtimeTemplate.sections
        .filter((section: any) => section?.name)
        .map((section: any) => ({
          id: section.name,
          title: section.title || section.topic || humanizeSectionName(section.name),
        }))
    : []

  const exportableContext = Object.fromEntries(
    Object.entries(context).filter(([key]) => key !== "document_plan")
  )

  const contextSections = Object.keys(exportableContext).map((key) => ({
    id: key,
    title: humanizeSectionName(key),
  }))

  const baseSections = runtimeSections.length > 0 ? runtimeSections : contextSections
  const extraSections = contextSections.filter(
    (section) => !baseSections.some((known: { id: string }) => known.id === section.id)
  )
  const allSections = [...baseSections, ...extraSections]

  const [activeTab, setActiveTab] = useState<string>(allSections[0]?.id || "")
  const [copied, setCopied] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportedFilename, setExportedFilename] = useState<string | null>(docxFilename || null)
  const [exportReport, setExportReport] = useState<any>(null)

  useEffect(() => {
    setExportedFilename(docxFilename || null)
    setExportReport(null)
  }, [docxFilename, topic])

  const sections = Object.entries(exportableContext).filter(([_, text]) => !!text)

  // Ensure an active tab is selected if the tabs list changed
  if (allSections.length > 0 && (!activeTab || !context[activeTab])) {
    const firstWithContent = allSections.find((s) => !!context[s.id])
    if (firstWithContent) {
      setActiveTab(firstWithContent.id)
    }
  }

  const handleDownload = () => {
    if (!exportedFilename) return
    window.open(`/api/download/${exportedFilename}`, "_blank")
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await fetch("/api/export/docx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          context: exportableContext,
          runtime_template: runtimeTemplate,
          author: author?.trim() || undefined,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Export failed")
      }
      setExportedFilename(data.filename)
      setExportReport(data)

      // Auto-trigger browser download
      const downloadUrl = `/api/download/${data.filename}`
      const link = document.createElement("a")
      link.href = downloadUrl
      link.setAttribute("download", data.filename)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      if (data.status === "passed") {
        toast.success("DOCX export passed quality checks")
      } else {
        toast.warning("DOCX exported with QA issues")
      }
    } catch (e: any) {
      toast.error(e.message || "Failed to export DOCX")
    } finally {
      setExporting(false)
    }
  }

  // Calculate stats
  const totalChars = sections.reduce((acc, [_, text]) => acc + text.length, 0)
  const totalWords = sections.reduce((acc, [_, text]) => acc + text.split(/\s+/).filter(Boolean).length, 0)

  const formatMath = (text: string) => text
    .replace(/\\text\{([^}]+)\}/g, "$1")
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "($1)/($2)")
    .replace(/\\sum/g, "∑")
    .replace(/\\tau/g, "τ")
    .replace(/\\epsilon/g, "ε")
    .replace(/\\_/g, "_")
    .replace(/[{}]/g, "")

  // Custom basic markdown formatter
  const renderMarkdown = (text: string) => {
    if (!text) return <p className="italic text-muted-foreground">{t.document.empty}</p>

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
          <div key={`code-${key}`} className="my-3 overflow-hidden rounded-lg border border-border/80 bg-slate-950 shadow-sm">
            {codeLanguage && (
              <div className="border-b border-white/10 px-4 py-1.5 font-mono text-[10px] uppercase tracking-wider text-slate-400">
                {codeLanguage}
              </div>
            )}
            <pre className="overflow-x-auto p-4 text-left font-mono text-xs leading-6 text-slate-100 whitespace-pre">
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
          <div key={`table-${key}`} className="overflow-x-auto my-2 border border-border/80 rounded-md">
            <table className="min-w-full border-collapse border border-border/80 text-xs">
              <tbody>
                {rows.map((row, ridx) => (
                  <tr key={ridx} className={ridx === 0 ? "bg-accent/40 font-semibold" : "bg-accent/10"}>
                    {row.map((cell, cidx) => (
                      <td key={cidx} className="border border-border/85 px-3 py-2 font-mono">{parseInlineStyles(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      } else if (currentBlockType === "list") {
        elements.push(
          <ul key={`list-${key}`} className="list-disc list-inside pl-4 my-1 space-y-1">
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
          <p key={`p-${key}`} className="indent-6 text-justify mb-4 leading-relaxed">{parseInlineStyles(joinedText)}</p>
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
              className="max-w-full h-auto rounded-lg border border-border/80 shadow-sm object-contain max-h-[450px]"
            />
            {altText && (
              <span className="text-xs text-muted-foreground italic font-sans">
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
          <h3 key={`h3-${idx}`} className="text-base md:text-lg font-semibold font-sans tracking-normal pt-2 text-foreground">
            {stripped.slice(4)}
          </h3>
        )
        return
      }
      if (stripped.startsWith("## ")) {
        flushBlock(idx)
        elements.push(
          <h2 key={`h2-${idx}`} className="text-lg md:text-xl font-bold font-sans tracking-tight pt-3 text-foreground">
            {stripped.slice(3)}
          </h2>
        )
        return
      }
      if (stripped.startsWith("# ")) {
        flushBlock(idx)
        elements.push(
          <h1 key={`h1-${idx}`} className="text-xl md:text-2xl font-bold font-sans tracking-tight border-b pb-2 pt-4 text-foreground">
            {stripped.slice(2)}
          </h1>
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
    return (
      <div className="space-y-4 font-serif text-[15px] leading-relaxed text-foreground antialiased select-text">
        {elements}
      </div>
    )
  }

  // Parse bold, italic, and math ($...$, $$...$$) inline
  const parseInlineStyles = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|\$.*?\$)/g)

    return parts.map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={index} className="font-bold">{part.slice(2, -2)}</strong>
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={index} className="italic">{part.slice(1, -1)}</em>
      }
      if (part.startsWith("$$") && part.endsWith("$$")) {
        return (
          <span key={index} className="block my-3 py-2 px-4 rounded bg-accent/20 font-mono text-center text-xs border border-border/40 select-all">
            {formatMath(part.slice(2, -2))}
          </span>
        )
      }
      if (part.startsWith("\\[") && part.endsWith("\\]")) {
        return (
          <span key={index} className="block my-3 py-2 px-4 rounded bg-accent/20 font-mono text-center text-xs border border-border/40 select-all">
            {formatMath(part.slice(2, -2))}
          </span>
        )
      }
      if (part.startsWith("\\(") && part.endsWith("\\)")) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-accent/30 font-mono text-xs text-sky-700 dark:text-sky-300 select-all">
            {formatMath(part.slice(2, -2))}
          </code>
        )
      }
      if (part.startsWith("$") && part.endsWith("$")) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-accent/30 font-mono text-xs text-teal-600 dark:text-teal-400 select-all">
            {formatMath(part.slice(1, -1))}
          </code>
        )
      }
      return part
    })
  }

  const copyToClipboard = () => {
    const fullText = allSections
      .filter((s) => !!context[s.id])
      .map((s) => `## ${s.title.toUpperCase()}\n\n${context[s.id]}`)
      .join("\n\n")
    navigator.clipboard.writeText(fullText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="w-full grid grid-cols-1 lg:grid-cols-4 gap-6 animate-in fade-in duration-500">
      
      {/* Sidebar Navigation */}
      <div className="lg:col-span-1 space-y-4">
        <Card className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <CardHeader className="p-1 pb-3">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{t.document.chapters}</CardTitle>
          </CardHeader>
          <CardContent className="p-0 flex flex-row lg:flex-col gap-1.5 overflow-x-auto lg:overflow-visible">
            {allSections.filter((s) => !!context[s.id]).map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveTab(section.id)}
                className={`w-full text-left px-3 py-2 text-xs font-bold rounded-lg border transition-all shrink-0 capitalize ${
                  activeTab === section.id
                    ? "border-teal-500 bg-teal-500/5 text-teal-600 dark:text-teal-400 font-semibold"
                    : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                {section.title}
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Paper Stats */}
        <Card className="rounded-2xl border border-border bg-card p-4 shadow-sm hidden lg:block">
          <CardHeader className="p-1 pb-3">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{t.document.stats}</CardTitle>
          </CardHeader>
          <CardContent className="p-0 space-y-2.5 text-xs">
            <div className="flex justify-between border-b pb-1.5 border-border/40">
              <span className="text-muted-foreground">{t.document.words}:</span>
              <span className="font-semibold">{totalWords}</span>
            </div>
            <div className="flex justify-between border-b pb-1.5 border-border/40">
              <span className="text-muted-foreground">{t.document.chars}:</span>
              <span className="font-semibold">{totalChars}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t.document.format}:</span>
              <span className="font-semibold flex items-center gap-1 text-teal-600 dark:text-teal-400">
                <FileText className="h-3 w-3" />
                Microsoft Word
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Preview Workspace */}
      <div className="lg:col-span-3 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl border border-border bg-card shadow-sm">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-teal-500/10 flex items-center justify-center text-teal-600 dark:text-teal-400">
              <Eye className="h-4.5 w-4.5" />
            </div>
            <div>
              <h2 className="text-xs font-bold text-muted-foreground uppercase">{t.document.ready}</h2>
              <p className="text-sm font-semibold truncate max-w-xs sm:max-w-md text-foreground">
                {exportedFilename || t.document.readyForExport}
              </p>
              {exportReport?.issues?.length > 0 && (
                <p className="text-[11px] text-amber-600 dark:text-amber-400">
                  QA: {exportReport.issues.length} issue(s), see export logs.
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <Button variant="outline" size="sm" onClick={copyToClipboard} className="text-xs h-9">
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 mr-1 text-emerald-500" />
                  {t.document.copied}
                </>
              ) : (
                t.document.copy
              )}
            </Button>
            
            {exportedFilename ? (
              <Button size="sm" onClick={handleDownload} className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9 gap-1.5 shadow-sm">
                <FileDown className="h-3.5 w-3.5" />
                {t.document.downloadDocx}
              </Button>
            ) : (
              <Button size="sm" onClick={handleExport} disabled={exporting} className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9 gap-1.5 shadow-sm">
                {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
                {t.document.exportDocx}
              </Button>
            )}
          </div>
        </div>

        {/* Paper Text Display */}
        <div className="rounded-2xl border border-border bg-card p-6 md:p-8 min-h-[300px] shadow-sm relative">
          <div className="absolute top-4 right-4 bg-muted/40 text-[9px] uppercase tracking-wider font-mono text-muted-foreground px-2 py-1 rounded">
            {t.document.preview}
          </div>
          {activeTab && context[activeTab] ? (
            renderMarkdown(context[activeTab])
          ) : (
            <div className="flex h-48 w-full items-center justify-center text-muted-foreground text-sm italic">
              {t.document.empty}
            </div>
          )}
        </div>
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
