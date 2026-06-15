"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { FileDown, FileText, Check, Eye, Loader2, ChevronDown } from "lucide-react"
import { toast } from "sonner"
import type { Messages } from "@/lib/i18n"

interface DocumentPreviewProps {
  topic: string
  context: Record<string, string>
  docxFilename?: string | null
  runId?: string | null
  runtimeTemplate?: any
  t: Messages
  author?: string | null
  language?: string
  metadata?: any
}

export function DocumentPreview({ topic, context, docxFilename, runId, runtimeTemplate, t, author, language, metadata }: DocumentPreviewProps) {
  const hiddenSectionIds = new Set(
    Array.isArray(runtimeTemplate?.sections)
      ? runtimeTemplate.sections
          .filter((section: any) => section?.name && !isRenderableTemplateSection(section))
          .map((section: any) => section.name)
      : []
  )

  const runtimeSections = Array.isArray(runtimeTemplate?.sections)
    ? runtimeTemplate.sections
        .filter((section: any) => section?.name && isRenderableTemplateSection(section))
        .map((section: any) => ({
          id: section.name,
          title: section.title || section.topic || humanizeSectionName(section.name),
        }))
    : []

  // Resolve debug metadata from the source
  const source = metadata || {}
  const summary = source.decision_summary || source.runtime_prompt_manifest?.metadata?.decision_summary
  const selection = source.manifest_selection || source.runtime_prompt_manifest?.metadata?.manifest_selection
  const contract = source.resolved_contract || source.runtime_prompt_manifest?.metadata?.resolved_contract
  const manifest = source.resolved_manifest || source.runtime_prompt_manifest?.metadata?.resolved_manifest
  const continuationIntent = source.continuation_intent || source.runtime_prompt_manifest?.metadata?.continuation_intent
  const documentState = source.document_state || source.runtime_prompt_manifest?.metadata?.document_state
  const editPlan = source.edit_plan || source.runtime_prompt_manifest?.metadata?.edit_plan
  const mergePatch = source.merge_patch || source.runtime_prompt_manifest?.metadata?.merge_patch

  const manifestId = manifest?.id || contract?.artifact || summary?.selected_manifest || ""
  const version = manifest?.version || ""
  const confidence = typeof summary?.confidence === "number"
    ? summary.confidence
    : typeof selection?.confidence === "number"
      ? selection.confidence
      : null
  const matchedPhrases = summary?.matched_phrases || selection?.matched_phrases || []
  const forbidList = manifest?.forbid || contract?.forbid || []
  const continuationIntentLabel = continuationIntent?.intent || ""
  const terminalSections = Array.isArray(documentState?.terminal_sections) ? documentState.terminal_sections : []
  const editOperations = Array.isArray(editPlan?.operations) ? editPlan.operations : []
  const continuityDossier = documentState?.continuity_dossier || null
  const styleProfile = documentState?.style_profile || null
  const referenceRegistry = Array.isArray(documentState?.reference_registry) ? documentState.reference_registry : []
  const redFlags = Array.isArray(editPlan?.red_flags) ? editPlan.red_flags : []
  const operationSummary = Array.isArray(mergePatch?.operation_summary) ? mergePatch.operation_summary : []
  const changedSections = {
    inserted: Object.keys(mergePatch?.inserted_content || {}),
    replaced: Object.keys(mergePatch?.replaced_ranges || {}),
    references: Array.isArray(mergePatch?.updated_references) ? mergePatch.updated_references : [],
  }
  const hasChangeSummary = changedSections.inserted.length > 0 || changedSections.replaced.length > 0 || changedSections.references.length > 0
  const hasEditorialInfo = !!continuationIntentLabel || !!continuityDossier || redFlags.length > 0 || operationSummary.length > 0 || hasChangeSummary
  const hasDebugInfo = !!manifestId || !!version || confidence !== null || matchedPhrases.length > 0 || forbidList.length > 0 || !!continuationIntentLabel || terminalSections.length > 0 || editOperations.length > 0 || operationSummary.length > 0

  const exportableContext = Object.fromEntries(
    Object.entries(context).filter(([key]) => key !== "document_plan" && !hiddenSectionIds.has(key))
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
  const hasAnyContent = allSections.some((s) => !!context[s.id])

  const [activeTab, setActiveTab] = useState<string>("__full__")
  const [copied, setCopied] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportingPdf, setExportingPdf] = useState(false)
  const [exportedFilename, setExportedFilename] = useState<string | null>(docxFilename || null)
  const [exportedPdfFilename, setExportedPdfFilename] = useState<string | null>(null)
  const [exportReport, setExportReport] = useState<any>(null)
  const [editorialOpen, setEditorialOpen] = useState(true)

  useEffect(() => {
    setExportedFilename(docxFilename || null)
    setExportedPdfFilename(null)
    setExportReport(null)
  }, [docxFilename, topic])

  const sections = Object.entries(exportableContext).filter(([_, text]) => !!text)

  // Ensure an active tab is selected if the tabs list changed
  if (hasAnyContent && (!activeTab || (activeTab !== "__full__" && !context[activeTab]))) {
    setActiveTab("__full__")
  }

  const handleDownload = () => {
    if (!exportedFilename) return
    window.open(`/api/download/${exportedFilename}`, "_blank")
  }

  const handleDownloadPdf = () => {
    if (!exportedPdfFilename) return
    window.open(`/api/download/${exportedPdfFilename}`, "_blank")
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
          run_id: runId || undefined,
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

  const handleExportPdf = async () => {
    setExportingPdf(true)
    try {
      const res = await fetch("/api/export/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          context: exportableContext,
          runtime_template: runtimeTemplate,
          author: author?.trim() || undefined,
          run_id: runId || undefined,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "PDF export failed")
      }
      setExportedPdfFilename(data.filename)

      const downloadUrl = `/api/download/${data.filename}`
      const link = document.createElement("a")
      link.href = downloadUrl
      link.setAttribute("download", data.filename)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      toast.success("PDF export completed")
    } catch (e: any) {
      toast.error(e.message || "Failed to export PDF")
    } finally {
      setExportingPdf(false)
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
          <div key={`math-${key}`} className="my-4 rounded-md border border-ape-primary/25 bg-ape-primary-soft/45 px-4 py-4 text-center font-mono text-sm text-ape-primary-text">
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
          <p key={`p-${key}`} className="ape-document-font indent-6 text-justify mb-4 leading-relaxed">{parseInlineStyles(joinedText)}</p>
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
          <h3 key={`h3-${idx}`} className="ape-document-font text-base md:text-lg font-semibold tracking-normal pt-2 text-foreground">
            {stripped.slice(4)}
          </h3>
        )
        return
      }
      if (stripped.startsWith("## ")) {
        flushBlock(idx)
        elements.push(
          <h2 key={`h2-${idx}`} className="ape-document-font text-lg md:text-xl font-bold tracking-normal pt-3 text-foreground">
            {stripped.slice(3)}
          </h2>
        )
        return
      }
      if (stripped.startsWith("# ")) {
        flushBlock(idx)
        elements.push(
          <h1 key={`h1-${idx}`} className="ape-document-font text-xl md:text-2xl font-bold tracking-normal border-b pb-2 pt-4 text-foreground">
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
      <div className="ape-document-font space-y-4 text-[15px] leading-relaxed text-foreground antialiased select-text">
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
          <code key={index} className="px-1.5 py-0.5 rounded bg-accent/30 font-mono text-xs text-ape-primary-text select-all">
            {formatMath(part.slice(2, -2))}
          </code>
        )
      }
      if (part.startsWith("$") && part.endsWith("$")) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-accent/30 font-mono text-xs text-ape-primary-text select-all">
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
            {hasAnyContent && (
              <button
                onClick={() => setActiveTab("__full__")}
                className={`w-full text-left px-3 py-2 text-xs font-bold rounded-lg border transition-all shrink-0 capitalize ${
                  activeTab === "__full__"
                    ? "border-ape-primary bg-ape-primary-soft text-ape-primary-text font-semibold"
                    : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                {t.document.fullDocument}
              </button>
            )}
            {allSections.filter((s) => !!context[s.id]).map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveTab(section.id)}
                className={`w-full text-left px-3 py-2 text-xs font-bold rounded-lg border transition-all shrink-0 capitalize ${
                  activeTab === section.id
                    ? "border-ape-primary bg-ape-primary-soft text-ape-primary-text font-semibold"
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
              <span className="font-semibold flex items-center gap-1 text-ape-primary-text">
                <FileText className="h-3 w-3" />
                Microsoft Word
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Editorial Continuity */}
        {hasEditorialInfo && (
          <Card className="rounded-2xl border border-border bg-card p-4 shadow-sm hidden lg:block mt-4">
            <Collapsible open={editorialOpen} onOpenChange={setEditorialOpen}>
              <CardHeader className="p-1 pb-3">
                <CollapsibleTrigger className="flex w-full items-center justify-between gap-2 text-left">
                  <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Editorial Continuity
                  </CardTitle>
                  <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${editorialOpen ? "rotate-180" : ""}`} />
                </CollapsibleTrigger>
              </CardHeader>
              <CollapsibleContent>
                <CardContent className="p-0 space-y-3 text-xs">
                  {continuationIntentLabel && (
                    <div className="flex justify-between border-b pb-1.5 border-border/40">
                      <span className="text-muted-foreground">Intent:</span>
                      <span className="font-mono font-semibold">{continuationIntentLabel}</span>
                    </div>
                  )}
                  {continuityDossier?.current_stopping_point && (
                    <div className="border-b pb-1.5 border-border/40 space-y-1">
                      <span className="text-muted-foreground">Stopping point:</span>
                      <p className="line-clamp-4 text-[11px] leading-relaxed text-foreground/80">
                        {continuityDossier.current_stopping_point}
                      </p>
                    </div>
                  )}
                  {(continuityDossier?.style_summary || styleProfile?.heading_style || styleProfile?.citation_style) && (
                    <div className="border-b pb-1.5 border-border/40 space-y-1">
                      <span className="text-muted-foreground">Style profile:</span>
                      <p className="text-[11px] leading-relaxed text-foreground/80">
                        {continuityDossier?.style_summary || `heading=${styleProfile?.heading_style || "unknown"}; citation=${styleProfile?.citation_style || "none"}`}
                      </p>
                    </div>
                  )}
                  {(continuityDossier?.reference_summary || referenceRegistry.length > 0) && (
                    <div className="border-b pb-1.5 border-border/40 space-y-1">
                      <span className="text-muted-foreground">References:</span>
                      <p className="text-[11px] leading-relaxed text-foreground/80">
                        {continuityDossier?.reference_summary || `${referenceRegistry.length} reference(s)`}
                      </p>
                    </div>
                  )}
                  {redFlags.length > 0 && (
                    <div className="border-b pb-1.5 border-border/40 space-y-1">
                      <span className="text-muted-foreground">Red flags:</span>
                      <ul className="space-y-1">
                        {redFlags.slice(0, 4).map((flag: string, idx: number) => (
                          <li key={idx} className="rounded bg-amber-500/10 px-2 py-1 text-[11px] leading-snug text-amber-700 dark:text-amber-300">
                            {flag}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {operationSummary.length > 0 && (
                    <div className="border-b pb-1.5 border-border/40 space-y-1">
                      <span className="text-muted-foreground">Operation summary:</span>
                      <div className="space-y-1">
                        {operationSummary.slice(0, 6).map((operation: any, idx: number) => (
                          <div key={idx} className="rounded bg-muted px-2 py-1">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-[10px] text-muted-foreground">{operation?.op || "op"}</span>
                              {operation?.target && (
                                <span className="truncate font-mono text-[10px] text-muted-foreground">{operation.target}</span>
                              )}
                            </div>
                            {operation?.result && (
                              <p className="mt-0.5 text-[11px] leading-snug text-foreground/80">{operation.result}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {hasChangeSummary && (
                    <div className="space-y-1">
                      <span className="text-muted-foreground">View changes:</span>
                      <div className="flex flex-wrap gap-1">
                        {changedSections.replaced.map((section: string) => (
                          <span key={`replaced-${section}`} className="rounded bg-orange-500/10 px-1.5 py-0.5 text-[10px] font-mono text-orange-700 dark:text-orange-300">
                            replaced:{section}
                          </span>
                        ))}
                        {changedSections.inserted.map((section: string) => (
                          <span key={`inserted-${section}`} className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-mono text-emerald-700 dark:text-emerald-300">
                            inserted:{section}
                          </span>
                        ))}
                        {changedSections.references.map((section: string) => (
                          <span key={`refs-${section}`} className="rounded bg-sky-500/10 px-1.5 py-0.5 text-[10px] font-mono text-sky-700 dark:text-sky-300">
                            refs:{section}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        )}

        {/* Debug Metadata */}
        {hasDebugInfo && (
          <Card className="rounded-2xl border border-border bg-card p-4 shadow-sm hidden lg:block mt-4">
            <CardHeader className="p-1 pb-3">
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                {language === "ru" ? "Отладочные метаданные" : "Debug Metadata"}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 space-y-2.5 text-xs">
              {manifestId && (
                <div className="flex justify-between border-b pb-1.5 border-border/40">
                  <span className="text-muted-foreground">Manifest ID:</span>
                  <span className="font-mono font-semibold">{manifestId}</span>
                </div>
              )}
              {version && (
                <div className="flex justify-between border-b pb-1.5 border-border/40">
                  <span className="text-muted-foreground">Version:</span>
                  <span className="font-mono font-semibold">{version}</span>
                </div>
              )}
              {confidence !== null && (
                <div className="flex justify-between border-b pb-1.5 border-border/40">
                  <span className="text-muted-foreground">Confidence:</span>
                  <span className={`font-semibold ${confidence < 0.65 ? "text-amber-500 animate-pulse" : ""}`}>
                    {Math.round(confidence * 100)}%
                  </span>
                </div>
              )}
              {continuationIntentLabel && (
                <div className="flex justify-between border-b pb-1.5 border-border/40">
                  <span className="text-muted-foreground">Intent:</span>
                  <span className="font-mono font-semibold">{continuationIntentLabel}</span>
                </div>
              )}
              {terminalSections.length > 0 && (
                <div className="border-b pb-1.5 border-border/40 space-y-1">
                  <span className="text-muted-foreground">Terminal Sections:</span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {terminalSections.map((section: string, idx: number) => (
                      <span key={idx} className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                        {section}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {editOperations.length > 0 && (
                <div className="border-b pb-1.5 border-border/40 space-y-1">
                  <span className="text-muted-foreground">Edit Ops:</span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {editOperations.map((operation: any, idx: number) => (
                      <span key={idx} className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                        {operation?.op || "op"}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {matchedPhrases.length > 0 && (
                <div className="border-b pb-1.5 border-border/40 space-y-1">
                  <span className="text-muted-foreground">Matched Cues:</span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {matchedPhrases.map((phrase: string, idx: number) => (
                      <span key={idx} className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                        {phrase}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {forbidList.length > 0 && (
                <div className="space-y-1">
                  <span className="text-muted-foreground">Negative Constraints:</span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {forbidList.map((constraint: string, idx: number) => (
                      <span key={idx} className="rounded bg-destructive/10 px-1.5 py-0.5 text-[10px] font-mono text-destructive">
                        {constraint}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Preview Workspace */}
      <div className="lg:col-span-3 space-y-4">
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 p-4 rounded-2xl border border-border bg-card shadow-sm">
          <div className="flex min-w-0 items-center gap-2">
            <div className="h-8 w-8 shrink-0 rounded-lg bg-ape-primary-soft flex items-center justify-center text-ape-primary-text">
              <Eye className="h-4.5 w-4.5" />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-xs font-bold text-muted-foreground uppercase">{t.document.ready}</h2>
              <p className="max-w-full break-words text-sm font-semibold leading-snug text-foreground">
                {exportedFilename || t.document.readyForExport}
              </p>
              {exportReport?.issues?.length > 0 && (
                <p className="text-[11px] text-amber-600 dark:text-amber-400">
                  QA: {exportReport.issues.length} issue(s), see export logs.
                </p>
              )}
            </div>
          </div>

          <div className="flex w-full shrink-0 flex-wrap items-center justify-end gap-2 xl:w-auto xl:self-auto">
            {(() => {
              const documentLabels = t.document as any
              const exportPdfLabel = documentLabels.exportPdf || t.document.exportDocx.replace("DOCX", "PDF")
              const downloadPdfLabel = documentLabels.downloadPdf || t.document.downloadDocx.replace("DOCX", "PDF")
              return exportedPdfFilename ? (
                <Button variant="outline" size="sm" onClick={handleDownloadPdf} className="h-9 shrink-0 gap-1.5 text-xs">
                  <FileDown className="h-3.5 w-3.5 shrink-0" />
                  {downloadPdfLabel}
                </Button>
              ) : (
                <Button variant="outline" size="sm" onClick={handleExportPdf} disabled={exportingPdf} className="h-9 shrink-0 gap-1.5 text-xs">
                  {exportingPdf ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" /> : <FileDown className="h-3.5 w-3.5 shrink-0" />}
                  {exportPdfLabel}
                </Button>
              )
            })()}

            <Button variant="outline" size="sm" onClick={copyToClipboard} className="h-9 shrink-0 text-xs">
              {copied ? (
                <>
                  <Check className="mr-1 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  {t.document.copied}
                </>
              ) : (
                t.document.copy
              )}
            </Button>
            
            {exportedFilename ? (
              <Button size="sm" onClick={handleDownload} className="h-9 shrink-0 gap-1.5 bg-ape-primary text-xs text-primary-foreground shadow-sm hover:bg-ape-primary/90">
                <FileDown className="h-3.5 w-3.5 shrink-0" />
                {t.document.downloadDocx}
              </Button>
            ) : (
              <Button size="sm" onClick={handleExport} disabled={exporting} className="h-9 shrink-0 gap-1.5 bg-ape-primary text-xs text-primary-foreground shadow-sm hover:bg-ape-primary/90">
                {exporting ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" /> : <FileDown className="h-3.5 w-3.5 shrink-0" />}
                {t.document.exportDocx}
              </Button>
            )}
          </div>
        </div>

        {/* Paper Text Display */}
        <div className="rounded-2xl border border-border bg-card p-6 md:p-8 min-h-[300px] shadow-sm relative">
          <div className="absolute top-4 right-4 bg-muted/40 text-[10px] uppercase font-mono text-muted-foreground px-2 py-1 rounded">
            {t.document.preview}
          </div>
          {activeTab === "__full__" ? (
            renderMarkdown(
              allSections
                .filter((s) => !!context[s.id])
                .map((s) => {
                  const text = context[s.id]
                  if (/^\s*#+\s+/.test(text)) {
                    return text
                  }
                  return `# ${s.title}\n\n${text}`
                })
                .join("\n\n")
            )
          ) : activeTab && context[activeTab] ? (
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

function isRenderableTemplateSection(section: any) {
  return String(section?.heading_policy || "render_required") !== "internal_only"
}
