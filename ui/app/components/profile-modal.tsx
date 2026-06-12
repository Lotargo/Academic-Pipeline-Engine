"use client"

import { useRef, useState } from "react"
import type { ChangeEvent, ReactNode } from "react"
import { Camera, Moon, Sun, UserRound } from "lucide-react"
import { toast } from "sonner"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { UiLanguage } from "@/lib/i18n"

const MAX_AVATAR_BYTES = 512 * 1024
const ALLOWED_AVATAR_TYPES = ["image/png", "image/jpeg", "image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon"]

interface ProfileModalProps {
  children: ReactNode
  language: UiLanguage
  onLanguageChange: (language: UiLanguage) => Promise<void> | void
  theme?: string
  onThemeChange: (theme: string) => void
  nickname: string
  onNicknameChange: (nickname: string) => void
  avatarUrl: string | null
  onAvatarChange: (avatarUrl: string | null) => void
}

const labels = {
  en: {
    title: "Profile",
    description: "Personal workspace settings for this browser.",
    identity: "Identity",
    nickname: "Nickname",
    nicknamePlaceholder: "Academic User",
    avatar: "Avatar",
    uploadAvatar: "Upload avatar",
    removeAvatar: "Remove",
    interface: "Interface",
    language: "Language",
    theme: "Theme",
    light: "Light",
    dark: "Dark",
    system: "System",
    saved: "Profile updated",
    languageSaved: "Language updated",
    avatarTooLarge: "Avatar must be 512 KB or smaller.",
    avatarType: "Use png, jpg, ico, or svg.",
  },
  ru: {
    title: "Профиль",
    description: "Личные настройки рабочей области для этого браузера.",
    identity: "Пользователь",
    nickname: "Имя",
    nicknamePlaceholder: "Пользователь",
    avatar: "Аватар",
    uploadAvatar: "Загрузить аватар",
    removeAvatar: "Удалить",
    interface: "Интерфейс",
    language: "Язык",
    theme: "Тема",
    light: "Светлая",
    dark: "Темная",
    system: "Системная",
    saved: "Профиль обновлен",
    languageSaved: "Язык обновлен",
    avatarTooLarge: "Аватар должен быть не больше 512 КБ.",
    avatarType: "Используйте png, jpg, ico или svg.",
  },
} as const

export function ProfileModal({
  children,
  language,
  onLanguageChange,
  theme,
  onThemeChange,
  nickname,
  onNicknameChange,
  avatarUrl,
  onAvatarChange,
}: ProfileModalProps) {
  const [open, setOpen] = useState(false)
  const [savingLanguage, setSavingLanguage] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const t = labels[language]
  const displayName = nickname.trim() || t.nicknamePlaceholder
  const initials = displayName.slice(0, 2).toUpperCase()

  const handleNicknameChange = (value: string) => {
    onNicknameChange(value)
    window.localStorage.setItem("ape.profile.nickname", value)
  }

  const handleThemeChange = (value: string) => {
    onThemeChange(value)
    toast.success(t.saved)
  }

  const handleLanguageChange = async (value: string) => {
    const nextLanguage = value === "ru" ? "ru" : "en"
    setSavingLanguage(true)
    try {
      await onLanguageChange(nextLanguage)
      toast.success(t.languageSaved)
    } catch {
      // The caller owns the visible error message and any state rollback.
    } finally {
      setSavingLanguage(false)
    }
  }

  const handleAvatarInput = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return

    const isAllowedType = ALLOWED_AVATAR_TYPES.includes(file.type) || file.name.toLowerCase().endsWith(".ico")
    if (!isAllowedType) {
      toast.error(t.avatarType)
      return
    }
    if (file.size > MAX_AVATAR_BYTES) {
      toast.error(t.avatarTooLarge)
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : null
      if (!result) return
      onAvatarChange(result)
      window.localStorage.setItem("ape.profile.avatar", result)
      toast.success(t.saved)
    }
    reader.readAsDataURL(file)
  }

  const removeAvatar = () => {
    onAvatarChange(null)
    window.localStorage.removeItem("ape.profile.avatar")
    toast.success(t.saved)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t.title}</DialogTitle>
          <DialogDescription>{t.description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <section className="space-y-3">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">{t.identity}</h3>
            <div className="flex items-center gap-4">
              <Avatar className="size-14 ring-2 ring-teal-500/20">
                {avatarUrl && <AvatarImage src={avatarUrl} alt={displayName} />}
                <AvatarFallback className="bg-teal-600/10 text-teal-600 dark:text-teal-400 text-sm font-bold">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1 space-y-2">
                <Label htmlFor="profile-nickname" className="text-xs">
                  {t.nickname}
                </Label>
                <Input
                  id="profile-nickname"
                  value={nickname}
                  onChange={(event) => handleNicknameChange(event.target.value)}
                  placeholder={t.nicknamePlaceholder}
                  maxLength={48}
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".png,.jpg,.jpeg,.ico,.svg,image/png,image/jpeg,image/svg+xml,image/x-icon"
                className="hidden"
                onChange={handleAvatarInput}
              />
              <Button type="button" variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                <Camera className="h-3.5 w-3.5" />
                {t.uploadAvatar}
              </Button>
              {avatarUrl && (
                <Button type="button" variant="ghost" size="sm" onClick={removeAvatar}>
                  {t.removeAvatar}
                </Button>
              )}
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">{t.interface}</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label className="text-xs">{t.language}</Label>
                <Select value={language} onValueChange={handleLanguageChange} disabled={savingLanguage}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ru">Русский</SelectItem>
                    <SelectItem value="en">English</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs">{t.theme}</Label>
                <Select value={theme || "system"} onValueChange={handleThemeChange}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">
                      <Sun className="h-3.5 w-3.5" />
                      {t.light}
                    </SelectItem>
                    <SelectItem value="dark">
                      <Moon className="h-3.5 w-3.5" />
                      {t.dark}
                    </SelectItem>
                    <SelectItem value="system">
                      <UserRound className="h-3.5 w-3.5" />
                      {t.system}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
