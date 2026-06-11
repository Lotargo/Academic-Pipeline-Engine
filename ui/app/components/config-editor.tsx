"use client"

import { useState, useEffect, ChangeEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { ArrowUp, ArrowDown, Trash2, Plus, Save, RotateCcw, Sliders, Settings2 } from "lucide-react"
import { toast } from "sonner"

export function ConfigEditor() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Fetch config on mount
  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    setLoading(true)
    try {
      const res = await fetch("/api/config")
      if (!res.ok) throw new Error("Failed to load configuration")
      const data = await res.json()
      // Backfill style config if missing
      if (!data.style) {
        data.style = {
          font_name: "Times New Roman",
          font_size: 14,
          title_font_size: 20,
          line_spacing: 1.5,
          first_line_indent_cm: 1.25,
          alignment: "justify",
        }
      }
      setConfig(data)
    } catch (e: any) {
      toast.error(e.message || "Error reading settings")
    } finally {
      setLoading(false)
    }
  }

  const saveConfig = async () => {
    setSaving(true)
    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to update configuration")
      }
      toast.success("Configuration saved and reloaded!")
    } catch (e: any) {
      toast.error(e.message || "Failed to save settings")
    } finally {
      setSaving(false)
    }
  }

  const handleAgentChange = (agentKey: string, field: string, value: any) => {
    setConfig((prev: any) => ({
      ...prev,
      agents: {
        ...prev.agents,
        [agentKey]: {
          ...prev.agents[agentKey],
          [field]: value,
        },
      },
    }))
  }

  const handleStyleChange = (field: string, value: any) => {
    setConfig((prev: any) => ({
      ...prev,
      style: {
        ...prev.style,
        [field]: value,
      },
    }))
  }

  const handleQualityGateChange = (gateKey: string, field: string, value: any) => {
    setConfig((prev: any) => ({
      ...prev,
      quality_gate: {
        ...prev.quality_gate,
        [gateKey]: {
          ...prev.quality_gate[gateKey],
          [field]: value,
        },
      },
    }))
  }

  const moveSection = (index: number, direction: "up" | "down") => {
    const sections = [...config.pipeline.sections]
    const targetIndex = direction === "up" ? index - 1 : index + 1
    if (targetIndex < 0 || targetIndex >= sections.length) return

    const temp = sections[index]
    sections[index] = sections[targetIndex]
    sections[targetIndex] = temp

    setConfig((prev: any) => ({
      ...prev,
      pipeline: {
        ...prev.pipeline,
        sections,
      },
    }))
  }

  const deleteSection = (index: number) => {
    const sections = [...config.pipeline.sections]
    sections.splice(index, 1)
    setConfig((prev: any) => ({
      ...prev,
      pipeline: {
        ...prev.pipeline,
        sections,
      },
    }))
  }

  const addSection = () => {
    const sections = [...config.pipeline.sections]
    sections.push({
      name: `custom_section_${sections.length + 1}`,
      topic: "New Section Topic",
      instruction: "Guidelines for this section.",
    })
    setConfig((prev: any) => ({
      ...prev,
      pipeline: {
        ...prev.pipeline,
        sections,
      },
    }))
  }

  const updateSection = (index: number, field: string, value: any) => {
    const sections = [...config.pipeline.sections]
    sections[index] = {
      ...sections[index],
      [field]: value,
    }
    setConfig((prev: any) => ({
      ...prev,
      pipeline: {
        ...prev.pipeline,
        sections,
      },
    }))
  }

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading configurations...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full overflow-y-auto px-4 py-8 md:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Settings2 className="h-6 w-6 text-teal-600 dark:text-teal-400" />
              Academic PE Settings
            </h1>
            <p className="text-sm text-muted-foreground">
              Configure system roles, agents, quality validation gates, and layout style profiles.
            </p>
          </div>
          <div className="flex items-center gap-2 self-end md:self-auto">
            <Button variant="outline" size="sm" onClick={fetchConfig} className="gap-1">
              <RotateCcw className="h-3.5 w-3.5" />
              Reset
            </Button>
            <Button size="sm" onClick={saveConfig} disabled={saving} className="bg-teal-600 hover:bg-teal-700 text-white gap-1">
              <Save className="h-3.5 w-3.5" />
              {saving ? "Saving..." : "Save Settings"}
            </Button>
          </div>
        </header>

        <Accordion type="multiple" defaultValue={["sections", "layout", "agents"]} className="w-full space-y-4">
          
          {/* Dynamic Sections Manager */}
          <AccordionItem value="sections" className="border rounded-xl bg-card overflow-hidden">
            <AccordionTrigger className="px-5 hover:no-underline hover:bg-accent/30">
              <span className="flex items-center gap-2.5 font-semibold text-[15px]">
                <Sliders className="h-4 w-4 text-teal-600" />
                Document Chapters & Structure
              </span>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 pt-1 space-y-4">
              <p className="text-xs text-muted-foreground">
                Define the outline of the generated paper. Reorder chapters, edit instructions, or add custom sections.
              </p>
              
              <div className="space-y-3">
                {config?.pipeline?.sections?.map((section: any, index: number) => (
                  <div key={index} className="flex flex-col gap-3 rounded-lg border border-border/80 bg-accent/10 p-4 relative group">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-500/10 text-xs font-semibold text-teal-600 dark:text-teal-400">
                          {index + 1}
                        </span>
                        <Input
                          value={section.name}
                          onChange={(e: ChangeEvent<HTMLInputElement>) => updateSection(index, "name", e.target.value)}
                          placeholder="Section Key"
                          className="h-8 w-44 font-semibold text-xs py-1"
                        />
                      </div>
                      
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-foreground"
                          disabled={index === 0}
                          onClick={() => moveSection(index, "up")}
                        >
                          <ArrowUp className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-foreground"
                          disabled={index === config.pipeline.sections.length - 1}
                          onClick={() => moveSection(index, "down")}
                        >
                          <ArrowDown className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-red-500 hover:text-red-600 hover:bg-red-500/10"
                          onClick={() => deleteSection(index)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <label className="text-[11px] font-medium text-muted-foreground">Default Topic Title</label>
                        <Input
                          value={section.topic}
                          onChange={(e: ChangeEvent<HTMLInputElement>) => updateSection(index, "topic", e.target.value)}
                          placeholder="e.g. Theoretical Foundations"
                          className="h-9 text-xs"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[11px] font-medium text-muted-foreground">Drafting Instructions</label>
                        <Input
                          value={section.instruction}
                          onChange={(e: ChangeEvent<HTMLInputElement>) => updateSection(index, "instruction", e.target.value)}
                          placeholder="Guidelines for the Writer Agent"
                          className="h-9 text-xs"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={addSection}
                className="w-full border-dashed border-teal-500/30 hover:border-teal-500/50 hover:bg-teal-500/5 text-teal-600 flex items-center justify-center gap-1 h-9 rounded-lg"
              >
                <Plus className="h-4 w-4" />
                Add Document Section
              </Button>
            </AccordionContent>
          </AccordionItem>

          {/* Document Styling Settings */}
          <AccordionItem value="layout" className="border rounded-xl bg-card overflow-hidden">
            <AccordionTrigger className="px-5 hover:no-underline hover:bg-accent/30">
              <span className="flex items-center gap-2.5 font-semibold text-[15px]">
                <Sliders className="h-4 w-4 text-teal-600" />
                Document Layout & Typography
              </span>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 pt-1 space-y-4">
              <p className="text-xs text-muted-foreground">
                Set formatting metrics applied when compiling final `.docx` output files.
              </p>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Document Title</label>
                  <Input
                    value={config?.pipeline?.title || ""}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => {
                      setConfig((prev: any) => ({
                        ...prev,
                        pipeline: {
                          ...prev.pipeline,
                          title: e.target.value,
                        },
                      }))
                    }}
                    placeholder="GENERATED ACADEMIC PAPER"
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Font Family</label>
                  <Select
                    value={config?.style?.font_name}
                    onValueChange={(val: string) => handleStyleChange("font_name", val)}
                  >
                    <SelectTrigger className="h-9 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Times New Roman">Times New Roman</SelectItem>
                      <SelectItem value="Arial">Arial</SelectItem>
                      <SelectItem value="Calibri">Calibri</SelectItem>
                      <SelectItem value="Georgia">Georgia</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Paragraph Alignment</label>
                  <Select
                    value={config?.style?.alignment}
                    onValueChange={(val: string) => handleStyleChange("alignment", val)}
                  >
                    <SelectTrigger className="h-9 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="justify">Justify (По ширине)</SelectItem>
                      <SelectItem value="left">Left (По левому краю)</SelectItem>
                      <SelectItem value="center">Center (По центру)</SelectItem>
                      <SelectItem value="right">Right (По правому краю)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Body Font Size (pt)</label>
                  <Input
                    type="number"
                    value={config?.style?.font_size}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleStyleChange("font_size", parseInt(e.target.value) || 12)}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Title Font Size (pt)</label>
                  <Input
                    type="number"
                    value={config?.style?.title_font_size}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleStyleChange("title_font_size", parseInt(e.target.value) || 18)}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Line Spacing (e.g. 1.5)</label>
                  <Input
                    type="number"
                    step="0.1"
                    value={config?.style?.line_spacing}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleStyleChange("line_spacing", parseFloat(e.target.value) || 1.5)}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">First Line Indent (cm)</label>
                  <Input
                    type="number"
                    step="0.05"
                    value={config?.style?.first_line_indent_cm}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleStyleChange("first_line_indent_cm", parseFloat(e.target.value) || 1.25)}
                    className="h-9 text-xs"
                  />
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* AI Agents Properties */}
          <AccordionItem value="agents" className="border rounded-xl bg-card overflow-hidden">
            <AccordionTrigger className="px-5 hover:no-underline hover:bg-accent/30">
              <span className="flex items-center gap-2.5 font-semibold text-[15px]">
                <Settings2 className="h-4 w-4 text-teal-600" />
                AI Agent Pipeline & Prompt Configurations
              </span>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 pt-1 space-y-5">
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                {/* Writer Agent Config */}
                <div className="space-y-3 rounded-lg border p-4 bg-muted/20">
                  <div className="flex items-center justify-between border-b pb-2">
                    <h3 className="font-semibold text-sm text-foreground">Writer Agent (Генератор)</h3>
                    <span className="rounded bg-teal-500/10 px-2 py-0.5 text-[10px] font-semibold text-teal-600 dark:text-teal-400">
                      Active
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-muted-foreground">Model Provider</label>
                      <Select
                        value={config?.agents?.writer?.provider}
                        onValueChange={(val: string) => handleAgentChange("writer", "provider", val)}
                      >
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="mock">Mock Engine</SelectItem>
                          <SelectItem value="openai">OpenAI (GPT)</SelectItem>
                          <SelectItem value="custom_openai">Ollama (Custom)</SelectItem>
                          <SelectItem value="anthropic">Claude (Anthropic)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-muted-foreground">Temperature</label>
                      <Input
                        type="number"
                        step="0.05"
                        min="0"
                        max="2"
                        value={config?.agents?.writer?.temperature}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => handleAgentChange("writer", "temperature", parseFloat(e.target.value) || 0.7)}
                        className="h-8 text-xs"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-muted-foreground">Model Name</label>
                    <Input
                      value={config?.agents?.writer?.model}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => handleAgentChange("writer", "model", e.target.value)}
                      placeholder="e.g. gpt-4o"
                      className="h-8 text-xs"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-muted-foreground">System Prompt</label>
                    <Textarea
                      value={config?.agents?.writer?.system_prompt}
                      onChange={(e: ChangeEvent<HTMLTextAreaElement>) => handleAgentChange("writer", "system_prompt", e.target.value)}
                      rows={6}
                      className="text-xs leading-normal"
                    />
                  </div>
                </div>

                {/* Reviewer Agent Config */}
                <div className="space-y-3 rounded-lg border p-4 bg-muted/20">
                  <div className="flex items-center justify-between border-b pb-2">
                    <h3 className="font-semibold text-sm text-foreground">Reviewer Agent (Валидатор)</h3>
                    <span className="rounded bg-teal-500/10 px-2 py-0.5 text-[10px] font-semibold text-teal-600 dark:text-teal-400">
                      Strict
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-muted-foreground">Model Provider</label>
                      <Select
                        value={config?.agents?.reviewer?.provider}
                        onValueChange={(val: string) => handleAgentChange("reviewer", "provider", val)}
                      >
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="mock">Mock Engine</SelectItem>
                          <SelectItem value="openai">OpenAI (GPT)</SelectItem>
                          <SelectItem value="custom_openai">Ollama (Custom)</SelectItem>
                          <SelectItem value="anthropic">Claude (Anthropic)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-muted-foreground">Temperature</label>
                      <Input
                        type="number"
                        step="0.05"
                        min="0"
                        max="2"
                        value={config?.agents?.reviewer?.temperature}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => handleAgentChange("reviewer", "temperature", parseFloat(e.target.value) || 0.3)}
                        className="h-8 text-xs"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-muted-foreground">Model Name</label>
                    <Input
                      value={config?.agents?.reviewer?.model}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => handleAgentChange("reviewer", "model", e.target.value)}
                      placeholder="e.g. gpt-4o"
                      className="h-8 text-xs"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-muted-foreground">System Prompt</label>
                    <Textarea
                      value={config?.agents?.reviewer?.system_prompt}
                      onChange={(e: ChangeEvent<HTMLTextAreaElement>) => handleAgentChange("reviewer", "system_prompt", e.target.value)}
                      rows={6}
                      className="text-xs leading-normal"
                    />
                  </div>
                </div>
              </div>

              {/* Quality Gates Config */}
              <div className="rounded-lg border p-4 bg-muted/20 space-y-4">
                <h3 className="font-semibold text-sm text-foreground border-b pb-2">Quality Gate Filters</h3>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div className="flex items-center justify-between gap-4">
                    <div className="space-y-0.5">
                      <label className="text-xs font-semibold">Volume Validation Gate</label>
                      <p className="text-[10px] text-muted-foreground">Reject draft if section character count is too small.</p>
                    </div>
                    <Switch
                      checked={config?.quality_gate?.volume?.enabled}
                      onCheckedChange={(val: boolean) => handleQualityGateChange("volume", "enabled", val)}
                    />
                  </div>

                  <div className="flex items-center justify-between gap-4">
                    <div className="space-y-0.5">
                      <label className="text-xs font-semibold">LaTeX Format Gate</label>
                      <p className="text-[10px] text-muted-foreground">Ensures inline math symbols are balanced and valid.</p>
                    </div>
                    <Switch
                      checked={config?.quality_gate?.latex?.enabled}
                      onCheckedChange={(val: boolean) => handleQualityGateChange("latex", "enabled", val)}
                    />
                  </div>
                </div>

                {config?.quality_gate?.volume?.enabled && (
                  <div className="w-48 space-y-1">
                    <label className="text-[11px] font-medium text-muted-foreground">Minimum characters per section</label>
                    <Input
                      type="number"
                      value={config?.quality_gate?.volume?.min_chars}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => handleQualityGateChange("volume", "min_chars", parseInt(e.target.value) || 200)}
                      className="h-8 text-xs"
                    />
                  </div>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>
    </div>
  )
}
