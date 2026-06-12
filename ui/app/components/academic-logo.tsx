"use client"

interface AcademicLogoProps {
  className?: string
  compact?: boolean
}

export function AcademicLogo({ className, compact = false }: AcademicLogoProps) {
  if (compact) {
    return (
      <svg
        aria-label="Academic PE"
        role="img"
        viewBox="0 0 72 72"
        className={className}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect className="ape-wordmark-frame" x="5" y="5" width="62" height="62" rx="12" />
        <text className="ape-wordmark-compact-title" x="36" y="37" textAnchor="middle">
          Ape
        </text>
        <line className="ape-wordmark-underline" x1="16" y1="47" x2="56" y2="47" />
      </svg>
    )
  }

  return (
    <svg
      aria-label="Academic PE Pipeline Engine"
      role="img"
      viewBox="0 0 280 92"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect className="ape-wordmark-frame" x="5" y="5" width="270" height="82" rx="10" />
      <text className="ape-wordmark-title" x="146" y="40" textAnchor="middle">
        Academic PE
      </text>
      <line className="ape-wordmark-underline" x1="36" y1="51" x2="250" y2="51" />
      <text className="ape-wordmark-subtitle" x="250" y="73" textAnchor="end">
        Pipeline Engine
      </text>
    </svg>
  )
}
