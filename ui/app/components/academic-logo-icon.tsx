"use client"

interface AcademicLogoIconProps {
  className?: string
  animate?: boolean
}

export function AcademicLogoIcon({ className = "h-14 w-14", animate = true }: AcademicLogoIconProps) {
  return (
    <svg
      viewBox="0 0 120 120"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Academic Pipeline Engine Logo"
    >
      <defs>
        {/* Main Brand Gradient */}
        <linearGradient id="ape-cap-grad" x1="10" y1="14" x2="90" y2="58" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--ape-primary)" />
          <stop offset="50%" stopColor="oklch(0.58 0.045 82)" />
          <stop offset="100%" stopColor="var(--ape-primary-text)" />
        </linearGradient>

        {/* Soft Gold/Bronze Gradient for lines and details */}
        <linearGradient id="ape-line-grad" x1="10" y1="35" x2="90" y2="35" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--ape-primary)" stopOpacity="0.4" />
          <stop offset="50%" stopColor="var(--ape-primary)" stopOpacity="1" />
          <stop offset="100%" stopColor="var(--ape-primary)" stopOpacity="0.4" />
        </linearGradient>

        {/* Glassmorphic Inner Shield/Diamond Gradient */}
        <linearGradient id="ape-inner-grad" x1="50" y1="20" x2="50" y2="50" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--card)" stopOpacity="0.15" />
          <stop offset="100%" stopColor="var(--card)" stopOpacity="0.7" />
        </linearGradient>

        {/* Glowing Filter for nodes */}
        <filter id="ape-glow-filter" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {animate && (
        <style dangerouslySetInnerHTML={{ __html: `
          @keyframes ape-pulse-node {
            0%, 100% {
              transform: scale(1);
              opacity: 0.9;
              filter: drop-shadow(0 0 2px var(--ape-primary));
            }
            50% {
              transform: scale(1.25);
              opacity: 1;
              filter: drop-shadow(0 0 6px var(--ape-primary));
            }
          }
          @keyframes ape-line-flow {
            to {
              stroke-dashoffset: -18;
            }
          }
          @keyframes ape-float {
            0%, 100% {
              transform: translateY(0px);
            }
            50% {
              transform: translateY(-2px);
            }
          }
          .ape-animate-float {
            animation: ape-float 6s ease-in-out infinite;
          }
          .ape-animate-node-1 {
            animation: ape-pulse-node 3.5s ease-in-out infinite;
            transform-origin: 60px 35px;
          }
          .ape-animate-node-2 {
            animation: ape-pulse-node 3.5s ease-in-out infinite;
            animation-delay: 1.1s;
            transform-origin: 41px 26px;
          }
          .ape-animate-node-3 {
            animation: ape-pulse-node 3.5s ease-in-out infinite;
            animation-delay: 2.2s;
            transform-origin: 79px 44px;
          }
          .ape-animate-line {
            stroke-dasharray: 6 3;
            animation: ape-line-flow 15s linear infinite;
          }
        `}} />
      )}

      {/* Floating Wrapper for Logo */}
      <g className="ape-animate-float">
        {/* Academic Pages/Book stack (Under cap base) */}
        {/* Page 3 (Deepest) */}
        <path
          d="M 38 52 C 38 67, 82 67, 82 52"
          stroke="url(#ape-cap-grad)"
          strokeWidth="1.5"
          strokeLinecap="round"
          opacity="0.3"
        />
        {/* Page 2 */}
        <path
          d="M 34 48 C 34 63, 86 63, 86 48"
          stroke="url(#ape-cap-grad)"
          strokeWidth="2"
          strokeLinecap="round"
          opacity="0.6"
        />
        {/* Page 1 (Main page/arch base) */}
        <path
          d="M 30 44 C 30 59, 90 59, 90 44 L 86 42.5 C 86 54.5, 34 54.5, 34 42.5 Z"
          fill="url(#ape-cap-grad)"
          opacity="0.9"
        />

        {/* The Mortarboard Diamond (Cap Top) */}
        {/* Background shadow path */}
        <path
          d="M 60 14 C 62 14, 103 33, 105 35 C 107 37, 107 39, 105 41 C 103 43, 62 62, 60 62 C 58 62, 17 43, 15 41 C 13 39, 13 37, 15 35 C 17 33, 58 14, 60 14 Z"
          fill="url(#ape-cap-grad)"
          opacity="0.95"
        />

        {/* Inner Glassmorphic Overlay for depth */}
        <path
          d="M 60 19 L 98 38 L 60 57 L 22 38 Z"
          fill="url(#ape-inner-grad)"
          stroke="var(--background)"
          strokeWidth="0.75"
          opacity="0.85"
        />

        {/* Pipeline tracks (Helix lines passing through the cap) */}
        {/* Track 1: Curved S-flow from left to right */}
        <path
          d="M 22 38 C 40 28, 80 48, 98 38"
          stroke="url(#ape-line-grad)"
          strokeWidth="1.5"
          strokeLinecap="round"
          className="ape-animate-line"
        />

        {/* Track 2: Complementary flow from top-left to bottom-right */}
        <path
          d="M 41 26 C 50 35, 70 35, 79 44"
          stroke="url(#ape-line-grad)"
          strokeWidth="1"
          strokeLinecap="round"
          opacity="0.8"
        />

        {/* Cooperative AI Agent Nodes (Pulsing circles at intersections) */}
        {/* Left Node */}
        <circle
          cx="41"
          cy="26"
          r="3"
          fill="var(--background)"
          stroke="var(--ape-primary)"
          strokeWidth="2.5"
          className="ape-animate-node-2"
        />

        {/* Right Node */}
        <circle
          cx="79"
          cy="44"
          r="3"
          fill="var(--background)"
          stroke="var(--ape-primary)"
          strokeWidth="2.5"
          className="ape-animate-node-3"
        />

        {/* Central Intelligence Node */}
        <circle
          cx="60"
          cy="35"
          r="4.5"
          fill="var(--background)"
          stroke="var(--ape-primary)"
          strokeWidth="3.5"
          className="ape-animate-node-1"
        />

        {/* Tassel (Connecting data stream from mortarboard corner) */}
        {/* Tassel string */}
        <path
          d="M 105 38 C 111 41, 113 49, 113 62"
          stroke="url(#ape-cap-grad)"
          strokeWidth="1.8"
          strokeLinecap="round"
          opacity="0.85"
        />

        {/* Tassel connection joint node */}
        <circle
          cx="113"
          cy="62"
          r="2"
          fill="var(--ape-primary-text)"
        />

        {/* Tassel Ending: Dynamic 4-Pointed Sparkle Agent */}
        <path
          d="M 113 65 Q 113 72, 120 72 Q 113 72, 113 79 Q 113 72, 106 72 Q 113 72, 113 65 Z"
          fill="url(#ape-cap-grad)"
          filter="url(#ape-glow-filter)"
        />
      </g>
    </svg>
  )
}
