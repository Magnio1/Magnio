import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  BrainCircuit,
  Check,
  Loader2,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
  Telescope,
} from 'lucide-react'

import type { ChatMode } from '../types'

type Step = {
  label: string
  icon: typeof Loader2
  delay: number
}

const ARENA_STEPS: Step[] = [
  { label: 'Classifying query', icon: BrainCircuit, delay: 0 },
  { label: 'Running 3 models in parallel', icon: Radar, delay: 1800 },
  { label: 'Scoring candidates', icon: ShieldCheck, delay: 7000 },
  { label: 'Synthesizing final answer', icon: Sparkles, delay: 10000 },
]

const ADVISOR_STEPS: Step[] = [
  { label: 'Searching knowledge base', icon: Search, delay: 0 },
  { label: 'Generating grounded answer', icon: Telescope, delay: 2000 },
]

const AUTO_STEPS: Step[] = [
  { label: 'Routing to best pipeline', icon: BrainCircuit, delay: 0 },
  { label: 'Running models', icon: Radar, delay: 2000 },
  { label: 'Synthesizing answer', icon: Sparkles, delay: 7000 },
]

function LoadingIndicator({ mode }: { mode: ChatMode }) {
  const [activeStep, setActiveStep] = useState(0)
  const steps =
    mode === 'arena' ? ARENA_STEPS : mode === 'advisor' ? ADVISOR_STEPS : AUTO_STEPS

  useEffect(() => {
    setActiveStep(0)
    const timers: number[] = []
    steps.forEach((step, index) => {
      if (index > 0) {
        timers.push(window.setTimeout(() => setActiveStep(index), step.delay))
      }
    })
    return () => timers.forEach(clearTimeout)
  }, [mode, steps])

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-[28px] border border-white/5 bg-white/[0.02] px-6 py-5 backdrop-blur-sm"
      role="status"
      aria-live="polite"
      aria-label="Processing query"
    >
      <div className="space-y-3">
        {steps.map((step, index) => {
          const isActive = index === activeStep
          const isComplete = index < activeStep
          const isPending = index > activeStep
          const Icon = step.icon

          return (
            <motion.div
              key={step.label}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: isPending ? 0.3 : 1, x: 0 }}
              transition={{ delay: 0.05 * index }}
              className="flex items-center gap-3"
            >
              {isActive ? (
                <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-cyan-400" />
              ) : isComplete ? (
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
              ) : (
                <Icon className="h-3.5 w-3.5 shrink-0 text-slate-600" />
              )}
              <span
                className={`text-[11px] font-bold uppercase tracking-[0.18em] ${
                  isActive
                    ? 'text-cyan-300'
                    : isComplete
                      ? 'text-slate-400'
                      : 'text-slate-600'
                }`}
              >
                {step.label}
              </span>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

export default LoadingIndicator
