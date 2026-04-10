import type { CandidateResult } from '../types'
import { formatLatency } from '../utils'

const SEGMENT_COLORS = [
  'bg-cyan-400',
  'bg-emerald-400',
  'bg-amber-400',
  'bg-violet-400',
  'bg-rose-400',
]

function LatencyBar({
  totalMs,
  candidates,
}: {
  totalMs: number
  candidates: CandidateResult[]
}) {
  const okCandidates = candidates.filter((c) => c.status !== 'error' && c.latencyMs > 0)

  // Advisor mode or no candidate breakdown — just show a plain total pill
  if (!okCandidates.length) {
    return (
      <div className="flex items-center gap-2">
        <div className="h-1.5 flex-1 rounded-full bg-white/10">
          <div className="h-full w-full rounded-full bg-cyan-400/60" />
        </div>
        <span className="shrink-0 text-xs font-bold text-slate-200">{formatLatency(totalMs)}</span>
      </div>
    )
  }

  // Arena mode — show per-model segments proportional to their latency
  const maxMs = Math.max(...okCandidates.map((c) => c.latencyMs))

  return (
    <div className="space-y-1.5">
      {okCandidates.map((candidate, idx) => {
        const pct = maxMs > 0 ? Math.round((candidate.latencyMs / maxMs) * 100) : 100
        const color = SEGMENT_COLORS[idx % SEGMENT_COLORS.length]
        const shortName = candidate.modelName?.split('/').pop() ?? candidate.modelId.split('/').pop() ?? candidate.modelId
        return (
          <div key={candidate.modelId} className="flex items-center gap-2">
            <div className="h-1.5 flex-1 rounded-full bg-white/10">
              <div
                className={`h-full rounded-full ${color} opacity-70 transition-all`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-14 shrink-0 text-right text-[10px] font-semibold text-slate-400">
              {formatLatency(candidate.latencyMs)}
            </span>
            <span className="hidden sm:block w-24 shrink-0 truncate text-[10px] text-slate-500" title={shortName}>
              {shortName}
            </span>
          </div>
        )
      })}
      <div className="flex justify-end pt-0.5">
        <span className="text-[10px] font-bold text-slate-300">total {formatLatency(totalMs)}</span>
      </div>
    </div>
  )
}

export default LatencyBar
