"use client"

import { AcademicLogoIcon } from "./academic-logo-icon"

interface AcademicLogoProps {
  className?: string
  compact?: boolean
}

export function AcademicLogo({ className = "", compact = false }: AcademicLogoProps) {
  if (compact) {
    return (
      <div className="flex items-center justify-center">
        <AcademicLogoIcon className="h-10 w-10 shrink-0" animate={false} />
      </div>
    )
  }

  return (
    <div className={`flex items-center gap-3 px-2 py-3 rounded-xl bg-card/40 border border-border/40 shadow-xs hover:border-ape-primary/20 transition-all duration-300 select-none ${className}`}>
      <AcademicLogoIcon className="h-12 w-12 shrink-0" animate={true} />
      
      <div className="flex flex-col leading-none justify-center">
        <div className="flex items-center gap-1.5">
          <span className="font-brand font-extrabold text-[15px] text-foreground tracking-tight">
            Academic PE
          </span>
          <span className="h-1 w-1 rounded-full bg-ape-primary animate-pulse" />
        </div>
        
        <span className="font-sans font-bold text-[9px] text-muted-foreground/80 uppercase tracking-[0.16em] mt-1.5">
          Pipeline Engine
        </span>
      </div>
    </div>
  )
}
