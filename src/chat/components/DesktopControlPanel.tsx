import { Activity, BarChart3, Loader2, Search, Telescope } from 'lucide-react'
import { useEffect, useState } from 'react'

import { getMagnioModelTrends } from '../api'
import { MODE_OPTIONS } from '../constants'
import { PROMPT_PRESETS } from '../prompts'
import type {
  ChatAnalyticsSummary,
  ChatHealth,
  ChatMode,
  ModelTrendPoint,
  PromptPreset,
  SavedConversation,
} from '../types'
import { formatRate } from '../utils'
import ConversationHistory from './ConversationHistory'
import ModelTrendChart from './ModelTrendChart'
import { ModeButton } from './ModeControls'

function DesktopControlPanel({
  mode,
  onModeChange,
  health,
  healthError,
  analyticsSummary,
  analyticsError,
  promptSearch,
  onPromptSearchChange,
  filteredPresets,
  onPreset,
  sessions,
  currentSessionId,
  onLoadSession,
  onDeleteSession,
  onNewSession,
}: {
  mode: ChatMode
  onModeChange: (mode: ChatMode) => void
  health: ChatHealth | null
  healthError: string
  analyticsSummary: ChatAnalyticsSummary | null
  analyticsError: string
  promptSearch: string
  onPromptSearchChange: (value: string) => void
  filteredPresets: PromptPreset[]
  onPreset: (prompt: string, mode: ChatMode) => void
  sessions: SavedConversation[]
  currentSessionId: string
  onLoadSession: (session: SavedConversation) => void
  onDeleteSession: (id: string) => void
  onNewSession: () => void
}) {
  const [trends, setTrends] = useState<ModelTrendPoint[]>([])

  useEffect(() => {
    getMagnioModelTrends(30)
      .then(setTrends)
      .catch(() => { /* silent — trend chart is best-effort */ })
  }, [])

  return (
    <div className="space-y-5">
      <section className="panel-card">
        <div className="flex items-center gap-2.5">
          <Telescope className="h-4.5 w-4.5 text-cyan-300" />
          <h2 className="text-base font-semibold text-white">Mode</h2>
        </div>
        <div className="mt-4 space-y-2" role="radiogroup" aria-label="Magnio chat mode">
          {MODE_OPTIONS.map((option) => (
            <ModeButton
              key={option.value}
              active={mode === option.value}
              label={option.label}
              onClick={() => onModeChange(option.value)}
            />
          ))}
        </div>
      </section>

      <section className="panel-card bg-black/20">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Activity className="h-4.5 w-4.5 text-emerald-400" />
            <h2 className="text-base font-semibold text-white">System Health</h2>
          </div>
          {health?.ok ? (
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
          ) : null}
        </div>
        {health ? (
          <div className="mt-5 grid grid-cols-2 gap-2.5">
            {[
              ['OpenRouter', health.openrouterConfigured ? 'Connected' : 'Missing Key', health.openrouterConfigured],
              ['Judge', health.judgeModelId, true],
              ['Advisor', health.advisorModelId, true],
              ['Knowledge', `${health.knowledgeChunkCount} nodes`, health.knowledgeChunkCount > 0],
            ].map(([label, value, ok]) => (
              <div key={label as string} className="rounded-2xl border border-white/5 bg-white/[0.03] px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
                  {label as string}
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs font-medium text-slate-200">
                  <span className={`h-1.5 w-1.5 rounded-full ${ok ? 'bg-emerald-500/70' : 'bg-rose-500/70'}`} />
                  {value as string}
                </div>
              </div>
            ))}
          </div>
        ) : healthError ? (
          <p className="mt-5 text-sm font-medium leading-6 text-rose-300/80" role="alert">
            {healthError}
          </p>
        ) : (
          <div className="mt-5 flex items-center gap-3 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Syncing engine...
          </div>
        )}
      </section>

      <section className="panel-card">
        <div className="flex items-center gap-2.5">
          <BarChart3 className="h-4.5 w-4.5 text-cyan-300" />
          <h2 className="text-base font-semibold text-white">Review Signals</h2>
        </div>
        {analyticsSummary ? (
          <>
            <div className="mt-5 grid grid-cols-2 gap-2.5">
              {[
                ['Runs', String(analyticsSummary.totalRuns)],
                ['Reviews', String(analyticsSummary.feedbackCount)],
                ['Arena', String(analyticsSummary.arenaRuns)],
                ['Advisor', String(analyticsSummary.advisorRuns)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-white/5 bg-black/25 px-3 py-3">
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
                    {label}
                  </div>
                  <div className="mt-1 text-xs font-semibold text-slate-100">{value}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 rounded-2xl border border-white/5 bg-black/25 px-3 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
                    Approval rate
                  </div>
                  <div className="mt-1 text-xs font-semibold text-slate-100">
                    {formatRate(analyticsSummary.upvotes, analyticsSummary.feedbackCount)}
                  </div>
                </div>
                <div className="text-right text-xs font-medium text-slate-400">
                  <div>{analyticsSummary.upvotes} approved</div>
                  <div>{analyticsSummary.downvotes} revise</div>
                </div>
              </div>
            </div>

            {trends.length > 0 && (
              <div className="mt-3 rounded-2xl border border-white/5 bg-black/25 px-3 py-3">
                <div className="mb-3 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
                  Arena win trend
                </div>
                <ModelTrendChart trends={trends} />
              </div>
            )}
          </>
        ) : analyticsError ? (
          <p className="mt-5 text-sm font-medium leading-6 text-rose-300/80" role="alert">
            {analyticsError}
          </p>
        ) : (
          <div className="mt-5 flex items-center gap-3 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading analytics...
          </div>
        )}
      </section>

      <section className="panel-card">
        <div className="flex items-center gap-2.5">
          <Search className="h-4.5 w-4.5 text-amber-300" />
          <h2 className="text-base font-semibold text-white">Prompts</h2>
        </div>
        <div className="relative mt-5">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <label className="sr-only" htmlFor="desktop-prompt-library-filter">
            Filter prompt library
          </label>
          <input
            id="desktop-prompt-library-filter"
            value={promptSearch}
            onChange={(event) => onPromptSearchChange(event.target.value)}
            placeholder="Filter library..."
            aria-label="Filter prompt library"
            className="w-full rounded-xl border border-white/10 bg-black/20 py-3 pl-11 pr-4 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-400/40 focus:ring-1 focus:ring-cyan-400/20"
          />
        </div>
        <div className="mt-4 max-h-[232px] space-y-2 overflow-y-auto pr-1 custom-scrollbar">
          {filteredPresets.slice(0, 4).map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => onPreset(preset.prompt, preset.mode)}
              className="group w-full rounded-xl border border-white/5 bg-black/15 px-4 py-3 text-left transition hover:border-white/15 hover:bg-black/30"
            >
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 transition-colors group-hover:text-cyan-400/70">
                {preset.mode}
              </div>
              <div className="mt-1 text-xs font-semibold text-slate-200 transition-colors group-hover:text-white">
                {preset.title}
              </div>
            </button>
          ))}
          {!filteredPresets.length ? (
            <div className="rounded-2xl border border-dashed border-white/10 px-4 py-6 text-center text-sm text-slate-500">
              No prompts found in {PROMPT_PRESETS.length} presets.
            </div>
          ) : null}
        </div>
      </section>

      <section className="panel-card">
        <ConversationHistory
          sessions={sessions}
          currentSessionId={currentSessionId}
          onLoad={onLoadSession}
          onDelete={onDeleteSession}
          onNew={onNewSession}
        />
      </section>
    </div>
  )
}

export default DesktopControlPanel
