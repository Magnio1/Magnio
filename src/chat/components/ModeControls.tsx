import { Bot, Radar, Telescope } from 'lucide-react'
import { motion } from 'framer-motion'

import type { ChatMode } from '../types'
import type { ModeOption } from '../constants'

export function ModeGlyph({
  mode,
  className = 'h-4 w-4',
}: {
  mode: ChatMode
  className?: string
}) {
  if (mode === 'arena') return <Radar className={className} />
  if (mode === 'advisor') return <Telescope className={className} />
  return <Bot className={className} />
}

export function ModeButton({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`w-full rounded-xl border px-3.5 py-3.5 text-left transition-all ${
        active
          ? 'border-cyan-300/60 bg-cyan-300/10 shadow-[0_0_20px_rgba(165,243,252,0.08)]'
          : 'border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/[0.08]'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-200">
          {label}
        </div>
        {active ? (
          <motion.span
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-full border border-cyan-200/30 bg-cyan-200/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-100"
          >
            selected
          </motion.span>
        ) : null}
      </div>
    </motion.button>
  )
}

export function ComposerModeButton({
  option,
  active,
  onClick,
}: {
  option: ModeOption
  active: boolean
  onClick: () => void
}) {
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`group inline-flex items-center gap-2 rounded-full border px-3.5 py-2.5 transition-all ${
        active
          ? 'border-cyan-400/40 bg-white/[0.12] text-white shadow-[0_0_20px_rgba(34,211,238,0.1)] backdrop-blur-md'
          : 'border-white/10 bg-white/[0.04] text-slate-400 hover:border-white/20 hover:bg-white/[0.08] hover:text-white'
      }`}
    >
      <span
        className={`flex h-6 w-6 items-center justify-center rounded-full ${
          active
            ? 'bg-cyan-400/12 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.45),inset_0_0_0_1px_rgba(103,232,249,0.22)]'
            : 'bg-white/[0.05] text-slate-300'
        }`}
      >
        <ModeGlyph mode={option.value} className="h-3 w-3" />
      </span>
      <span className="text-[10px] font-bold uppercase tracking-[0.22em]">
        {option.label}
      </span>
    </motion.button>
  )
}
