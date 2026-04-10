import { Loader2, MessageSquareText } from 'lucide-react'

import type { RecentEvaluationCase } from '../types'
import { formatLatency } from '../utils'

function ReviewQueueSection({
  cases,
  error,
  loading,
  onLoadCase,
  compact = false,
}: {
  cases: RecentEvaluationCase[]
  error: string
  loading: boolean
  onLoadCase: (item: RecentEvaluationCase) => void
  compact?: boolean
}) {
  const items = compact ? cases.slice(0, 4) : cases.slice(0, 6)

  return (
    <section className="panel-card">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <MessageSquareText className="h-4.5 w-4.5 text-cyan-300" />
          <h2 className="text-base font-semibold text-white">Review Queue</h2>
        </div>
        <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
          {cases.filter((item) => item.review?.vote === 'down').length} revise
        </div>
      </div>

      {error ? (
        <p className="mt-5 text-sm font-medium leading-6 text-rose-300/80" role="alert">
          {error}
        </p>
      ) : loading ? (
        <div className="mt-5 flex items-center gap-3 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading recent cases...
        </div>
      ) : items.length ? (
        <div className="mt-4 space-y-2.5">
          {items.map((item) => {
            const needsRevision = item.review?.vote === 'down'
            const approved = item.review?.vote === 'up'
            const modeLabel = (
              item.resolvedMode ||
              item.requestedMode ||
              'auto'
            ).toUpperCase()
            return (
              <div
                key={item.runId}
                className="rounded-2xl border border-white/6 bg-black/20 px-4 py-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                        {modeLabel}
                      </span>
                      {item.topicLabel ? (
                        <span className="rounded-full border border-white/8 bg-white/[0.03] px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-500">
                          {item.topicLabel}
                        </span>
                      ) : null}
                      {needsRevision ? (
                        <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.16em] text-amber-200">
                          Needs revision
                        </span>
                      ) : approved ? (
                        <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.16em] text-emerald-200">
                          Approved
                        </span>
                      ) : (
                        <span className="rounded-full border border-white/8 bg-white/[0.03] px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-500">
                          Pending
                        </span>
                      )}
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm font-medium leading-6 text-slate-200">
                      {item.queryPreview}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] font-medium text-slate-500">
                      {item.createdAt ? <span>{item.createdAt}</span> : null}
                      {typeof item.latencyMs === 'number' ? (
                        <span>{formatLatency(item.latencyMs)}</span>
                      ) : null}
                      {item.review?.note ? (
                        <span className="line-clamp-1">Review note saved</span>
                      ) : null}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onLoadCase(item)}
                    className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-200 transition hover:bg-white/[0.08]"
                  >
                    Load case
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="mt-5 rounded-2xl border border-dashed border-white/10 px-4 py-6 text-sm text-slate-500">
          No recent cases yet.
        </div>
      )}
    </section>
  )
}

export default ReviewQueueSection
