"use client"

interface Win11LoaderProps {
  size?: "sm" | "md" | "lg"
  className?: string
}

export function Win11Loader({ size = "md", className = "" }: Win11LoaderProps) {
  const sizeClass = {
    sm: "win11-spinner-sm",
    md: "win11-spinner-md",
    lg: "win11-spinner-lg",
  }[size]

  return (
    <div className={`win11-spinner ${sizeClass} ${className}`} role="status" aria-label="Loading">
      <div className="win11-spinner-dot" />
      <div className="win11-spinner-dot" />
      <div className="win11-spinner-dot" />
      <div className="win11-spinner-dot" />
      <div className="win11-spinner-dot" />
    </div>
  )
}
