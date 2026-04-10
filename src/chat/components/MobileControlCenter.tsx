import { Activity, ChevronDown, Loader2, Search } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

import type {
  ChatAnalyticsSummary,
  ChatHealth,
  ChatMode,
  PromptPreset,
  RecentEvaluationCase,
  SavedConversation,
} from '../types'
import ConversationHistory from './ConversationHistory'
import ReviewQueueSection from './ReviewQueueSection'

function MobileControlCenter({
  open,
  onToggle,
  health,
  healthError,
  analyticsSummary,
  analyticsError,
  recentCases,
  recentCasesError,
  recentCasesLoading,
  promptSearch,
  onPromptSearchChange,
  quickPresets,
  filteredPresets,
  onPreset,
  onLoadCase,
  sessions,
  currentSessionId,
  onLoadSession,
  onDeleteSession,
  onNewSession,
}: {
  open: boolean
  onToggle: () => void
  health: ChatHealth | null
  healthError: string
  analyticsSummary: ChatAnalyticsSummary | null
  analyticsError: string
  recentCases: RecentEvaluationCase[]
  recentCasesError: string
  recentCasesLoading: boolean
  promptSearch: string
  onPromptSearchChange: (value: string) => void
  quickPresets: PromptPreset[]
  filteredPresets: PromptPreset[]
  onPreset: (prompt: string, mode: ChatMode) => void
  onLoadCase: (item: RecentEvaluationCase) => void
  sessions: SavedConversation[]
  currentSessionId: string
  onLoadSession: (session: SavedConversation) => void
  onDeleteSession: (id: string) => void
  onNewSession: () => void
}) {
  const panelId = 'mobile-control-center-panel'

  return (
    <div className="xl:hidden overflow-hidden rounded-[28px] border border-white/10 bg-black/35 backdrop-blur-xl">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-3 px-4 py-4 text-left"
      >
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-cyan-300/70">
            Control Center
          </div>
          <div className="mt-1 text-sm font-semibold text-white">
            System, analytics, and quick prompts
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${
              health?.openrouterConfigured
                ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200'
                : 'border-amber-300/20 bg-amber-300/10 text-amber-100'
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                health?.openrouterConfigured ? 'bg-emerald-300' : 'bg-amber-300'
              }`}
            />
            {health?.openrouterConfigured ? 'Live' : 'Check'}
          </span>
          <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
            <ChevronDown className="h-4 w-4 text-slate-400" />
          </motion.span>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={panelId}
            key="mobile-control-center"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="overflow-hidden border-t border-white/6"
          >
            <div className="px-4 pb-4 pt-3">
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-2xl border border-white/6 bg-white/[0.03] px-3 py-3">
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                    Runs
                  </div>
                  <div className="mt-1 text-sm font-semibold text-white">
                    {analyticsSummary ? analyticsSummary.totalRuns : '--'}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/6 bg-white/[0.03] px-3 py-3">
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                    Arena
                  </div>
                  <div className="mt-1 text-sm font-semibold text-white">
                    {analyticsSummary ? analyticsSummary.arenaRuns : '--'}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/6 bg-white/[0.03] px-3 py-3">
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                    Advisor
                  </div>
                  <div className="mt-1 text-sm font-semibold text-white">
                    {analyticsSummary ? analyticsSummary.advisorRuns : '--'}
                  </div>
                </div>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-2xl border border-white/6 bg-black/25 px-3 py-3">
                  <div className="flex items-center gap-2">
                    <Activity className="h-3.5 w-3.5 text-emerald-400" />
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                      Judge
                    </div>
                  </div>
                  <div className="mt-1 text-xs font-medium text-slate-200">
                    {health?.judgeModelId || healthError || 'Syncing...'}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/6 bg-black/25 px-3 py-3">
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                    Knowledge
                  </div>
                  <div className="mt-1 text-xs font-medium text-slate-200">
                    {health ? `${health.knowledgeChunkCount} nodes` : analyticsError || 'Loading...'}
                  </div>
                </div>
              </div>

              {!analyticsSummary && !health && (analyticsError || healthError) ? (
                <div
                  className="mt-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200"
                  role="alert"
                >
                  {analyticsError || healthError}
                </div>
              ) : null}

              {!analyticsSummary && !analyticsError ? (
                <div className="mt-3 flex items-center gap-3 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading analytics...
                </div>
              ) : null}

              <div className="mt-4">
                <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500">
                  Quick Launch
                </div>
                <div className="mt-3 flex gap-2 overflow-x-auto pb-1 custom-scrollbar">
                  {quickPresets.map((preset) => (
                    <button
                      key={`mobile-preset-${preset.id}`}
                      type="button"
                      onClick={() => onPreset(preset.prompt, preset.mode)}
                      className="min-w-[150px] shrink-0 rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-left"
                    >
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                        {preset.mode}
                      </div>
                      <div className="mt-1 text-sm font-semibold text-white">{preset.title}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="relative mt-4">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <label className="sr-only" htmlFor="mobile-prompt-library-filter">
                  Filter prompt library
                </label>
                <input
                  id="mobile-prompt-library-filter"
                  value={promptSearch}
                  onChange={(event) => onPromptSearchChange(event.target.value)}
                  placeholder="Filter prompt library..."
                  aria-label="Filter prompt library"
                  className="w-full rounded-2xl border border-white/10 bg-black/35 py-3 pl-11 pr-4 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-400/40 focus:ring-1 focus:ring-cyan-400/20"
                />
              </div>

              <div className="mt-3 max-h-[220px] space-y-2 overflow-y-auto pr-1 custom-scrollbar">
                {filteredPresets.slice(0, 6).map((preset) => (
                  <button
                    key={`mobile-library-${preset.id}`}
                    type="button"
                    onClick={() => onPreset(preset.prompt, preset.mode)}
                    className="w-full rounded-2xl border border-white/6 bg-black/20 px-4 py-3 text-left"
                  >
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                      {preset.mode}
                    </div>
                    <div className="mt-1 text-sm font-semibold text-slate-100">{preset.title}</div>
                  </button>
                ))}
              </div>

              <div className="mt-4">
                <ReviewQueueSection
                  cases={recentCases}
                  error={recentCasesError}
                  loading={recentCasesLoading}
                  onLoadCase={onLoadCase}
                  compact
                />
              </div>

              <div className="mt-4 rounded-2xl border border-white/6 bg-white/[0.02] px-3 py-3">
                <ConversationHistory
                  sessions={sessions}
                  currentSessionId={currentSessionId}
                  onLoad={onLoadSession}
                  onDelete={onDeleteSession}
                  onNew={onNewSession}
                />
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}

export default MobileControlCenter
