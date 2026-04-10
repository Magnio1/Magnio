import { Radar } from 'lucide-react'
import { motion } from 'framer-motion'

import type { ChatMode } from '../types'
import { PROMPT_PRESETS } from '../prompts'

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
}

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
}

function EmptyState({
  onPreset,
}: {
  onPreset: (prompt: string, mode: ChatMode) => void
}) {
  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="flex min-h-[280px] flex-col items-center justify-center px-4 sm:px-6 py-6 sm:py-12 text-center sm:min-h-[460px]"
    >
      <motion.div variants={item} className="flex flex-col items-center">
        <div className="inline-flex items-center gap-3 rounded-full border border-amber-400/20 bg-amber-400/10 px-4 py-2 text-[10px] font-bold uppercase tracking-[0.3em] text-amber-300 shadow-[0_0_20px_rgba(251,191,36,0.05)]">
          <Radar className="h-4 w-4" />
          Magnio Engine
        </div>

        <h1 className="mt-6 sm:mt-10 max-w-4xl text-3xl sm:text-4xl lg:text-6xl font-bold leading-[1.1] tracking-tight text-white">
          Orchestrated intelligence{' '}
          <span className="bg-gradient-to-r from-cyan-300 via-sky-200 to-emerald-400 bg-clip-text text-transparent">
            at the edge.
          </span>
        </h1>

        <p className="mt-5 sm:mt-8 max-w-2xl text-base sm:text-lg lg:text-xl font-medium leading-relaxed text-slate-400">
          Compare top-ranked models or consult the grounded Magnio advisor. Pick
          a quick launch below or type your own question.
        </p>

        <div className="mt-8 sm:mt-12 w-full max-w-3xl">
          <div className="mb-6 text-[10px] font-bold uppercase tracking-[0.3em] text-slate-600">
            Quick Launch
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            {PROMPT_PRESETS.slice(0, 4).map((preset) => (
              <motion.button
                key={preset.id}
                whileHover={{ y: -2, backgroundColor: 'rgba(34, 211, 238, 0.08)' }}
                whileTap={{ scale: 0.98 }}
                type="button"
                onClick={() => onPreset(preset.prompt, preset.mode)}
                className="group inline-flex items-center gap-3 rounded-full border border-white/8 bg-white/[0.03] px-4 sm:px-6 py-3 sm:py-3.5 shadow-lg transition-all hover:border-cyan-400/30"
              >
                <div className="text-[9px] font-bold uppercase tracking-[0.2em] text-slate-500 transition-colors group-hover:text-cyan-400">
                  {preset.mode}
                </div>
                <span className="text-[15px] font-bold text-slate-200 group-hover:text-white">
                  {preset.title}
                </span>
              </motion.button>
            ))}
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default EmptyState
