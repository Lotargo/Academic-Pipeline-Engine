import { useState } from "react"
import { FileText, Loader2, Sparkles, CheckCircle2, PenTool, Check, Copy, FileDown } from "lucide-react"

interface LiveDocumentCanvasProps {
  status: any
}

export function LiveDocumentCanvas({ status }: LiveDocumentCanvasProps) {
  const [copied, setCopied] = useState(false)
  const context = status?.context || {}
  const activeState = status?.state || "INIT"
  const isRunning = status?.status === "RUNNING"
  const isCompleted = status?.status === "COMPLETED" || activeState === "DONE"

  const handleDownload = () => {
    const docxFilename = status?.docx_filename
    if (!docxFilename) return
    window.open(`/api/download/${docxFilename}`, "_blank")
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

  // Standard ordered list of sections
  const sectionMeta = [
    { id: "theory", title: "1. Theoretical Foundations" },
    { id: "calculation", title: "2. Quantitative Analysis & Models" },
    { id: "conclusion", title: "3. Summary & Outlook" },
  ]

  // Add any extra sections present in context but not in meta
  const extraSections = Object.keys(context).filter(
    (k) => !sectionMeta.some((m) => m.id === k)
  )
  const allSections = [
    ...sectionMeta,
    ...extraSections.map((k) => ({
      id: k,
      title: k.charAt(0).toUpperCase() + k.slice(1),
    })),
  ]

  // Determine active section index during drafting
  let activeSectionId = ""
  if (activeState === "DRAFTING") {
    // Active is the first section that hasn't been drafted yet
    const nextToDraft = allSections.find((s) => !context[s.id])
    if (nextToDraft) {
      activeSectionId = nextToDraft.id
    }
  }

  // Inline styling parser (supports bold, italic, and LaTeX blocks)
  const parseInlineStyles = (text: string) => {
    if (!text) return null
    const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|\$\$.*?\$\$|\$.*?\$)/g)

    return parts.map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={index} className="font-bold text-zinc-900 dark:text-zinc-50">{part.slice(2, -2)}</strong>
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={index} className="italic text-zinc-800 dark:text-zinc-200">{part.slice(1, -1)}</em>
      }
      if (part.startsWith("$$") && part.endsWith("$$")) {
        return (
          <span key={index} className="block my-3 py-2 px-4 rounded bg-zinc-100 dark:bg-zinc-800/50 font-mono text-center text-xs border border-zinc-200 dark:border-zinc-700 select-all text-teal-600 dark:text-teal-400">
            {part.slice(2, -2)}
          </span>
        )
      }
      if (part.startsWith("$") && part.endsWith("$")) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800/80 font-mono text-xs text-teal-600 dark:text-teal-400 select-all">
            {part.slice(1, -1)}
          </code>
        )
      }
      return part
    })
  }

  // Render paragraphs and headers
  const renderContent = (text: string) => {
    if (!text) return null
    return text.split("\n").map((line, idx) => {
      const stripped = line.trim()
      if (!stripped) return null

      if (stripped.startsWith("# ")) {
        return (
          <h2 key={idx} className="text-lg font-bold font-sans tracking-tight border-b border-zinc-200 dark:border-zinc-800 pb-1 pt-3 mb-2 text-zinc-900 dark:text-zinc-50">
            {stripped.slice(2)}
          </h2>
        )
      }
      if (stripped.startsWith("## ")) {
        return (
          <h3 key={idx} className="text-base font-bold font-sans tracking-tight pt-2 mb-2 text-zinc-800 dark:text-zinc-100">
            {stripped.slice(3)}
          </h3>
        )
      }
      if (stripped.startsWith("- ") || stripped.startsWith("* ")) {
        return (
          <ul key={idx} className="list-disc list-inside pl-4 my-1 text-zinc-700 dark:text-zinc-300">
            <li>{parseInlineStyles(stripped.slice(2))}</li>
          </ul>
        )
      }
      if (stripped.startsWith("|")) {
        if (stripped.includes("---")) return null
        const cells = stripped.split("|").map(c => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1)
        return (
          <div key={idx} className="overflow-x-auto my-2 border border-zinc-200 dark:border-zinc-850 rounded">
            <table className="min-w-full border-collapse text-xs">
              <tbody>
                <tr className="bg-zinc-50 dark:bg-zinc-900/60">
                  {cells.map((cell, cidx) => (
                    <td key={cidx} className="border border-zinc-200 dark:border-zinc-800 px-3 py-1.5 font-mono text-zinc-700 dark:text-zinc-300">{cell}</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )
      }

      return (
        <p key={idx} className="indent-6 text-justify text-zinc-700 dark:text-zinc-300 mb-3 leading-relaxed">
          {parseInlineStyles(stripped)}
        </p>
      )
    })
  }

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      {/* Document Sheet Container */}
      <div className="relative flex-1 bg-[#fdfdfc] dark:bg-[#151518] text-zinc-850 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-800/80 rounded-2xl shadow-xl p-6 md:p-10 font-serif min-h-[650px] overflow-y-auto max-h-[80vh] scrollbar-thin scrollbar-thumb-zinc-200 dark:scrollbar-thumb-zinc-800 transition-all duration-300">
        
        {/* Paper Header / Running Metadata */}
        <div className="flex items-center justify-between border-b border-zinc-200/60 dark:border-zinc-800/60 pb-3 mb-6 text-[10px] font-mono tracking-widest text-zinc-400 dark:text-zinc-500 uppercase">
          <div className="flex items-center gap-1.5">
            <FileText className="h-3 w-3" />
            <span>Academic PE Compiler</span>
          </div>
          <div className="flex items-center gap-2">
            {isRunning && (
              <>
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-500" />
                </span>
                <span className="text-amber-500 font-bold">Compiling Draft ({activeState})</span>
              </>
            )}
            {isCompleted && (
              <div className="flex items-center gap-1.5 lowercase tracking-normal font-sans">
                <button
                  onClick={copyToClipboard}
                  className="px-2 py-1 rounded bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors flex items-center gap-1 text-[10px] font-bold text-zinc-650 dark:text-zinc-400 cursor-pointer border-0"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-emerald-500" />
                      copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      copy
                    </>
                  )}
                </button>
                {status?.docx_filename && (
                  <button
                    onClick={handleDownload}
                    className="px-2 py-1 rounded bg-teal-50 dark:bg-teal-950/20 text-teal-600 dark:text-teal-400 hover:bg-teal-100 dark:hover:bg-teal-950/40 transition-colors flex items-center gap-1 text-[10px] font-bold cursor-pointer border-0"
                  >
                    <FileDown className="h-3.5 w-3.5" />
                    download docx
                  </button>
                )}
                <span className="text-emerald-500 font-bold uppercase tracking-widest flex items-center gap-0.5 ml-1.5">
                  <CheckCircle2 className="h-3 w-3 animate-pulse" /> Ready
                </span>
              </div>
            )}
            {!isRunning && !isCompleted && <span className="text-zinc-400">Idle</span>}
          </div>
        </div>

        {/* Paper Title Block */}
        <div className="text-center space-y-3 mb-10">
          <h1 className="text-2xl md:text-3xl font-extrabold font-sans tracking-tight text-zinc-900 dark:text-zinc-50 leading-tight">
            {status?.topic || "Technical Research Paper Draft"}
          </h1>
          <div className="text-[11px] font-sans text-zinc-400 dark:text-zinc-500 tracking-wide uppercase italic">
            Automated Generation Loop by Cooperative Agents
          </div>
          <div className="w-20 h-0.5 bg-teal-500/30 mx-auto rounded-full mt-4" />
        </div>

        {/* Sections Content Output */}
        <div className="space-y-8 select-text">
          {allSections.map((section) => {
            const hasContent = !!context[section.id]
            const isDrafting = activeSectionId === section.id

            return (
              <div key={section.id} className="relative group transition-all duration-300">
                
                {/* Section Header */}
                <div className="flex items-center justify-between mb-3 border-b border-zinc-150/50 dark:border-zinc-800/30 pb-1.5">
                  <h2 className="text-sm font-sans font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                    {section.title}
                  </h2>
                  <div className="text-[10px] font-sans">
                    {hasContent ? (
                      <span className="text-emerald-500 dark:text-emerald-400 font-bold flex items-center gap-1">
                        <CheckCircle2 className="h-3 w-3" /> Compiled
                      </span>
                    ) : isDrafting ? (
                      <span className="text-amber-500 dark:text-amber-400 font-bold flex items-center gap-1 animate-pulse">
                        <Loader2 className="h-3 w-3 animate-spin" /> Drafting...
                      </span>
                    ) : (
                      <span className="text-zinc-350 dark:text-zinc-650">Pending</span>
                    )}
                  </div>
                </div>

                {/* Section Content / Loading Card / Placeholder */}
                {hasContent ? (
                  <div className="animate-in fade-in duration-500">
                    {renderContent(context[section.id])}
                  </div>
                ) : isDrafting ? (
                  <div className="rounded-xl border border-dashed border-amber-300 dark:border-amber-900/50 bg-amber-50/10 dark:bg-amber-950/5 p-6 animate-pulse flex flex-col items-center justify-center text-center space-y-3">
                    <PenTool className="h-5 w-5 text-amber-500 animate-bounce" />
                    <div>
                      <h4 className="text-xs font-sans font-bold text-zinc-800 dark:text-zinc-200">Writer Agent Drafting</h4>
                      <p className="text-[11px] font-sans text-zinc-400 dark:text-zinc-500 mt-1 max-w-sm">
                        Generating styled content, markdown sections, and LaTeX complexity metrics for this chapter.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800/60 p-6 flex flex-col items-center justify-center text-center text-zinc-300 dark:text-zinc-700">
                    <span className="text-xs font-sans italic">Awaiting document compiler pipeline...</span>
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
