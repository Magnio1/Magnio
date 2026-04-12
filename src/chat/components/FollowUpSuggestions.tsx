import { Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

import { getMagnioFollowUpSuggestions } from '../api'
import type { ChatMode } from '../types'

function FollowUpSuggestions({
  answer,
  topicLabel,
  mode,
  onSelect,
}: {
  answer: string
  topicLabel: string
  mode: ChatMode
  onSelect: (suggestion: string) => void
}) {
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setSuggestions([])

    getMagnioFollowUpSuggestions(answer, topicLabel, mode)
      .then((results) => {
        if (!cancelled) {
          setSuggestions(results)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [answer, topicLabel, mode])

  if (!loading && !suggestions.length) return null

  return (
    <div className="mt-4 space-y-2">
      <div className="flex items-center gap-2">
        <Sparkles className="h-3.5 w-3.5 text-violet-400" />
        <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500">
          Follow-up
        </span>
      </div>

      <AnimatePresence>
        {loading ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex gap-2"
          >
            {[100, 140, 120].map((w) => (
              <div
                key={w}
                className="h-7 animate-pulse rounded-full border border-white/5 bg-white/[0.04]"
                style={{ width: w }}
              />
            ))}
          </motion.div>
        ) : (
          <motion.div
            key="chips"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap gap-2"
          >
            {suggestions.map((s, i) => (
              <motion.button
                key={i}
                type="button"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.06 }}
                onClick={() => onSelect(s)}
                className="max-w-[280px] rounded-full border border-violet-400/20 bg-violet-400/10 px-3 py-1.5 text-left text-xs font-medium text-violet-200 transition hover:border-violet-400/40 hover:bg-violet-400/20 hover:text-white"
              >
                {s}
              </motion.button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default FollowUpSuggestions
