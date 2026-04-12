import { Activity } from 'lucide-react'
import { motion } from 'framer-motion'

import type { CandidateResult, JudgeScore } from '../types'
import { formatLatency } from '../utils'
import MarkdownSurface from '../MarkdownSurface'

const METRIC_LABELS: Array<{
  key: keyof JudgeScore
  short: string
  full: string
}> = [
  { key: 'usefulness', short: 'Useful', full: 'Usefulness' },
  { key: 'groundedness', short: 'Grounded', full: 'Groundedness' },
  { key: 'clarity', short: 'Clear', full: 'Clarity' },
  { key: 'decisiveness', short: 'Decisive', full: 'Decisiveness' },
]

function CandidateCard({
  candidate,
  winnerModelId,
  score,
  index,
}: {
  candidate: CandidateResult
  winnerModelId?: string
  score?: JudgeScore
  index: number
}) {
  const isWinner = winnerModelId === candidate.modelId
  const totalScore =
    score?.total ??
    [score?.usefulness, score?.groundedness, score?.clarity, score?.decisiveness].reduce<number>(
      (sum, value) => sum + (typeof value === 'number' ? value : 0),
      0,
    )

  return (
    <motion.article
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 * index }}
      className={`flex flex-col overflow-hidden rounded-[24px] border transition-all ${
        isWinner
          ? 'border-emerald-400/30 bg-emerald-400/[0.04] shadow-lg'
          : 'border-white/6 bg-white/[0.02] hover:bg-white/[0.04]'
      }`}
    >
      <header className="flex flex-col gap-4 p-4 sm:gap-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-white/10 bg-black/40 px-2.5 py-1 text-[8px] font-bold uppercase tracking-[0.16em] text-slate-400">
              {candidate.provider}
            </span>
            {isWinner ? (
              <span className="rounded-full border border-emerald-400/20 bg-emerald-400/20 px-2.5 py-1 text-[8px] font-bold uppercase tracking-[0.16em] text-emerald-300">
                winner
              </span>
            ) : null}
          </div>
          <div className="inline-flex items-center gap-1.5 rounded-full border border-white/5 bg-black/30 px-3 py-1 text-[9px] font-bold text-slate-400">
            <Activity className="h-2.5 w-2.5 text-cyan-400/50" />
            {formatLatency(candidate.latencyMs)}
          </div>
        </div>

        <div>
          <h4 className="text-[18px] font-bold leading-tight tracking-tight text-white transition-colors sm:text-[20px]">
            {candidate.modelName}
          </h4>
          <div className="mt-2 truncate text-[8px] font-medium uppercase tracking-[0.08em] text-slate-500 opacity-60">
            {candidate.modelId}
          </div>
        </div>

        {score ? (
          <div className="inline-flex items-center gap-3 self-start rounded-full border border-white/5 bg-white/[0.03] py-1.5 pl-3.5 pr-2.5">
            <span className="text-[8px] font-bold uppercase tracking-[0.2em] text-slate-500">
              Score
            </span>
            <span className="text-sm font-bold text-white">{totalScore}</span>
            <span className="text-[9px] font-medium text-slate-600">/ 40</span>
          </div>
        ) : null}
      </header>

      {candidate.status === 'error' ? (
        <div className="p-5 pt-0">
          <div className="rounded-xl border border-rose-500/15 bg-rose-500/5 px-4 py-3 text-xs font-medium leading-relaxed text-rose-200/80">
            {candidate.error ?? 'Call failed.'}
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4 p-4 pt-0 sm:gap-5 sm:p-6 sm:pt-0">
          {score ? (
            <div className="grid grid-cols-2 gap-2">
              {METRIC_LABELS.map(({ key, short, full }) => {
                const value = score[key] as number | undefined
                return (
                  <div
                    key={`${candidate.modelId}-${key}`}
                    title={full}
                    className="group/metric rounded-[20px] border border-white/5 bg-black/20 p-3.5 transition-colors hover:bg-black/30"
                  >
                    <div className="text-[8px] font-bold uppercase tracking-[0.14em] text-slate-500 transition-colors">
                      {short}
                    </div>
                    <div className="mt-2.5 flex items-baseline gap-1">
                      <div className="text-[20px] font-bold leading-none tracking-tight text-white transition-colors group-hover/metric:text-cyan-200">
                        {value ?? '--'}
                      </div>
                      <div className="text-[9px] font-bold text-slate-700">/10</div>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : null}

          {score?.notes ? (
            <div className="rounded-[20px] border border-white/5 bg-black/20 p-4">
              <div className="mb-2 text-[9px] font-bold uppercase tracking-[0.15em] text-cyan-400/50">
                Evaluation note
              </div>
              <p className="whitespace-pre-line text-[12px] font-medium leading-6 text-slate-400">
                {score.notes}
              </p>
            </div>
          ) : null}

          <details className="group/details">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-full border border-white/5 bg-black/15 px-4 py-3 text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500 transition-all hover:bg-black/25">
              <span>Full perspective</span>
              <div className="h-px flex-1 bg-white/5" />
            </summary>
            <div className="mt-3 overflow-hidden rounded-[20px] border border-white/5 bg-black/15 p-5">
              <MarkdownSurface content={candidate.content} />
            </div>
          </details>
        </div>
      )}
    </motion.article>
  )
}

export default CandidateCard
