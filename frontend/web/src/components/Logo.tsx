"use client";

import { cn } from "@/lib/utils";

/**
 * Логотип AI Career Copilot — gradient monogram + soft glow.
 *
 * Используется в шапке (Sidebar) и hero (login/register). Цветовая
 * палитра: #004D43 (глубокий teal) → #1A3134 (угольный бирюзовый)
 * + #CFFF71 (лаймовый accent). Высокий контраст, как венчурный фонд
 * / Web3-проект / premium SaaS.
 * SVG, не зависит от next/image.
 */
export function Logo({
  size = 32,
  className,
  withWordmark = false,
}: {
  size?: number;
  className?: string;
  withWordmark?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 64 64"
        width={size}
        height={size}
        fill="none"
        aria-hidden
      >
        <defs>
          <linearGradient id="logoBg" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#004D43" />
            <stop offset="0.5" stopColor="#1A3134" />
            <stop offset="1" stopColor="#004D43" />
          </linearGradient>
          <radialGradient id="logoGlow" cx="0.3" cy="0.3" r="0.7">
            <stop offset="0" stopColor="#CFFF71" stopOpacity="0.3" />
            <stop offset="1" stopColor="#CFFF71" stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx="32" cy="32" r="30" fill="url(#logoBg)" />
        <circle cx="32" cy="32" r="30" fill="url(#logoGlow)" />
        <text
          x="32"
          y="40"
          fontFamily="ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
          fontSize="22"
          fontWeight="600"
          textAnchor="middle"
          fill="#CFFF71"
          letterSpacing="-1.5"
        >
          AC
        </text>
      </svg>
      {withWordmark && (
        <span className="font-semibold tracking-tight">AI Career Copilot</span>
      )}
    </span>
  );
}
