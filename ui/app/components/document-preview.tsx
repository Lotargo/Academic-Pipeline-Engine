"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { FileDown, FileText, Check, ListCollapse, Eye } from "lucide-react"

interface DocumentPreviewProps {
  topic: string
  context: Record<string, string>
  docxFilename: string
}

export function DocumentPreview({ topic, context, docxFilename }: DocumentPreviewProps) {
  const [activeTab, setActiveTab] = useState<string>(Object.keys(context)[0] || "")
  const [copied, setCopied] = useState(false)

  const sections = Object.entries(context).filter(([_, text]) => !!text)

  // Ensure an active tab is selected if the tabs list changed
  if (sections.length > 0 && (!activeTab || !context[activeTab])) {
    setActiveTab(sections[0][0])
  }

  const handleDownload = () => {
    if (!docxFilename) return
    window.open(`/api/download/${docxFilename}`, "_blank")
  }

  // Calculate stats
  const totalChars = sections.reduce((acc, [_, text]) => acc + text.length, 0)
  const totalWords = sections.reduce((acc, [_, text]) => acc + text.split(/\s+/).filter(Boolean).length, 0)

  // Custom basic markdown formatter
  const renderMarkdown = (text: string) => {
    if (!text) return <p className="italic text-muted-foreground">Empty content.</p>

    const lines = text.split("\n")
    return (
      <div className="space-y-4 font-serif text-[15px] leading-relaxed text-foreground antialiased select-text">
        {lines.map((line, idx) => {
          const stripped = line.trim()
          if (!stripped) return null

          // H1
          if (stripped.startsWith("# ")) {
            return (
              <h1 key={idx} className="text-xl md:text-2xl font-bold font-sans tracking-tight border-b pb-2 pt-4 text-foreground">
                {stripped.slice(2)}
              </h1>
            )
          }

          // H2
          if (stripped.startsWith("## ")) {
            return (
              <h2 key={idx} className="text-lg md:text-xl font-bold font-sans tracking-tight pt-3 text-foreground">
                {stripped.slice(3)}
              </h2>
            )
          }

          // H3
          if (stripped.startsWith("### ")) {
            return (
              <h3 key={idx} className="text-base md:text-lg font-bold font-sans tracking-tight pt-2 text-foreground">
                {stripped.slice(4)}
              </h3>
            )
          }

          // Table Line
          if (stripped.startsWith("|")) {
            // Check if separator line
            if (stripped.includes("---")) return null
            const cells = stripped.split("|").map(c => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1)
            return (
              <div key={idx} className="overflow-x-auto my-2">
                <table className="min-w-full border-collapse border border-border/80 text-xs">
                  <tbody>
                    <tr className="bg-accent/40">
                      {cells.map((cell, cidx) => (
                        <td key={cidx} className="border border-border/85 px-3 py-2 font-mono">{cell}</td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            )
          }

          // Bullet point
          if (stripped.startsWith("- ") || stripped.startsWith("* ")) {
            return (
              <ul key={idx} className="list-disc list-inside pl-4 my-1">
                <li>{parseInlineStyles(stripped.slice(2))}</li>
              </ul>
            )
          }

          // Standard paragraph
          return <p key={idx} className="indent-6 text-justify">{parseInlineStyles(stripped)}</p>
        })}
      </div>
    )
  }

  // Parse bold, italic, and math ($...$, $$...$$) inline
  const parseInlineStyles = (text: string) => {
    // Escape standard replacements
    const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|\$\$.*?\$\$|\$.*?\$)/g)

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
            {part.slice(2, -2)}
          </span>
        )
      }
      if (part.startsWith("$") && part.endsWith("$")) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-accent/30 font-mono text-xs text-teal-600 dark:text-teal-400 select-all">
            {part.slice(1, -1)}
          </code>
        )
      }
      return part
    })
  }

  const copyToClipboard = () => {
    const fullText = sections.map(([name, text]) => `## ${name.toUpperCase()}\n\n${text}`).join("\n\n")
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
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Chapters</CardTitle>
          </CardHeader>
          <CardContent className="p-0 flex flex-row lg:flex-col gap-1.5 overflow-x-auto lg:overflow-visible">
            {sections.map(([name]) => (
              <button
                key={name}
                onClick={() => setActiveTab(name)}
                className={`w-full text-left px-3 py-2 text-xs font-bold rounded-lg border transition-all shrink-0 capitalize ${
                  activeTab === name
                    ? "border-teal-500 bg-teal-500/5 text-teal-600 dark:text-teal-400 font-semibold"
                    : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                {name}
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Paper Stats */}
        <Card className="rounded-2xl border border-border bg-card p-4 shadow-sm hidden lg:block">
          <CardHeader className="p-1 pb-3">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Document Stats</CardTitle>
          </CardHeader>
          <CardContent className="p-0 space-y-2.5 text-xs">
            <div className="flex justify-between border-b pb-1.5 border-border/40">
              <span className="text-muted-foreground">Total Words:</span>
              <span className="font-semibold">{totalWords}</span>
            </div>
            <div className="flex justify-between border-b pb-1.5 border-border/40">
              <span className="text-muted-foreground">Total Characters:</span>
              <span className="font-semibold">{totalChars}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">File Format:</span>
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
              <h2 className="text-xs font-bold text-muted-foreground uppercase">Document Ready</h2>
              <p className="text-sm font-semibold truncate max-w-xs sm:max-w-md text-foreground">{docxFilename}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <Button variant="outline" size="sm" onClick={copyToClipboard} className="text-xs h-9">
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 mr-1 text-emerald-500" />
                  Copied Text
                </>
              ) : (
                "Copy Content"
              )}
            </Button>
            
            {docxFilename && (
              <Button size="sm" onClick={handleDownload} className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9 gap-1.5 shadow-sm">
                <FileDown className="h-3.5 w-3.5" />
                Download DOCX
              </Button>
            )}
          </div>
        </div>

        {/* Paper Text Display */}
        <div className="rounded-2xl border border-border bg-card p-6 md:p-8 min-h-[300px] shadow-sm relative">
          <div className="absolute top-4 right-4 bg-muted/40 text-[9px] uppercase tracking-wider font-mono text-muted-foreground px-2 py-1 rounded">
            Academic Layout Preview
          </div>
          {activeTab && context[activeTab] ? (
            renderMarkdown(context[activeTab])
          ) : (
            <div className="flex h-48 w-full items-center justify-center text-muted-foreground text-sm italic">
              No content compiled for this chapter yet.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
