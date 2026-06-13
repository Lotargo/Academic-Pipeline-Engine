'use client'

import { useTheme } from 'next-themes'
import { Toaster as Sonner, ToasterProps } from 'sonner'

function ApeToastIcon({ tone }: { tone: 'success' | 'info' | 'warning' | 'error' }) {
  return (
    <svg className={`ape-toast-icon ape-toast-icon-${tone}`} viewBox="0 0 34 34" aria-hidden="true">
      <path className="ape-toast-icon-shadow" d="M4 17 11 5h13l6 12-7 12H10L4 17Z" />
      <path className="ape-toast-icon-shell" d="M5.5 17 11.8 6.5h10.9L28.5 17l-6.3 10.5H11.3L5.5 17Z" />
      <path className="ape-toast-icon-core" d="M10 17 14 10h7l4 7-4 7h-7l-4-7Z" />
      <path className="ape-toast-icon-cut ape-toast-icon-cut-a" d="M6 17h6" />
      <path className="ape-toast-icon-cut ape-toast-icon-cut-b" d="M22 17h6" />
      <path className="ape-toast-icon-mark" d={tone === 'error' ? 'M14 14l6 6m0-6-6 6' : tone === 'warning' ? 'M17 12v7m0 4h.1' : 'm13.5 17 2.4 2.4 5-5.2'} />
    </svg>
  )
}

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = 'system' } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps['theme']}
      position="top-right"
      offset={{ top: 76, right: 24 }}
      mobileOffset={{ top: 72, right: 16, left: 16 }}
      richColors={false}
      visibleToasts={4}
      gap={10}
      duration={3600}
      swipeDirections={['right']}
      className="ape-toaster group"
      icons={{
        success: <ApeToastIcon tone="success" />,
        info: <ApeToastIcon tone="info" />,
        warning: <ApeToastIcon tone="warning" />,
        error: <ApeToastIcon tone="error" />,
      }}
      toastOptions={{
        classNames: {
          toast: 'ape-toast',
          title: 'ape-toast-title',
          description: 'ape-toast-description',
          icon: 'ape-toast-icon-wrap',
          content: 'ape-toast-content',
        },
      }}
      style={
        {
          '--normal-bg': 'var(--popover)',
          '--normal-text': 'var(--popover-foreground)',
          '--normal-border': 'var(--border)',
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
