"use client"

import { useState, useEffect, ChangeEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { ArrowUp, ArrowDown, Trash2, Plus, Save, RotateCcw, Sliders, Settings2, AlertTriangle, Eye, EyeOff } from "lucide-react"
import { toast } from "sonner"
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

type DocumentTemplateSummary = {
  id: string
  name: string
  description?: string
  category?: string
  section_count?: number
}

export function ConfigEditor({ language = "en" }: { language?: string }) {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [secretsStatus, setSecretsStatus] = useState<Record<string, boolean>>({})
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({})
  const [writerModels, setWriterModels] = useState<string[]>([])
  const [reviewerModels, setReviewerModels] = useState<string[]>([])
  const [plannerModels, setPlannerModels] = useState<string[]>([])
  const [researcherModels, setResearcherModels] = useState<string[]>([])
  const [exampleGeneratorModels, setExampleGeneratorModels] = useState<string[]>([])
  const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({})
  const [documentTemplates, setDocumentTemplates] = useState<DocumentTemplateSummary[]>([])
  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({})
  const [resetDialogOpen, setResetDialogOpen] = useState(false)
  const [activeAgentTab, setActiveAgentTab] = useState<string>("writer")

  const toggleShowApiKey = (provider: string) => {
    setShowApiKeys(prev => ({ ...prev, [provider]: !prev[provider] }))
  }

  // Fetch config and secrets status on mount
  useEffect(() => {
    fetchConfig()
    fetchSecretsStatus()
    fetchDocumentTemplates()
  }, [])

  // Auto load models when config is loaded
  useEffect(() => {
    if (config?.agents) {
      if (config.agents.writer) {
        fetchModelsForAgent("writer", config.agents.writer.provider, config.agents.writer.base_url)
      }
      if (config.agents.reviewer) {
        fetchModelsForAgent("reviewer", config.agents.reviewer.provider, config.agents.reviewer.base_url)
      }
      if (config.agents.planner) {
        fetchModelsForAgent("planner", config.agents.planner.provider, config.agents.planner.base_url)
      }
      if (config.agents.researcher) {
        fetchModelsForAgent("researcher", config.agents.researcher.provider, config.agents.researcher.base_url)
      }
      if (config.agents.example_generator) {
        fetchModelsForAgent("example_generator", config.agents.example_generator.provider, config.agents.example_generator.base_url)
      }
    }
  }, [config === null])

  const fetchSecretsStatus = async () => {
    try {
      const res = await fetch("/api/secrets")
      if (res.ok) {
        const data = await res.json()
        const statusMap: Record<string, boolean> = {}
        const keysMap: Record<string, string> = {}
        for (const [provider, key] of Object.entries(data)) {
          statusMap[provider] = !!key
          keysMap[provider] = (key as string) || ""
        }
        setSecretsStatus(statusMap)
        setApiKeys(keysMap)
      }
    } catch (e) {
      console.error("Error loading secrets status:", e)
    }
  }

  const fetchDocumentTemplates = async () => {
    try {
      const res = await fetch("/api/templates")
      if (res.ok) {
        const data = await res.json()
        setDocumentTemplates(data)
      }
    } catch (e) {
      console.error("Error loading document templates:", e)
    }
  }

  const handleHardReset = () => {
    setResetDialogOpen(true);
  };

  const executeHardReset = async () => {
    setResetDialogOpen(false);
    try {
      const res = await fetch("/api/history/reset", {
        method: "POST"
      });
      if (res.ok) {
        toast.success(language === "ru" ? "База данных и все файлы успешно очищены!" : "Database and all files cleared successfully!");
        window.dispatchEvent(new CustomEvent("ape-history-reset"));
      } else {
        const err = await res.json();
        throw new Error(err.detail || "Reset failed");
      }
    } catch (e: any) {
      toast.error(language === "ru" ? `Сброс не удался: ${e.message}` : `Reset failed: ${e.message}`);
    }
  };

  const fetchModelsForAgent = async (agentKey: string, provider: string, baseUrl?: string) => {
    if (!provider || provider === "mock") {
      const defaultModels = ["mock-model-1", "mock-model-2"]
      if (agentKey === "writer") setWriterModels(defaultModels)
      else if (agentKey === "reviewer") setReviewerModels(defaultModels)
      else if (agentKey === "planner") setPlannerModels(defaultModels)
      else if (agentKey === "researcher") setResearcherModels(defaultModels)
      else if (agentKey === "example_generator") setExampleGeneratorModels(defaultModels)
      return
    }
    setLoadingModels(prev => ({ ...prev, [agentKey]: true }))
    try {
      let url = `/api/models?provider=${provider}`
      if (baseUrl) {
        url += `&base_url=${encodeURIComponent(baseUrl)}`
      }
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        if (agentKey === "writer") setWriterModels(data)
        else if (agentKey === "reviewer") setReviewerModels(data)
        else if (agentKey === "planner") setPlannerModels(data)
        else if (agentKey === "researcher") setResearcherModels(data)
        else if (agentKey === "example_generator") setExampleGeneratorModels(data)
      }
    } catch (e) {
      console.error(`Error fetching models for ${agentKey}:`, e)
    } finally {
      setLoadingModels(prev => ({ ...prev, [agentKey]: false }))
    }
  }

  const handleSaveApiKey = async (provider: string) => {
    const key = apiKeys[provider]
    if (!key || !key.trim()) {
      toast.error("Please enter a valid API key")
      return
    }
    try {
      const res = await fetch("/api/secrets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: key }),
      })
      if (!res.ok) throw new Error("Failed to save API key")
      toast.success(`API key for ${provider} saved securely!`)
      
      // Update secrets status
      await fetchSecretsStatus()
      
      // Keep saved key in state to let the user view/edit it
      // setApiKeys(prev => ({ ...prev, [provider]: "" }))
      
      // Trigger models fetch since key is updated
      if (config?.agents?.writer?.provider === provider) {
        fetchModelsForAgent("writer", provider, config?.agents?.writer?.base_url)
      }
      if (config?.agents?.reviewer?.provider === provider) {
        fetchModelsForAgent("reviewer", provider, config?.agents?.reviewer?.base_url)
      }
      if (config?.agents?.planner?.provider === provider) {
        fetchModelsForAgent("planner", provider, config?.agents?.planner?.base_url)
      }
      if (config?.agents?.researcher?.provider === provider) {
        fetchModelsForAgent("researcher", provider, config?.agents?.researcher?.base_url)
      }
      if (config?.agents?.example_generator?.provider === provider) {
        fetchModelsForAgent("example_generator", provider, config?.agents?.example_generator?.base_url)
      }
    } catch (e: any) {
      toast.error(e.message || "Failed to save secret key")
    }
  }

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
      if (!data.ui) {
        data.ui = { language: "ru" }
      }
      if (data.dynamic_examples_enabled === undefined) {
        data.dynamic_examples_enabled = true
      }
      if (data.dynamic_examples_interval_mins === undefined) {
        data.dynamic_examples_interval_mins = 15
      }
      if (!data.pipeline.template_mode) {
        data.pipeline.template_mode = "custom"
      }
      if (data.pipeline.template_id === undefined) {
        data.pipeline.template_id = null
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
      // 1. Save any pending API keys first
      for (const [provider, key] of Object.entries(apiKeys)) {
        if (key && key.trim()) {
          const secretRes = await fetch("/api/secrets", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider, api_key: key }),
          })
          if (!secretRes.ok) throw new Error(`Failed to save API key for ${provider}`)
        }
      }
      setApiKeys({})
      await fetchSecretsStatus()

      // 2. Save config
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to update configuration")
      }
      window.dispatchEvent(new CustomEvent("ape-config-saved"))
      toast.success("Configuration saved and reloaded!")
    } catch (e: any) {
      toast.error(e.message || "Failed to save settings")
    } finally {
      setSaving(false)
    }
  }

  const handleAgentChange = (agentKey: string, field: string, value: any) => {
    setConfig((prev: any) => {
      const updatedAgent = {
        ...prev.agents[agentKey],
        [field]: value,
      }
      
      if (field === "provider" || field === "base_url") {
        fetchModelsForAgent(agentKey, updatedAgent.provider, updatedAgent.base_url)
      }
      
      return {
        ...prev,
        agents: {
          ...prev.agents,
          [agentKey]: updatedAgent,
        },
      }
    })
  }

  const renderAgentConfig = (agentKey: string) => {
    const agent = config?.agents?.[agentKey]
    if (!agent) return null

    let tag = "Agent"
    let defaultTemp = 0.5
    if (agentKey === "writer") {
      tag = language === "ru" ? "Активный" : "Active"
      defaultTemp = 0.7
    } else if (agentKey === "reviewer") {
      tag = language === "ru" ? "Строгий" : "Strict"
      defaultTemp = 0.3
    } else if (agentKey === "planner") {
      tag = language === "ru" ? "Планировщик" : "Planner"
      defaultTemp = 0.2
    } else if (agentKey === "researcher") {
      tag = language === "ru" ? "Поиск" : "Research"
      defaultTemp = 0.1
    } else if (agentKey === "example_generator") {
      tag = language === "ru" ? "Динамический" : "Dynamic"
      defaultTemp = 0.8
    }

    const agentModels = 
      agentKey === "writer" ? writerModels :
      agentKey === "reviewer" ? reviewerModels :
      agentKey === "planner" ? plannerModels :
      agentKey === "researcher" ? researcherModels :
      exampleGeneratorModels;

    const agentTitle = 
      agentKey === "writer" ? (language === "ru" ? "Writer Agent (Писатель)" : "Writer Agent") :
      agentKey === "reviewer" ? (language === "ru" ? "Reviewer Agent (Рецензент)" : "Reviewer Agent") :
      agentKey === "planner" ? (language === "ru" ? "Planner Agent (Планировщик)" : "Planner Agent") :
      agentKey === "researcher" ? (language === "ru" ? "Researcher Agent (Исследователь)" : "Researcher Agent") :
      (language === "ru" ? "Example Generator Agent (Генератор примеров)" : "Example Generator Agent");

    const provider = agent.provider || "mock"
    const showKey = showApiKeys[provider] || false
    const currentKey = apiKeys[provider] || ""

    return (
      <div className="space-y-4 rounded-xl border border-border/60 p-5 bg-muted/10">
        <div className="flex items-center justify-between border-b border-border/40 pb-3">
          <div>
            <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
              {agentTitle}
            </h3>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {agentKey === "writer" && (language === "ru" ? "Пишет разделы документа на основе плана и контекста." : "Writes document sections based on the plan and context.")}
              {agentKey === "reviewer" && (language === "ru" ? "Проверяет разделы на логику, стиль и корректность LaTeX." : "Checks sections for logic, style, and LaTeX correctness.")}
              {agentKey === "planner" && (language === "ru" ? "Создает структуру документа и инструкции для писателя." : "Creates the document structure and instructions for the writer.")}
              {agentKey === "researcher" && (language === "ru" ? "Ищет информацию в веб-поиске и готовит выдержки." : "Searches for information on the web and prepares summaries.")}
              {agentKey === "example_generator" && (language === "ru" ? "Генерирует примеры тем для начального заполнения." : "Generates topic examples for initial seeding.")}
            </p>
          </div>
          <span className="rounded bg-ape-primary-soft px-2.5 py-1 text-[10px] font-semibold text-ape-primary-text border border-ape-primary-text/10">
            {tag}
          </span>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-muted-foreground">{language === "ru" ? "Провайдер модели" : "Model Provider"}</label>
              <Select
                value={provider}
                onValueChange={(val: string) => handleAgentChange(agentKey, "provider", val)}
              >
                <SelectTrigger className="h-9 text-xs w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mock">{language === "ru" ? "Тестовый движок (Mock)" : "Mock Engine"}</SelectItem>
                  <SelectItem value="openai">OpenAI (GPT)</SelectItem>
                  <SelectItem value="google">Google (Gemini)</SelectItem>
                  <SelectItem value="custom_openai">{language === "ru" ? "OpenAI совместимый (Свой)" : "OpenAI Compatible (Custom)"}</SelectItem>
                  <SelectItem value="lm_studio">LM Studio</SelectItem>
                  <SelectItem value="zen">OpenCode Zen</SelectItem>
                  <SelectItem value="anthropic">Claude (Anthropic)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-medium text-muted-foreground">{language === "ru" ? "Название модели" : "Model Name"}</label>
                {loadingModels[agentKey] && (
                  <span className="text-[9px] text-ape-primary-text animate-pulse font-medium">{language === "ru" ? "Загрузка..." : "Fetching..."}</span>
                )}
              </div>
              <Input
                list={`${agentKey}-models-list`}
                value={agent.model || ""}
                onChange={(e: ChangeEvent<HTMLInputElement>) => handleAgentChange(agentKey, "model", e.target.value)}
                placeholder={language === "ru" ? "Выберите или введите название модели" : "Select or type model name"}
                className="h-9 text-xs"
              />
              <datalist id={`${agentKey}-models-list`}>
                {agentModels.map((m: string) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-muted-foreground">{language === "ru" ? "Температура" : "Temperature"}</label>
              <Input
                type="number"
                step="0.05"
                min="0"
                max="2"
                value={agent.temperature ?? defaultTemp}
                onChange={(e: ChangeEvent<HTMLInputElement>) => handleAgentChange(agentKey, "temperature", parseFloat(e.target.value) ?? defaultTemp)}
                className="h-9 text-xs"
              />
            </div>

            {provider && provider !== "mock" && (
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground">{language === "ru" ? "API Ключ" : "API Key"}</label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Input
                      type={showKey ? "text" : "password"}
                      value={currentKey}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => {
                        const val = e.target.value;
                        setApiKeys((prev: any) => ({ ...prev, [provider]: val }))
                      }}
                      placeholder={language === "ru" ? "Введите API ключ" : "Enter API Key"}
                      className="h-9 text-xs pr-10 w-full"
                    />
                    <button
                      type="button"
                      onClick={() => toggleShowApiKey(provider)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer bg-transparent border-0 p-0 flex items-center justify-center z-10"
                    >
                      {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleSaveApiKey(provider)}
                    className="h-9 text-xs px-3 font-semibold"
                  >
                    {language === "ru" ? "Сохранить" : "Save Key"}
                  </Button>
                </div>
              </div>
            )}

            {(provider === "custom_openai" || provider === "lm_studio") && (
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground">{language === "ru" ? "Адрес сервера (Base URL)" : "Base URL"}</label>
                <Input
                  value={agent.base_url || ""}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => handleAgentChange(agentKey, "base_url", e.target.value)}
                  placeholder={provider === "lm_studio" ? "http://localhost:1234/v1" : "http://localhost:11434/v1"}
                  className="h-9 text-xs"
                />
              </div>
            )}
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-[11px] font-medium text-muted-foreground">{language === "ru" ? "Системный промпт" : "System Prompt"}</label>
          <Textarea
            value={agent.system_prompt || ""}
            onChange={(e: ChangeEvent<HTMLTextAreaElement>) => handleAgentChange(agentKey, "system_prompt", e.target.value)}
            rows={8}
            className="text-xs leading-relaxed font-mono"
          />
        </div>
      </div>
    )
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

  const handlePipelineChange = (field: string, value: any) => {
    setConfig((prev: any) => ({
      ...prev,
      pipeline: {
        ...prev.pipeline,
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
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-ape-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading configurations...</p>
        </div>
      </div>
    )
  }

  if (!config) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-4 text-center p-8">
        <AlertTriangle className="h-12 w-12 text-destructive animate-bounce" />
        <h2 className="text-lg font-semibold text-foreground">Failed to load configuration</h2>
        <p className="text-sm text-muted-foreground max-w-sm">
          Please make sure the backend server is running and accessible.
        </p>
        <Button onClick={fetchConfig} className="bg-ape-primary hover:bg-ape-primary/90 text-primary-foreground gap-2">
          <RotateCcw className="h-4 w-4" />
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="h-full w-full overflow-y-auto px-4 py-8 md:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Settings2 className="h-6 w-6 text-ape-primary-text" />
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
            <Button size="sm" onClick={saveConfig} disabled={saving} className="bg-ape-primary hover:bg-ape-primary/90 text-primary-foreground gap-1">
              <Save className="h-3.5 w-3.5" />
              {saving ? "Saving..." : "Save Settings"}
            </Button>
          </div>
        </header>

        <Accordion type="multiple" defaultValue={["sections", "layout", "agents"]} className="w-full space-y-4">
          
          {/* Template Selection and Custom Sections Manager */}
          <AccordionItem value="sections" className="border rounded-xl bg-card overflow-hidden">
            <AccordionTrigger className="px-5 hover:no-underline hover:bg-accent/30">
              <span className="flex items-center gap-2.5 font-semibold text-[15px]">
                <Sliders className="h-4 w-4 text-ape-primary-text" />
                Document Template Selection
              </span>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 pt-1 space-y-4">
              <p className="text-xs text-muted-foreground">
                Choose how each run receives its document structure. The section editor below defines only the live
                custom_current template used by Custom mode.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 rounded-lg border border-border/80 bg-muted/20 p-4">
                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-muted-foreground">Template Mode</label>
                  <Select
                    value={config?.pipeline?.template_mode || "custom"}
                    onValueChange={(val: string) => {
                      setConfig((prev: any) => ({
                        ...prev,
                        pipeline: {
                          ...prev.pipeline,
                          template_mode: val,
                          template_id: val === "fixed"
                            ? (prev.pipeline.template_id || documentTemplates[0]?.id || null)
                            : null,
                        },
                      }))
                    }}
                  >
                    <SelectTrigger className="h-9 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="custom">Custom current sections</SelectItem>
                      <SelectItem value="fixed">Saved template</SelectItem>
                      <SelectItem value="auto">Auto planner runtime template</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-muted-foreground">Saved Template</label>
                  <Select
                    value={config?.pipeline?.template_id || ""}
                    disabled={config?.pipeline?.template_mode !== "fixed" || documentTemplates.length === 0}
                    onValueChange={(val: string) => handlePipelineChange("template_id", val)}
                  >
                    <SelectTrigger className="h-9 text-xs">
                      <SelectValue placeholder="Select a saved template" />
                    </SelectTrigger>
                    <SelectContent>
                      {documentTemplates.map((template) => (
                        <SelectItem key={template.id} value={template.id}>
                          {template.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="md:col-span-2 text-[11px] leading-relaxed text-muted-foreground">
                  {config?.pipeline?.template_mode === "fixed" && config?.pipeline?.template_id ? (
                    <>
                      Active saved template:{" "}
                      <span className="font-medium text-foreground">
                        {documentTemplates.find((template) => template.id === config.pipeline.template_id)?.name || config.pipeline.template_id}
                      </span>
                      . Custom sections remain editable, but they are ignored while Fixed mode is active.
                    </>
                  ) : config?.pipeline?.template_mode === "auto" ? (
                    <>
                      Auto mode asks the Planner agent to create a temporary runtime template from the user request.
                      Custom sections are kept for later but are not used in Auto mode.
                    </>
                  ) : (
                    <>
                      Custom mode uses the sections below as the active runtime template for generation.
                    </>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-foreground">custom_current Section Editor</h3>
                {config?.pipeline?.template_mode !== "custom" && (
                  <span className="rounded bg-amber-500/10 px-2 py-1 text-[10px] font-medium text-amber-700 dark:text-amber-300">
                    Inactive for current mode
                  </span>
                )}
              </div>
              
              <div className="space-y-3">
                {config?.pipeline?.sections?.map((section: any, index: number) => (
                  <div
                    key={index}
                    className={`flex flex-col gap-3 rounded-lg border border-border/80 p-4 relative group ${
                      config?.pipeline?.template_mode === "custom"
                        ? "bg-accent/10"
                        : "bg-muted/20 opacity-70"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ape-primary-soft text-xs font-semibold text-ape-primary-text">
                          {index + 1}
                        </span>
                        <Input
                          value={section.name}
                          onChange={(e: ChangeEvent<HTMLInputElement>) => updateSection(index, "name", e.target.value)}
                          placeholder="Section Key"
                          disabled={config?.pipeline?.template_mode !== "custom"}
                          className="h-8 w-44 font-semibold text-xs py-1"
                        />
                      </div>
                      
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-foreground"
                          disabled={config?.pipeline?.template_mode !== "custom" || index === 0}
                          onClick={() => moveSection(index, "up")}
                        >
                          <ArrowUp className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-foreground"
                          disabled={config?.pipeline?.template_mode !== "custom" || index === config.pipeline.sections.length - 1}
                          onClick={() => moveSection(index, "down")}
                        >
                          <ArrowDown className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-red-500 hover:text-red-600 hover:bg-red-500/10"
                          disabled={config?.pipeline?.template_mode !== "custom"}
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
                          disabled={config?.pipeline?.template_mode !== "custom"}
                          className="h-9 text-xs"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[11px] font-medium text-muted-foreground">Drafting Instructions</label>
                        <Input
                          value={section.instruction}
                          onChange={(e: ChangeEvent<HTMLInputElement>) => updateSection(index, "instruction", e.target.value)}
                          placeholder="Guidelines for the Writer Agent"
                          disabled={config?.pipeline?.template_mode !== "custom"}
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
                disabled={config?.pipeline?.template_mode !== "custom"}
                className="w-full border-dashed border-ape-primary/30 hover:border-ape-primary/50 hover:bg-ape-primary-soft text-ape-primary-text flex items-center justify-center gap-1 h-9 rounded-lg"
              >
                <Plus className="h-4 w-4" />
                Add custom_current Section
              </Button>
            </AccordionContent>
          </AccordionItem>

          {/* Document Styling Settings */}
          <AccordionItem value="layout" className="border rounded-xl bg-card overflow-hidden">
            <AccordionTrigger className="px-5 hover:no-underline hover:bg-accent/30">
              <span className="flex items-center gap-2.5 font-semibold text-[15px]">
                <Sliders className="h-4 w-4 text-ape-primary-text" />
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
                  <label className="text-xs font-medium text-muted-foreground">Document Language</label>
                  <Select
                    value={config?.pipeline?.language || "auto"}
                    onValueChange={(val: string) => {
                      setConfig((prev: any) => ({
                        ...prev,
                        pipeline: {
                          ...prev.pipeline,
                          language: val,
                        },
                      }))
                    }}
                  >
                    <SelectTrigger className="h-9 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Auto (prompt language)</SelectItem>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="ru">Russian</SelectItem>
                      <SelectItem value="zh">Chinese</SelectItem>
                    </SelectContent>
                  </Select>
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
                      <SelectItem value="justify">Justify</SelectItem>
                      <SelectItem value="left">Left</SelectItem>
                      <SelectItem value="center">Center</SelectItem>
                      <SelectItem value="right">Right</SelectItem>
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
                <Settings2 className="h-4 w-4 text-ape-primary-text" />
                AI Agent Pipeline & Prompt Configurations
              </span>
            </AccordionTrigger>
            <AccordionContent className="px-5 pb-5 pt-1 space-y-5">
              
              {/* Dynamic Examples Toggle */}
              <div className="rounded-lg border p-4 bg-muted/20 flex flex-col gap-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="space-y-0.5">
                    <label className="text-xs font-semibold">Dynamic Examples Generator</label>
                    <p className="text-[10px] text-muted-foreground">
                      Automatically generate fresh academic writing topics and guidelines periodically.
                    </p>
                  </div>
                  <Switch
                    checked={config?.dynamic_examples_enabled ?? true}
                    onCheckedChange={(val: boolean) => {
                      setConfig((prev: any) => ({
                        ...prev,
                        dynamic_examples_enabled: val,
                      }))
                    }}
                  />
                </div>
                {(config?.dynamic_examples_enabled ?? true) && (
                  <div className="w-48 space-y-1 pt-2 border-t border-border/40">
                    <label className="text-[11px] font-medium text-muted-foreground">Update Interval (minutes)</label>
                    <Input
                      type="number"
                      min="1"
                      max="1440"
                      value={config?.dynamic_examples_interval_mins ?? 15}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => {
                        setConfig((prev: any) => ({
                          ...prev,
                          dynamic_examples_interval_mins: parseInt(e.target.value) || 15,
                        }))
                      }}
                      className="h-8 text-xs"
                    />
                  </div>
                )}
              </div>

              {/* Agent Tabs */}
              <div className="flex flex-wrap gap-1 border-b border-border/40 pb-px">
                {[
                  { id: "writer", label: language === "ru" ? "Writer (Писатель)" : "Writer Agent" },
                  { id: "reviewer", label: language === "ru" ? "Reviewer (Рецензент)" : "Reviewer Agent" },
                  { id: "planner", label: language === "ru" ? "Planner (Планировщик)" : "Planner Agent" },
                  { id: "researcher", label: language === "ru" ? "Researcher (Исследователь)" : "Researcher Agent" },
                  { id: "example_generator", label: language === "ru" ? "Example Gen (Генератор)" : "Example Generator" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveAgentTab(tab.id)}
                    className={`px-4 py-2 text-xs font-semibold rounded-t-lg transition-all duration-200 border-b-2 -mb-[2px] ${
                      activeAgentTab === tab.id
                        ? "border-ape-primary-text text-ape-primary-text bg-ape-primary-soft/30"
                        : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/10"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Active Agent Configuration Panel */}
              <div className="pt-2">
                {renderAgentConfig(activeAgentTab)}
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

        {/* Danger Zone */}
        <div className="rounded-xl border border-destructive/30 p-5 bg-destructive/5 space-y-4 mt-6">
          <div className="flex items-center gap-2 border-b border-destructive/20 pb-3">
            <AlertTriangle className="h-5 w-5 text-destructive animate-pulse" />
            <h3 className="font-bold text-sm text-destructive">
              {language === "ru" ? "Danger Zone / Опасная зона" : "Danger Zone"}
            </h3>
          </div>
          
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <label className="text-xs font-bold text-foreground">
                {language === "ru" ? "Жёсткий сброс всей системы" : "Hard Reset All Data"}
              </label>
              <p className="text-[10px] leading-relaxed text-muted-foreground max-w-xl">
                {language === "ru" 
                  ? "Полностью очищает SQLite базу данных (runs, sources, artifacts), удаляет все сгенерированные черновики, DOCX/PDF отчеты, а также legacy-файлы метаданных. Это действие необратимо."
                  : "Permanently clears the SQLite database (runs, sources, artifacts), deletes all generated drafts, DOCX/PDF reports, and legacy metadata files. This action is irreversible."}
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleHardReset}
              className="shrink-0 font-bold bg-red-600 hover:bg-red-700 text-white px-4 h-9"
            >
              {language === "ru" ? "Выполнить сброс" : "Perform Reset"}
            </Button>
          </div>
        </div>

        <AlertDialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
          <AlertDialogContent className="border border-destructive/20 bg-background">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-destructive flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 animate-pulse" />
                {language === "ru" ? "Подтвердите жесткий сброс" : "Confirm Hard Reset"}
              </AlertDialogTitle>
              <AlertDialogDescription className="text-foreground/80 leading-relaxed text-xs">
                {language === "ru"
                  ? "ВНИМАНИЕ! Это действие ПОЛНОСТЬЮ удалит всю историю генераций, все загруженные файлы и очистит базу данных. Это действие НЕОБРАТИМО. Вы уверены, что хотите продолжить?"
                  : "WARNING! This action will PERMANENTLY delete all generation history, all uploaded files, and clear the database. This action is IRREVERSIBLE. Are you sure you want to proceed?"}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter className="mt-4 gap-2">
              <AlertDialogCancel className="text-xs">
                {language === "ru" ? "Отмена" : "Cancel"}
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={executeHardReset}
                className="bg-red-600 hover:bg-red-700 text-white font-bold text-xs"
              >
                {language === "ru" ? "Да, удалить всё" : "Yes, delete everything"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  )
}
