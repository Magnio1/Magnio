import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  AlertTriangle,
  ArrowUpRight,
  Briefcase,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  CircleDashed,
  Loader2,
  MapPin,
  Play,
  RotateCcw,
  Send,
  XCircle,
  Zap,
} from 'lucide-react'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/$/, '')

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Job {
  id: string
  title: string
  company: string
  url: string
  source: string
  source_detail?: string
  company_slug?: string
  collection_lane?: 'watchlist' | 'discovery'
  location: string
  remote: boolean
  salary: string
  jd_full: string
  scraped_at: string
  status: string
  // enriched fields
  fit_score?: number
  summary?: string
  red_flags?: string[]
  strengths?: string[]
  positioning_note?: string
  outreach_draft?: string
  recommendation?: 'pursue' | 'review' | 'bypass'
  enriched_at?: string
  shortlisted?: boolean
}

interface PipelineRun {
  run_id: string
  started_at: string
  completed_at: string
  total_scored: number
  shortlist_count: number
  scrape_summary: {
    yc_fetched: number
    greenhouse_fetched: number
    lever_fetched?: number
    ashby_fetched?: number
    total_fetched: number
    new_written: number
    deduped_in_batch?: number
    skipped_existing?: number
    sources?: {
      yc?: {
        status?: string
        strategy?: string
        fetched?: number
        error?: string | null
        fallback_used?: boolean
      }
      greenhouse?: {
        status?: string
        strategy?: string
        fetched?: number
        watchlist_companies?: number
        watchlist_fetched?: number
        discovery_companies?: number
        discovery_fetched?: number
        error?: string | null
      }
      lever?: {
        status?: string
        strategy?: string
        fetched?: number
        watchlist_companies?: number
        watchlist_fetched?: number
        discovery_companies?: number
        discovery_fetched?: number
        error?: string | null
      }
      ashby?: {
        status?: string
        strategy?: string
        fetched?: number
        watchlist_companies?: number
        watchlist_fetched?: number
        discovery_companies?: number
        discovery_fetched?: number
        error?: string | null
      }
    }
  }
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreColor(score: number | undefined): string {
  if (score === undefined || score === null) return 'text-zinc-500'
  if (score >= 85) return 'text-emerald-400'
  if (score >= 70) return 'text-blue-400'
  if (score >= 55) return 'text-amber-400'
  if (score >= 40) return 'text-orange-400'
  return 'text-red-400'
}

function scoreBg(score: number | undefined): string {
  if (score === undefined || score === null) return 'bg-zinc-800'
  if (score >= 85) return 'bg-emerald-500/10 border border-emerald-500/20'
  if (score >= 70) return 'bg-blue-500/10 border border-blue-500/20'
  if (score >= 55) return 'bg-amber-500/10 border border-amber-500/20'
  if (score >= 40) return 'bg-orange-500/10 border border-orange-500/20'
  return 'bg-red-500/10 border border-red-500/20'
}

function recommendationBadge(rec: string | undefined) {
  if (rec === 'pursue')
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-300 border border-emerald-500/20">
        <CheckCircle size={10} />
        Pursue
      </span>
    )
  if (rec === 'review')
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-300 border border-amber-500/20">
        <CircleDashed size={10} />
        Review
      </span>
    )
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-zinc-800 px-2.5 py-0.5 text-xs font-medium text-zinc-500 border border-zinc-700/50">
      <XCircle size={10} />
      Bypass
    </span>
  )
}

function sourceBadge(source: string) {
  if (source === 'yc')
    return (
      <span className="rounded-full bg-orange-500/10 px-2 py-0.5 text-[10px] font-medium text-orange-400 border border-orange-500/20">
        YC
      </span>
    )
  if (source === 'hackernews')
    return (
      <span className="rounded-full bg-[#ff6600]/10 px-2 py-0.5 text-[10px] font-medium text-[#ff6600] border border-[#ff6600]/20">
        HN
      </span>
    )
  if (source === 'lever')
    return (
      <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300 border border-cyan-500/20">
        LV
      </span>
    )
  if (source === 'ashby')
    return (
      <span className="rounded-full bg-fuchsia-500/10 px-2 py-0.5 text-[10px] font-medium text-fuchsia-300 border border-fuchsia-500/20">
        AH
      </span>
    )
  return (
    <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-zinc-400 border border-zinc-700/50">
      GH
    </span>
  )
}

function laneBadge(lane: string | undefined) {
  if (lane === 'discovery') {
    return (
      <span className="rounded-full bg-violet-500/10 px-2 py-0.5 text-[10px] font-medium text-violet-300 border border-violet-500/20">
        Discovery
      </span>
    )
  }
  if (lane === 'watchlist') {
    return (
      <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-300 border border-sky-500/20">
        Watchlist
      </span>
    )
  }
  return null
}

function sourceRunPills(lastRun: PipelineRun | null) {
  const summary = lastRun?.scrape_summary
  const sourceEntries = [
    { key: 'yc', label: 'YC', fetched: summary?.sources?.yc?.fetched ?? summary?.yc_fetched, tone: 'text-orange-400 border-orange-500/20 bg-orange-500/10' },
    { key: 'greenhouse', label: 'GH', fetched: summary?.sources?.greenhouse?.fetched ?? summary?.greenhouse_fetched, tone: 'text-zinc-300 border-zinc-700/60 bg-zinc-800/60' },
    { key: 'lever', label: 'LV', fetched: summary?.sources?.lever?.fetched ?? summary?.lever_fetched, tone: 'text-cyan-300 border-cyan-500/20 bg-cyan-500/10' },
    { key: 'ashby', label: 'AH', fetched: summary?.sources?.ashby?.fetched ?? summary?.ashby_fetched, tone: 'text-fuchsia-300 border-fuchsia-500/20 bg-fuchsia-500/10' },
  ].filter((entry) => typeof entry.fetched === 'number')

  if (!sourceEntries.length) return null

  return (
    <div className="hidden xl:flex items-center gap-1.5">
      {sourceEntries.map((entry) => (
        <span
          key={entry.key}
          className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-[10px] ${entry.tone}`}
        >
          <span className="font-medium">{entry.label}</span>
          <span className="text-[11px] font-semibold">{entry.fetched ?? 0}</span>
        </span>
      ))}
      {typeof summary?.deduped_in_batch === 'number' && summary.deduped_in_batch > 0 && (
        <span className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-2 py-1 text-[10px] text-zinc-400">
          <span>deduped</span>
          <span className="font-semibold text-slate-200">{summary.deduped_in_batch}</span>
        </span>
      )}
    </div>
  )
}

function relativeTime(iso: string): string {
  if (!iso) return ''
  const delta = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(delta / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

// ---------------------------------------------------------------------------
// Token gate
// ---------------------------------------------------------------------------

function TokenGate({ onSubmit }: { onSubmit: (t: string) => void }) {
  const [value, setValue] = useState('')
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#060c14] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/15 via-[#060c14] to-[#060c14] relative">
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay pointer-events-none"></div>
      <div className="w-full max-w-sm rounded-2xl border border-white/5 bg-white/[0.02] backdrop-blur-2xl p-8 shadow-[0_8px_32px_rgba(0,0,0,0.5)] ring-1 ring-white/10 relative overflow-hidden">
        <div className="absolute -top-24 -right-24 h-48 w-48 rounded-full bg-blue-500/20 blur-3xl pointer-events-none" />
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 border border-blue-500/20">
            <Zap size={18} className="text-blue-400" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-100">JobRadar</div>
            <div className="text-xs text-zinc-500">Magnio Job Intelligence</div>
          </div>
        </div>
        <p className="mb-4 text-xs text-zinc-500">Enter your task token to access the triage dashboard.</p>
        <input
          type="password"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && value && onSubmit(value)}
          placeholder="Task token"
          className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2.5 text-sm text-slate-100 placeholder-zinc-500 outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 mb-3 transition-colors shadow-inner"
        />
        <button
          onClick={() => value && onSubmit(value)}
          className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
        >
          Access Dashboard
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Job card (left panel)
// ---------------------------------------------------------------------------

function JobCard({
  job,
  selected,
  onClick,
  onStatusChange,
  token,
}: {
  job: Job
  selected: boolean
  onClick: () => void
  onStatusChange: (status: string) => void
  token: string
}) {
  const [actioning, setActioning] = useState(false)

  async function updateStatus(status: string) {
    setActioning(true)
    try {
      await fetch(`${API_BASE}/jobs/${job.id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-task-token': token },
        body: JSON.stringify({ status }),
      })
      onStatusChange(status)
    } catch (err) {
      console.error('status update failed', err)
    } finally {
      setActioning(false)
    }
  }

  const isPursued = job.status === 'approved'
  const isBypassed = job.status === 'bypassed'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      onClick={onClick}
      className={`relative overflow-hidden cursor-pointer rounded-xl border p-4 transition-all duration-300 ${
        selected
          ? 'border-blue-500/40 bg-blue-500/[0.08] backdrop-blur-md ring-1 ring-blue-500/30 shadow-[0_0_20px_rgba(59,130,246,0.15)]'
          : 'border-white/5 bg-white/[0.02] backdrop-blur-sm hover:border-white/10 hover:bg-white/[0.04]'
      } ${isBypassed ? 'opacity-40' : ''}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            {sourceBadge(job.source)}
            {laneBadge(job.collection_lane)}
            <span className="text-[10px] text-zinc-600">{relativeTime(job.scraped_at)}</span>
          </div>
          <div className="mt-1 text-sm font-semibold text-slate-100 leading-tight truncate">
            {job.title}
          </div>
          <div className="text-xs text-zinc-400 mt-0.5">{job.company}</div>
        </div>

        {/* Fit score */}
        {job.fit_score !== undefined && (
          <div className={`flex-shrink-0 rounded-xl px-3 py-2 text-center ${scoreBg(job.fit_score)}`}>
            <div className={`text-lg font-bold leading-none ${scoreColor(job.fit_score)}`}>
              {job.fit_score}
            </div>
            <div className="text-[9px] text-zinc-500 mt-0.5">score</div>
          </div>
        )}
      </div>

      {/* Location + remote */}
      {job.location && (
        <div className="flex items-center gap-1 mb-2 text-xs text-zinc-500">
          <MapPin size={10} />
          {job.location}
          {job.remote && <span className="ml-1 text-emerald-500/70">· Remote</span>}
        </div>
      )}

      {/* Recommendation + salary */}
      <div className="flex items-center gap-2 flex-wrap mb-3">
        {recommendationBadge(job.recommendation)}
        {job.salary && (
          <span className="text-xs text-zinc-500">{job.salary}</span>
        )}
      </div>

      {/* Summary */}
      {job.summary && (
        <p className="text-xs text-zinc-400 leading-relaxed mb-3 line-clamp-2">
          {job.summary}
        </p>
      )}

      {/* Red flags */}
      {(job.red_flags ?? []).length > 0 && (
        <div className="mb-3 space-y-0.5">
          {(job.red_flags ?? []).slice(0, 2).map((rf, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[11px] text-red-400/80">
              <AlertTriangle size={10} className="mt-0.5 flex-shrink-0" />
              <span className="line-clamp-1">{rf}</span>
            </div>
          ))}
          {(job.red_flags ?? []).length > 2 && (
            <div className="text-[10px] text-zinc-600">
              +{(job.red_flags ?? []).length - 2} more flags
            </div>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
        {!isPursued ? (
          <button
            disabled={actioning || isBypassed}
            onClick={() => updateStatus('approved')}
            className="flex-1 rounded-lg border border-emerald-500/20 bg-emerald-500/5 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/10 transition-colors disabled:opacity-40"
          >
            Pursue
          </button>
        ) : (
          <button
            disabled={actioning}
            onClick={() => updateStatus('scored')}
            className="flex-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 py-1.5 text-xs font-medium text-emerald-300"
          >
            ✓ Pursuing
          </button>
        )}
        {!isBypassed ? (
          <button
            disabled={actioning || isPursued}
            onClick={() => updateStatus('bypassed')}
            className="flex-1 rounded-lg border border-zinc-700/50 bg-zinc-800/50 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-800 transition-colors disabled:opacity-40"
          >
            Bypass
          </button>
        ) : (
          <button
            disabled={actioning}
            onClick={() => updateStatus('scored')}
            className="flex-1 rounded-lg border border-zinc-700/50 bg-zinc-800/50 py-1.5 text-xs font-medium text-zinc-500"
          >
            Undo
          </button>
        )}
        <a
          href={job.url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-center rounded-lg border border-zinc-700/50 bg-zinc-800/50 px-2.5 hover:bg-zinc-800 transition-colors"
        >
          <ArrowUpRight size={13} className="text-zinc-400" />
        </a>
      </div>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Streaming dots indicator
// ---------------------------------------------------------------------------

function StreamingDots() {
  return (
    <span className="inline-flex items-center gap-[3px] ml-1 align-middle">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="inline-block h-1.5 w-1.5 rounded-full bg-blue-400/70"
          style={{ animation: `bounceDot 1.2s ease-in-out ${i * 0.2}s infinite` }}
        />
      ))}
      <style>{`
        @keyframes bounceDot {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </span>
  )
}

// ---------------------------------------------------------------------------
// Chat panel (right panel)
// ---------------------------------------------------------------------------

function ChatPanel({ job, token, onBack }: { job: Job; token: string; onBack?: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // RAF handle to batch chunk-level state updates into one render per frame
  const rafRef = useRef<number | null>(null)
  const accRef = useRef('')

  // Reset chat when job changes
  useEffect(() => {
    setMessages([])
    setInput('')
  }, [job.id])

  // Scroll: instant during streaming (no animation fighting), smooth for new messages
  useEffect(() => {
    const isStreaming = messages[messages.length - 1]?.isStreaming
    bottomRef.current?.scrollIntoView({ behavior: isStreaming ? 'instant' : 'smooth' })
  }, [messages])

  async function sendMessage() {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: ChatMessage = { role: 'user', content: text }
    const assistantMsg: ChatMessage = { role: 'assistant', content: '', isStreaming: true }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')
    setLoading(true)

    const history = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }))

    try {
      const resp = await fetch(`${API_BASE}/jobs/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-task-token': token },
        body: JSON.stringify({ job_id: job.id, messages: history }),
      })

      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      accRef.current = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        accRef.current += decoder.decode(value, { stream: true })

        // Collapse multiple chunks arriving in the same animation frame into one render
        if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
        const snapshot = accRef.current
        rafRef.current = requestAnimationFrame(() => {
          setMessages((prev) => {
            const next = [...prev]
            next[next.length - 1] = { role: 'assistant', content: snapshot, isStreaming: true }
            return next
          })
          rafRef.current = null
        })
      }

      // Cancel any pending frame and commit final state
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      const finalContent = accRef.current
      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = { role: 'assistant', content: finalContent, isStreaming: false }
        return next
      })
    } catch (err) {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = {
          role: 'assistant',
          content: `Error: ${err instanceof Error ? err.message : 'Request failed'}`,
          isStreaming: false,
        }
        return next
      })
    } finally {
      setLoading(false)
      textareaRef.current?.focus()
    }
  }

  const suggestions = [
    { text: 'Why did this score the way it did?', icon: '◎' },
    { text: 'What are my biggest risks here?', icon: '⚑' },
    { text: 'Rewrite the outreach for this role', icon: '✦' },
    { text: 'Which story should I lead with?', icon: '◈' },
  ]

  return (
    <div className="flex h-full flex-col">
      {/* Chat header */}
      <div className="border-b border-white/5 bg-white/[0.015] backdrop-blur-xl px-5 py-3.5 flex-shrink-0 relative">
        {/* Top gradient accent line */}
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/40 to-transparent" />
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            {/* Back button — mobile only */}
            {onBack && (
              <button
                onClick={onBack}
                className="sm:hidden flex items-center gap-1 text-zinc-400 hover:text-slate-200 transition-colors flex-shrink-0 -ml-1"
              >
                <ChevronLeft size={18} />
                <span className="text-xs font-medium">Jobs</span>
              </button>
            )}
            <div className="relative flex-shrink-0">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500/20 to-indigo-500/10 border border-blue-500/25 shadow-[0_0_12px_rgba(59,130,246,0.15)]">
                <Briefcase size={13} className="text-blue-300" />
              </div>
              <div className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 border-2 border-[#060c14] shadow-[0_0_6px_rgba(16,185,129,0.8)]" />
            </div>
            <div className="min-w-0">
              <div className="text-[13px] font-semibold text-slate-100 truncate leading-tight">
                {job.title}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[11px] text-zinc-400">{job.company}</span>
                {job.fit_score !== undefined && (
                  <>
                    <span className="text-zinc-700">·</span>
                    <span className={`text-[11px] font-semibold ${scoreColor(job.fit_score)}`}>
                      {job.fit_score}
                    </span>
                  </>
                )}
                {job.recommendation && (
                  <>
                    <span className="text-zinc-700">·</span>
                    {recommendationBadge(job.recommendation)}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5 min-h-0 scroll-smooth">
        {messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4 pt-1"
          >
            {/* Intro blurb */}
            <div className="flex items-start gap-2.5">
              <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500/20 to-indigo-500/10 border border-blue-500/20 mt-0.5">
                <Zap size={12} className="text-blue-300" />
              </div>
              <div className="rounded-2xl rounded-tl-sm bg-white/[0.04] border border-white/[0.07] backdrop-blur-md px-4 py-3 shadow-sm">
                <p className="text-[12.5px] text-zinc-300 leading-relaxed">
                  I've analyzed this role for you. Ask me about fit reasoning, red flags, positioning strategy, or outreach copy.
                </p>
              </div>
            </div>

            {/* Suggestion chips */}
            <div className="grid grid-cols-1 gap-2 pl-9">
              {suggestions.map((s) => (
                <button
                  key={s.text}
                  onClick={() => { setInput(s.text); textareaRef.current?.focus() }}
                  className="group relative rounded-xl border border-white/[0.07] bg-white/[0.025] px-4 py-2.5 text-left text-[12.5px] text-zinc-400 hover:border-blue-500/30 hover:bg-blue-500/[0.05] hover:text-slate-200 transition-all duration-200 flex items-center justify-between overflow-hidden backdrop-blur-sm"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 to-blue-500/0 group-hover:from-blue-500/[0.04] group-hover:to-transparent transition-all duration-300 pointer-events-none" />
                  <div className="flex items-center gap-2.5 relative z-10">
                    <span className="text-[11px] text-zinc-600 group-hover:text-blue-400/70 transition-colors font-mono">
                      {s.icon}
                    </span>
                    <span>{s.text}</span>
                  </div>
                  <ChevronRight
                    size={13}
                    className="text-zinc-700 group-hover:text-blue-400/60 group-hover:translate-x-0.5 transition-all flex-shrink-0 relative z-10"
                  />
                </button>
              ))}
            </div>
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className={`flex items-end gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {/* Assistant avatar */}
              {msg.role === 'assistant' && (
                <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500/20 to-indigo-500/10 border border-blue-500/20 mb-0.5">
                  <Zap size={12} className="text-blue-300" />
                </div>
              )}

              {msg.role === 'user' ? (
                <div className="max-w-[78%] rounded-2xl rounded-br-sm bg-gradient-to-br from-blue-600 to-blue-500 shadow-[0_4px_24px_rgba(59,130,246,0.35)] border border-blue-400/30 px-4 py-2.5 text-[13px] text-white leading-relaxed">
                  {msg.content}
                </div>
              ) : (
                <div className="max-w-[88%] rounded-2xl rounded-tl-sm relative overflow-hidden">
                  {/* Left accent bar */}
                  <div className="absolute left-0 top-3 bottom-3 w-[2px] rounded-full bg-gradient-to-b from-blue-500/60 to-indigo-500/40" />
                  <div className="bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] shadow-[0_2px_16px_rgba(0,0,0,0.3)] px-4 pl-5 py-3 text-[13px] text-slate-300 leading-relaxed">
                    {msg.content === '' && msg.isStreaming ? (
                      <StreamingDots />
                    ) : (
                      <>
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            h1: ({ ...props }) => <h1 className="text-base font-bold mt-4 mb-2 text-white" {...props} />,
                            h2: ({ ...props }) => <h2 className="text-[13px] font-semibold mt-4 mb-2 text-white" {...props} />,
                            h3: ({ ...props }) => <h3 className="text-[13px] font-semibold mt-3 mb-1.5 text-blue-300" {...props} />,
                            p: ({ ...props }) => <p className="mb-3 last:mb-0 leading-[1.65]" {...props} />,
                            ul: ({ ...props }) => <ul className="list-none pl-0 mb-3 space-y-1.5" {...props} />,
                            ol: ({ ...props }) => <ol className="list-decimal pl-4 mb-3 space-y-1.5" {...props} />,
                            li: ({ ...props }) => (
                              <li className="flex items-start gap-2 text-[12.5px]">
                                <span className="mt-1.5 h-1 w-1 rounded-full bg-blue-400/50 flex-shrink-0" />
                                <span {...props} />
                              </li>
                            ),
                            strong: ({ ...props }) => <strong className="font-semibold text-slate-100" {...props} />,
                            hr: ({ ...props }) => <hr className="my-4 border-white/[0.08]" {...props} />,
                            code: ({ ...props }) => (
                              <code className="bg-blue-500/10 border border-blue-500/20 rounded-md px-1.5 py-0.5 font-mono text-[11px] text-blue-200" {...props} />
                            ),
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                        {msg.isStreaming && <StreamingDots />}
                      </>
                    )}
                  </div>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-white/[0.06] backdrop-blur-2xl px-4 py-3.5 flex-shrink-0 relative z-10">
        {/* Top shimmer line */}
        <div className="absolute top-0 left-8 right-8 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent pointer-events-none" />
        <div className="flex items-end gap-3 rounded-2xl border border-white/[0.09] bg-white/[0.03] px-4 py-3 focus-within:border-blue-500/40 focus-within:ring-[3px] focus-within:ring-blue-500/[0.08] focus-within:bg-white/[0.05] transition-all duration-200 shadow-[0_2px_20px_rgba(0,0,0,0.4)]">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendMessage()
              }
            }}
            placeholder="Ask about fit, flags, positioning, outreach..."
            rows={1}
            className="flex-1 resize-none appearance-none rounded-none border-0 bg-transparent p-0 text-[13px] text-slate-100 shadow-none outline-none placeholder-zinc-600 focus:border-0 focus:outline-none focus:ring-0 focus:shadow-none leading-relaxed max-h-32 py-1"
          />
          <div className="flex items-center gap-2 flex-shrink-0">
            {input && (
              <span className="hidden sm:block text-[10px] text-zinc-700 select-none">
                ⇧↵ newline
              </span>
            )}
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 to-blue-400 text-white transition-all duration-200 shadow-[0_0_16px_rgba(59,130,246,0.35)] border border-blue-400/40 hover:shadow-[0_0_28px_rgba(59,130,246,0.55)] hover:scale-[1.04] active:scale-[0.96] disabled:opacity-25 disabled:saturate-0 disabled:shadow-none disabled:scale-100"
            >
              {loading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Send size={13} className="mr-0.5 mt-0.5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty chat state
// ---------------------------------------------------------------------------

function ChatEmpty() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center px-8">
      {/* Pulsing ring icon */}
      <div className="relative">
        <div className="absolute inset-0 rounded-2xl bg-blue-500/10 blur-xl animate-pulse" />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500/10 to-indigo-500/5 border border-blue-500/20 backdrop-blur-xl shadow-[0_0_30px_rgba(59,130,246,0.12)]">
          <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-white/[0.04] to-transparent pointer-events-none" />
          <Briefcase size={22} className="text-blue-400/70 relative z-10" />
        </div>
      </div>
      <div>
        <div className="text-sm font-semibold text-zinc-300">Select a role to begin</div>
        <div className="mt-1.5 text-xs text-zinc-600 leading-relaxed max-w-[200px]">
          Choose any job card to open the AI Advisor chat for that role.
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export default function JobRadarPanel() {
  const [token, setToken] = useState(() => localStorage.getItem('jobradar-token') ?? '')
  const [authed, setAuthed] = useState(false)

  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [mobileView, setMobileView] = useState<'jobs' | 'chat'>('jobs')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [lastRun, setLastRun] = useState<PipelineRun | null>(null)
  const [pipelineMsg, setPipelineMsg] = useState('')

  // Load jobs once authed
  useEffect(() => {
    if (authed) {
      loadJobs()
      loadLastRun()
    }
  }, [authed])

  function handleTokenSubmit(t: string) {
    setToken(t)
    localStorage.setItem('jobradar-token', t)
    setAuthed(true)
  }

  if (!authed && !token) {
    return <TokenGate onSubmit={handleTokenSubmit} />
  }

  // Try auto-auth with stored token
  if (!authed && token) {
    setAuthed(true)
  }

  async function loadJobs() {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/jobs/?limit=40`, {
        headers: { 'x-task-token': token },
      })
      if (res.status === 401) {
        setAuthed(false)
        setToken('')
        localStorage.removeItem('jobradar-token')
        return
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setJobs(data.jobs ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }

  async function loadLastRun() {
    try {
      const res = await fetch(`${API_BASE}/jobs/pipeline/runs?limit=1`, {
        headers: { 'x-task-token': token },
      })
      if (!res.ok) return
      const data = await res.json()
      if (data.runs?.length > 0) setLastRun(data.runs[0])
    } catch {
      // non-critical
    }
  }

  async function runPipeline() {
    setPipelineRunning(true)
    setPipelineMsg('Running pipeline — this takes 2–4 minutes...')
    try {
      const res = await fetch(`${API_BASE}/jobs/pipeline/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-task-token': token },
        body: JSON.stringify({ yc_limit: 40, hn_limit: 40, score_limit: 40, top_n: 10 }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setLastRun(data)
      setPipelineMsg(
        `Done — ${data.total_scored} scored, ${data.shortlist_count} shortlisted (${data.scrape_summary?.total_fetched ?? 0} fetched, ${data.scrape_summary?.deduped_in_batch ?? 0} deduped)`
      )
      await loadJobs()
      await loadLastRun()
    } catch (err) {
      setPipelineMsg(`Pipeline failed: ${err instanceof Error ? err.message : 'unknown error'}`)
    } finally {
      setPipelineRunning(false)
    }
  }

  function handleJobStatusChange(jobId: string, status: string) {
    setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, status } : j)))
    setSelectedJob((prev) => (prev?.id === jobId ? { ...prev, status } : prev))
  }

  // Counts
  const pursue = jobs.filter((j) => j.recommendation === 'pursue').length
  const review = jobs.filter((j) => j.recommendation === 'review').length
  const pursuing = jobs.filter((j) => j.status === 'approved').length

  return (
    <div className="flex h-screen flex-col bg-[#060c14] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/15 via-[#060c14] to-black text-slate-100 overflow-hidden relative">
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay pointer-events-none"></div>
      
      {/* Ambient background glow */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />
      <div className="absolute bottom-1/3 right-1/4 w-[28rem] h-[28rem] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />

      {/* Header */}
      <div className="border-b border-white/5 bg-white/[0.01] backdrop-blur-2xl px-5 py-3.5 flex-shrink-0 z-10 relative shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-500/10 border border-blue-500/20">
              <Zap size={15} className="text-blue-400" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-100">JobRadar</div>
              <div className="text-[10px] text-zinc-500">Magnio Job Intelligence</div>
            </div>

            {/* Stats */}
            <div className="hidden sm:flex items-center gap-1.5 ml-3">
              {/* AI recommendation pills */}
              <div className="flex items-center rounded-lg border border-white/[0.06] bg-white/[0.03] divide-x divide-white/[0.06] overflow-hidden">
                <div className="flex items-center gap-1.5 px-2.5 py-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_4px_rgba(52,211,153,0.8)]" />
                  <span className="text-[11px] font-semibold text-emerald-400">{pursue}</span>
                  <span className="text-[10px] text-zinc-600">pursue</span>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 py-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shadow-[0_0_4px_rgba(251,191,36,0.8)]" />
                  <span className="text-[11px] font-semibold text-amber-400">{review}</span>
                  <span className="text-[10px] text-zinc-600">review</span>
                </div>
              </div>

              {/* Divider */}
              <div className="h-4 w-px bg-white/[0.06] mx-0.5" />

              {/* User decision pill — this is what Pursue button increments */}
              <div className="flex items-center gap-1.5 rounded-lg border border-blue-500/20 bg-blue-500/[0.07] px-2.5 py-1.5">
                <CheckCircle size={11} className="text-blue-400" />
                <span className="text-[11px] font-semibold text-blue-400">{pursuing}</span>
                <span className="text-[10px] text-zinc-500">pursuing</span>
              </div>
            </div>
          </div>

          {sourceRunPills(lastRun)}

          <div className="flex items-center gap-2">
            {pipelineMsg && (
              <span className="text-[11px] text-zinc-500 max-w-xs truncate hidden md:block">{pipelineMsg}</span>
            )}
            {lastRun && !pipelineMsg && (
              <span className="text-[11px] text-zinc-600 hidden md:block">
                Last run {relativeTime(lastRun.completed_at)}
              </span>
            )}
            <button
              onClick={loadJobs}
              disabled={loading}
              className="flex items-center gap-1.5 rounded-lg border border-zinc-700/60 bg-zinc-900/60 px-3 py-1.5 text-xs text-zinc-400 hover:border-zinc-600/60 hover:text-slate-200 transition-colors disabled:opacity-40"
            >
              <RotateCcw size={11} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button
              onClick={runPipeline}
              disabled={pipelineRunning}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 transition-colors disabled:opacity-60"
            >
              {pipelineRunning ? (
                <Loader2 size={11} className="animate-spin" />
              ) : (
                <Play size={11} />
              )}
              Run Pipeline
            </button>
          </div>
        </div>
      </div>

      {/* Body: split panel */}
      <div className="flex flex-1 min-h-0 overflow-hidden relative z-10">
        {/* Left panel: job list — hidden on mobile when chat is open */}
        <div className={`
          border-r border-white/5 bg-black/20 backdrop-blur-md flex flex-col min-h-0 flex-shrink-0
          shadow-[4px_0_24px_rgba(0,0,0,0.2)]
          w-full sm:w-[42%] lg:w-[38%]
          ${mobileView === 'chat' ? 'hidden sm:flex' : 'flex'}
        `}>
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 flex-shrink-0">
            <span className="text-xs text-zinc-500">{jobs.length} jobs</span>
            {error && <span className="text-xs text-red-400">{error}</span>}
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {loading && jobs.length === 0 && (
              <div className="flex items-center justify-center py-16 text-xs text-zinc-600">
                <Loader2 size={16} className="animate-spin mr-2" />
                Loading jobs...
              </div>
            )}

            {!loading && jobs.length === 0 && !error && (
              <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-white/5 bg-white/[0.02] backdrop-blur-sm shadow-inner relative">
                  <div className="absolute inset-0 rounded-xl bg-gradient-to-tr from-white/5 to-transparent pointer-events-none" />
                  <Briefcase size={18} className="text-zinc-500" />
                </div>
                <div>
                  <div className="text-xs font-medium text-zinc-500">No jobs yet</div>
                  <div className="text-[11px] text-zinc-600 mt-1">Run the pipeline to scrape and score jobs</div>
                </div>
              </div>
            )}

            <AnimatePresence mode="popLayout">
              {jobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  selected={selectedJob?.id === job.id}
                  onClick={() => {
                    setSelectedJob(job)
                    setMobileView('chat')
                  }}
                  onStatusChange={(s) => handleJobStatusChange(job.id, s)}
                  token={token}
                />
              ))}
            </AnimatePresence>
          </div>
        </div>

        {/* Right panel: chat — hidden on mobile when jobs list is open */}
        <div className={`
          flex-1 min-w-0 flex flex-col min-h-0
          ${mobileView === 'jobs' ? 'hidden sm:flex' : 'flex'}
        `}>
          <AnimatePresence mode="wait">
            {selectedJob ? (
              <motion.div
                key={selectedJob.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="h-full"
              >
                <ChatPanel
                  job={selectedJob}
                  token={token}
                  onBack={() => {
                    setMobileView('jobs')
                    setSelectedJob(null)
                  }}
                />
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="h-full"
              >
                <ChatEmpty />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
