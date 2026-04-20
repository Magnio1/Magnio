import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  AlertTriangle,
  ArrowLeft,
  ArrowUpRight,
  Briefcase,
  CheckCircle,
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
    total_fetched: number
    new_written: number
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

function scoreRing(score: number | undefined): string {
  if (score === undefined || score === null) return 'ring-zinc-700 bg-zinc-800/40'
  if (score >= 85) return 'ring-emerald-500/40 bg-emerald-500/5'
  if (score >= 70) return 'ring-blue-500/40 bg-blue-500/5'
  if (score >= 55) return 'ring-amber-500/40 bg-amber-500/5'
  if (score >= 40) return 'ring-orange-500/40 bg-orange-500/5'
  return 'ring-red-500/40 bg-red-500/5'
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
  if (source === 'greenhouse')
    return (
      <span className="rounded-full bg-green-500/10 px-2 py-0.5 text-[10px] font-medium text-green-400 border border-green-500/20">
        GH
      </span>
    )
  if (source === 'lever')
    return (
      <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-400 border border-cyan-500/20">
        LV
      </span>
    )
  if (source === 'ashby')
    return (
      <span className="rounded-full bg-purple-500/10 px-2 py-0.5 text-[10px] font-medium text-purple-400 border border-purple-500/20">
        AB
      </span>
    )
  if (source === 'hackernews')
    return (
      <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400 border border-amber-500/20">
        HN
      </span>
    )
  if (source === 'workable')
    return (
      <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-400 border border-sky-500/20">
        WK
      </span>
    )
  return (
    <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-zinc-400 border border-zinc-700/50">
      {source.slice(0, 2).toUpperCase()}
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

function relativeTime(iso: string): string {
  if (!iso) return ''
  const delta = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(delta / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function addedDateLabel(iso: string): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

// ---------------------------------------------------------------------------
// Token gate
// ---------------------------------------------------------------------------

function TokenGate({ onSubmit }: { onSubmit: (t: string) => void }) {
  const [value, setValue] = useState('')
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#060c14] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/15 via-[#060c14] to-[#060c14] relative">
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay pointer-events-none" />
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
  dimWhenBypassed = true,
  index = 0,
}: {
  job: Job
  selected: boolean
  onClick: () => void
  onStatusChange: (status: string) => void
  token: string
  dimWhenBypassed?: boolean
  index?: number
}) {
  const [actioning, setActioning] = useState(false)
  const [flagsExpanded, setFlagsExpanded] = useState(false)

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
  const flags = job.red_flags ?? []
  const strengths = job.strengths ?? []
  const visibleFlagCount = flagsExpanded ? flags.length : 2
  const isPursueTier = (job.fit_score ?? 0) >= 80 && job.recommendation === 'pursue'

  const animStyle = isBypassed && dimWhenBypassed
    ? {}
    : {
        animation: 'cardFadeIn 0.18s ease-out backwards',
        animationDelay: `${Math.min(index * 0.03, 0.2)}s`,
      }

  return (
    <div
      style={animStyle}
      onClick={onClick}
      className={`relative w-full overflow-hidden cursor-pointer rounded-xl border p-4 transition-[border-color,background-color,box-shadow,opacity] duration-200 ${
        selected
          ? 'border-blue-500/40 bg-blue-500/[0.08] backdrop-blur-md ring-1 ring-blue-500/30 shadow-[0_0_20px_rgba(59,130,246,0.15)]'
          : isPursueTier
            ? 'border-emerald-500/20 bg-emerald-500/[0.03] backdrop-blur-sm hover:border-emerald-500/30 hover:bg-emerald-500/[0.05]'
            : 'border-white/5 bg-white/[0.02] backdrop-blur-sm hover:border-white/10 hover:bg-white/[0.04]'
      } ${isBypassed && dimWhenBypassed ? 'opacity-40' : ''}`}
    >
      {/* Selected accent bar */}
      {selected && (
        <div className="absolute top-0 left-0 bottom-0 w-[3px] bg-gradient-to-b from-blue-400 to-blue-600 rounded-l-xl" />
      )}
      {/* Pursue-tier accent bar */}
      {!selected && isPursueTier && (
        <div className="absolute top-0 left-0 bottom-0 w-[3px] bg-gradient-to-b from-emerald-400 to-emerald-600 rounded-l-xl" />
      )}

      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-2.5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
            {sourceBadge(job.source)}
            {laneBadge(job.collection_lane)}
            <span className="text-[10px] text-zinc-600">{relativeTime(job.scraped_at)}</span>
            <span className="text-[10px] text-zinc-700">·</span>
            <span className="text-[10px] text-zinc-600">Added {addedDateLabel(job.scraped_at)}</span>
          </div>
          <div className="text-[13px] font-bold text-slate-100 leading-snug">
            {job.title}
          </div>
          <div className="text-xs text-zinc-400 mt-0.5">{job.company}</div>
        </div>

        {/* Circular fit score */}
        {job.fit_score !== undefined && (
          <div className={`flex-shrink-0 w-12 h-12 rounded-full ring-2 flex flex-col items-center justify-center ${scoreRing(job.fit_score)}`}>
            <div className={`text-base font-bold leading-none ${scoreColor(job.fit_score)}`}>
              {job.fit_score}
            </div>
            <div className="text-[8px] text-zinc-500 mt-0.5 uppercase tracking-wide">fit</div>
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
      <div className="flex items-center gap-2 flex-wrap mb-2.5">
        {recommendationBadge(job.recommendation)}
        {job.salary && (
          <span className="text-xs text-zinc-500">{job.salary}</span>
        )}
      </div>

      {/* Summary */}
      {job.summary && (
        <p className="text-xs text-zinc-400 leading-relaxed mb-2.5 line-clamp-2">
          {job.summary}
        </p>
      )}

      {/* Strengths — top 1 shown as a green signal */}
      {strengths.length > 0 && (
        <div className="mb-2 space-y-0.5">
          {strengths.slice(0, 1).map((s, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[11px] text-emerald-400/80">
              <CheckCircle size={10} className="mt-0.5 flex-shrink-0" />
              <span className="line-clamp-1">{s}</span>
            </div>
          ))}
        </div>
      )}

      {/* Red flags — expandable */}
      {flags.length > 0 && (
        <div className="mb-3 space-y-0.5">
          {flags.slice(0, visibleFlagCount).map((rf, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[11px] text-red-400/80">
              <AlertTriangle size={10} className="mt-0.5 flex-shrink-0" />
              <span className={flagsExpanded ? '' : 'line-clamp-1'}>{rf}</span>
            </div>
          ))}
          {flags.length > 2 && (
            <button
              onClick={(e) => { e.stopPropagation(); setFlagsExpanded((v) => !v) }}
              className="text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              {flagsExpanded ? '↑ Show less' : `+${flags.length - 2} more flags`}
            </button>
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
            className="flex-1 rounded-lg border border-emerald-500/40 bg-emerald-500/15 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/5 transition-colors"
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
            className="flex-1 rounded-lg border border-zinc-700/50 bg-zinc-800/50 py-1.5 text-xs font-medium text-zinc-400 hover:text-zinc-300 hover:bg-zinc-700/50 transition-colors"
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
    </div>
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

  useEffect(() => {
    setMessages([])
    setInput('')
  }, [job.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
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
      let accumulated = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        accumulated += decoder.decode(value, { stream: true })
        setMessages((prev) => {
          const next = [...prev]
          next[next.length - 1] = { role: 'assistant', content: accumulated, isStreaming: true }
          return next
        })
      }

      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = { role: 'assistant', content: accumulated, isStreaming: false }
        return next
      })
    } catch (err) {
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
    'Why did this score the way it did?',
    'What are my biggest risks here?',
    'Rewrite the outreach for this role',
    'Which story should I lead with?',
  ]

  return (
    <div className="flex h-full flex-col">
      {/* Chat header */}
      <div className="border-b border-white/5 bg-white/[0.01] backdrop-blur-md px-4 py-3 flex-shrink-0 relative">
        <div className="flex items-center gap-3">
          {/* Back button — mobile only */}
          {onBack && (
            <button
              onClick={onBack}
              className="sm:hidden flex items-center justify-center w-8 h-8 rounded-lg border border-white/10 bg-white/[0.03] text-zinc-400 hover:text-slate-200 hover:border-white/20 transition-colors flex-shrink-0"
              aria-label="Back to job list"
            >
              <ArrowLeft size={14} />
            </button>
          )}
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-500/10 border border-blue-500/20 flex-shrink-0">
            <Briefcase size={13} className="text-blue-400" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold text-slate-100 truncate">
              {job.title} · {job.company}
            </div>
            <div className="flex items-center gap-2 text-[10px] text-zinc-500">
              <span className={`font-medium ${scoreColor(job.fit_score)}`}>
                {job.fit_score !== undefined ? `${job.fit_score}/100` : 'Unscored'}
              </span>
              {job.recommendation && (
                <>
                  <span>·</span>
                  <span className="capitalize">{job.recommendation}</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="space-y-3 pt-2">
            <p className="text-xs text-zinc-500">
              Ask anything about this role — fit reasoning, red flags, positioning, outreach.
            </p>
            <div className="grid grid-cols-1 gap-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => { setInput(s); textareaRef.current?.focus() }}
                  className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-left text-xs text-zinc-400 hover:border-white/10 hover:bg-white/[0.04] hover:text-slate-200 transition-all flex items-center justify-between group backdrop-blur-sm"
                >
                  {s}
                  <ChevronRight size={12} className="text-zinc-600 group-hover:text-zinc-400 flex-shrink-0" />
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' ? (
              <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-blue-600 shadow-md shadow-blue-500/20 border border-blue-500 px-4 py-2.5 text-xs text-white">
                {msg.content}
              </div>
            ) : (
              <div className="max-w-[92%] rounded-2xl rounded-tl-sm bg-white/[0.03] backdrop-blur-md border border-white/5 shadow-sm px-4 py-3 text-xs text-slate-300 leading-relaxed">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ ...props }) => <h1 className="text-lg font-bold mt-4 mb-2 text-white" {...props} />,
                    h2: ({ ...props }) => <h2 className="text-base font-semibold mt-4 mb-2 text-white" {...props} />,
                    h3: ({ ...props }) => <h3 className="text-sm font-semibold mt-3 mb-1 text-blue-300" {...props} />,
                    p: ({ ...props }) => <p className="mb-3 last:mb-0 leading-relaxed" {...props} />,
                    ul: ({ ...props }) => <ul className="list-disc pl-4 mb-3 space-y-1" {...props} />,
                    ol: ({ ...props }) => <ol className="list-decimal pl-4 mb-3 space-y-1" {...props} />,
                    li: ({ ...props }) => <li className="mb-0.5" {...props} />,
                    strong: ({ ...props }) => <strong className="font-semibold text-slate-100" {...props} />,
                    hr: ({ ...props }) => <hr className="my-4 border-white/10" {...props} />,
                    code: ({ ...props }) => <code className="bg-white/10 rounded px-1 py-0.5 font-mono text-[11px]" {...props} />,
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
                {msg.isStreaming && (
                  <span className="ml-1 inline-block h-3 w-0.5 animate-pulse bg-blue-400 align-middle" />
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-white/5 bg-white/[0.01] backdrop-blur-md p-4 flex-shrink-0">
        <div className="mx-auto flex items-end gap-2 rounded-xl border border-white/5 bg-black/20 px-3 py-2 focus-within:border-blue-500/40 focus-within:ring-1 focus-within:ring-blue-500/10 focus-within:bg-black/40 transition-all shadow-inner">
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
            className="flex-1 resize-none bg-transparent text-xs text-slate-200 placeholder-zinc-600 outline-none leading-relaxed max-h-24"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-40 transition-colors"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
          </button>
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
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.02] backdrop-blur-xl shadow-[0_0_30px_rgba(255,255,255,0.03)] relative">
        <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-white/5 to-transparent pointer-events-none" />
        <Briefcase size={22} className="text-zinc-500" />
      </div>
      <div>
        <div className="text-sm font-semibold text-zinc-300">Job Advisor</div>
        <div className="mt-1.5 text-xs text-zinc-600 leading-relaxed max-w-[220px]">
          Select a job from the list to get AI-powered fit analysis, red flag breakdown, and outreach drafts.
        </div>
      </div>
      <div className="flex flex-col gap-1.5 w-full max-w-[240px]">
        {['Fit reasoning', 'Red flag breakdown', 'Outreach drafts', 'Positioning advice'].map((hint) => (
          <div key={hint} className="flex items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
            <div className="w-1 h-1 rounded-full bg-blue-500/60 flex-shrink-0" />
            <span className="text-[11px] text-zinc-500">{hint}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Filter chip types
// ---------------------------------------------------------------------------

type FilterKey = 'all' | 'pursue' | 'review' | 'bypass' | 'approved'

const FILTERS: { key: FilterKey; label: string; activeColor: string }[] = [
  { key: 'all',      label: 'All',      activeColor: 'bg-zinc-700/60 text-slate-200 border-zinc-600/60' },
  { key: 'pursue',   label: 'Pursue',   activeColor: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30' },
  { key: 'review',   label: 'Review',   activeColor: 'bg-amber-500/10 text-amber-300 border-amber-500/30' },
  { key: 'bypass',   label: 'Bypass',   activeColor: 'bg-zinc-800 text-zinc-400 border-zinc-600/60' },
  { key: 'approved', label: 'Approved', activeColor: 'bg-blue-500/10 text-blue-300 border-blue-500/30' },
]

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export default function JobRadarPanel() {
  const [token, setToken] = useState(() => localStorage.getItem('jobradar-token') ?? '')
  const [authed, setAuthed] = useState(false)

  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [lastRun, setLastRun] = useState<PipelineRun | null>(null)
  const [pipelineMsg, setPipelineMsg] = useState('')

  // Mobile: 'list' shows left panel, 'chat' shows right panel
  const [mobileView, setMobileView] = useState<'list' | 'chat'>('list')

  // Filter state
  const [activeFilter, setActiveFilter] = useState<FilterKey>('all')

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
        body: JSON.stringify({ yc_limit: 20, score_limit: 30, top_n: 10 }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setPipelineMsg(
        `Done — ${data.total_scored} scored, ${data.shortlist_count} shortlisted · ${data.scrape_summary?.total_fetched ?? 0} fetched, ${data.scrape_summary?.new_written ?? '?'} new, ${data.scrape_summary?.location_filtered ?? 0} location-filtered`
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
  }

  function handleSelectJob(job: Job) {
    setSelectedJob(job)
    setMobileView('chat')
  }

  // Counts for header pills
  const pursue   = jobs.filter((j) => j.recommendation === 'pursue').length
  const review   = jobs.filter((j) => j.recommendation === 'review').length
  const approved = jobs.filter((j) => j.status === 'approved').length
  const bypass   = jobs.filter((j) => j.recommendation === 'bypass').length

  // Filtered job list
  const filteredJobs = jobs.filter((j) => {
    if (activeFilter === 'all')      return true
    if (activeFilter === 'pursue')   return j.recommendation === 'pursue'
    if (activeFilter === 'review')   return j.recommendation === 'review'
    if (activeFilter === 'bypass')   return j.recommendation === 'bypass'
    if (activeFilter === 'approved') return j.status === 'approved'
    return true
  })

  const filterCounts: Record<FilterKey, number> = { all: jobs.length, pursue, review, bypass, approved }

  return (
    <div className="flex h-screen flex-col bg-[#060c14] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/15 via-[#060c14] to-black text-slate-100 overflow-hidden relative">
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay pointer-events-none" />

      {/* Ambient background glow */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />
      <div className="absolute bottom-1/3 right-1/4 w-[28rem] h-[28rem] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />

      {/* Header */}
      <div className="border-b border-white/5 bg-white/[0.01] backdrop-blur-2xl px-4 sm:px-5 py-3 flex-shrink-0 z-10 relative shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-500/10 border border-blue-500/20">
              <Zap size={15} className="text-blue-400" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-100">JobRadar</div>
              <div className="text-[10px] text-zinc-500">Magnio Job Intelligence</div>
            </div>

            {/* Stats pills */}
            <div className="hidden sm:flex items-center gap-1.5 ml-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 text-[11px] font-medium text-emerald-300">
                <span className="font-bold">{pursue}</span> pursue
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 text-[11px] font-medium text-amber-300">
                <span className="font-bold">{review}</span> review
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 text-[11px] font-medium text-blue-300">
                <span className="font-bold">{approved}</span> approved
              </span>
            </div>
          </div>

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
              <span className="hidden sm:inline">Refresh</span>
            </button>
            <button
              onClick={runPipeline}
              disabled={pipelineRunning}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 transition-colors disabled:opacity-60"
            >
              {pipelineRunning ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
              <span className="hidden sm:inline">Run Pipeline</span>
            </button>
          </div>
        </div>
      </div>

      {/* Body: split panel */}
      <div className="flex flex-1 min-h-0 overflow-hidden relative z-10">

        {/* Left panel — hidden on mobile when chat is open */}
        <div className={`${mobileView === 'chat' ? 'hidden sm:flex' : 'flex'} w-full sm:w-[42%] lg:w-[38%] border-r border-white/5 bg-black/20 backdrop-blur-md flex-col min-h-0 flex-shrink-0 shadow-[4px_0_24px_rgba(0,0,0,0.2)]`}>

          {/* Filter chips */}
          <div className="flex items-center gap-1.5 px-3 py-2.5 border-b border-white/5 overflow-x-auto flex-shrink-0">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setActiveFilter(f.key)}
                className={`flex-shrink-0 rounded-full border px-3 py-1 text-[11px] font-medium transition-all ${
                  activeFilter === f.key
                    ? f.activeColor
                    : 'text-zinc-500 border-zinc-700/60 hover:border-zinc-600/60 hover:text-zinc-300 bg-transparent'
                }`}
              >
                {f.label}
                <span className="ml-1 opacity-60">{filterCounts[f.key]}</span>
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 flex-shrink-0">
            <span className="text-xs text-zinc-500">{filteredJobs.length} jobs</span>
            {error && <span className="text-xs text-red-400">{error}</span>}
          </div>

          <div className="flex-1 overflow-y-auto p-3">
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

            {!loading && filteredJobs.length === 0 && jobs.length > 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-center gap-2">
                <div className="text-xs font-medium text-zinc-500">No jobs match this filter</div>
                <button
                  onClick={() => setActiveFilter('all')}
                  className="text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
                >
                  Show all
                </button>
              </div>
            )}

            <div className="space-y-2">
              {filteredJobs.map((job, i) => (
                <JobCard
                  key={`${activeFilter}-${job.id}`}
                  job={job}
                  index={i}
                  selected={selectedJob?.id === job.id}
                  onClick={() => handleSelectJob(job)}
                  onStatusChange={(s) => handleJobStatusChange(job.id, s)}
                  token={token}
                  dimWhenBypassed={activeFilter !== 'bypass'}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Right panel — hidden on mobile when list is shown */}
        <div className={`${mobileView === 'list' ? 'hidden sm:flex' : 'flex'} flex-1 min-w-0 flex-col min-h-0`}>
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
                  onBack={() => setMobileView('list')}
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
