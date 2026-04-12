import { useEffect, useState } from 'react'
import {
  ChevronDown,
  DatabaseZap,
  Loader2,
  MessageSquareText,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

import MarkdownSurface from '../MarkdownSurface'
import type { ChatFeedbackVote, ChatResponse } from '../types'
import { getScoreForModel, formatLatency } from '../utils'
import CandidateCard from './CandidateCard'
import CopyButton from './CopyButton'
import FollowUpSuggestions from './FollowUpSuggestions'
import LatencyBar from './LatencyBar'
import RetrievalCard from './RetrievalCard'

function formatStreamingPhase(phase: string | null | undefined) {
  if (!phase) return 'Streaming response'

  switch (phase) {
    case 'queued':
      return 'Queueing response'
    case 'started':
      return 'Starting response'
    case 'retrieval':
      return 'Loading context'
    case 'analysis':
      return 'Analyzing evidence'
    case 'generation':
      return 'Streaming synthesis'
    case 'candidates':
      return 'Collecting candidate answers'
    case 'judge':
      return 'Scoring and synthesizing'
    case 'retry':
      return 'Retrying model pool'
    case 'error':
      return 'Stream interrupted'
    default:
      return 'Streaming response'
  }
}

function AssistantTurn({
  response,
  onFeedbackSubmitted,
  onRegenerate,
  onFollowUp,
}: {
  response: ChatResponse
  onFeedbackSubmitted: (runId: string, vote: ChatFeedbackVote, note?: string) => Promise<void>
  onRegenerate?: () => void
  onFollowUp?: (suggestion: string) => void
}) {
  const [note, setNote] = useState(response.feedback?.note ?? '')
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false)
  const [feedbackError, setFeedbackError] = useState('')
  const [collapsed, setCollapsed] = useState({ evalCase: false, candidates: false, retrieval: false })
  const isStreaming = response.isStreaming === true
  const showPostSynthesisPanels = !isStreaming
  const streamingPhaseLabel = formatStreamingPhase(response.streamingPhase)

  function toggleSection(section: keyof typeof collapsed) {
    setCollapsed((prev) => ({ ...prev, [section]: !prev[section] }))
  }

  useEffect(() => {
    setNote(response.feedback?.note ?? '')
  }, [response.feedback?.note, response.runId])

  async function handleVote(vote: ChatFeedbackVote) {
    if (!response.runId) return
    setIsSubmittingFeedback(true)
    setFeedbackError('')
    try {
      await onFeedbackSubmitted(response.runId, vote, vote === 'down' ? note : undefined)
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : 'Unable to submit feedback.')
    } finally {
      setIsSubmittingFeedback(false)
    }
  }

  async function handleNoteSave() {
    if (!response.runId || response.feedback?.vote !== 'down') return
    setIsSubmittingFeedback(true)
    setFeedbackError('')
    try {
      await onFeedbackSubmitted(response.runId, 'down', note)
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : 'Unable to save the note.')
    } finally {
      setIsSubmittingFeedback(false)
    }
  }

  return (
    <motion.article
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div className="rounded-[32px] border border-white/8 bg-white/[0.02] p-4 sm:p-6 shadow-xl backdrop-blur-2xl">
        <div className="flex flex-wrap items-center gap-3">
          <motion.span
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-1.5 text-[10px] font-bold uppercase tracking-[0.25em] text-cyan-300"
          >
            {response.resolvedMode}
          </motion.span>
          <span className="rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
            {response.topic.label}
          </span>
          <span className="hidden sm:inline-block rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400 max-w-[220px] truncate" title={response.diagnostics.strategy}>
            {response.diagnostics.strategy}
          </span>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="mt-4 sm:mt-6 rounded-[24px] border border-white/6 bg-[#050b12]/40 p-4 sm:p-6 shadow-inner"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-amber-400/15 bg-gradient-to-br from-amber-400/15 to-orange-500/5">
                <Sparkles className="h-4.5 w-4.5 text-amber-300" />
              </div>
              <h3 className="text-lg font-bold tracking-tight text-white">
                {isStreaming ? 'Synthesis in Progress' : 'Final Synthesis'}
              </h3>
            </div>
            <div className="flex items-center gap-2">
              {isStreaming ? (
                <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-200 max-w-[180px] sm:max-w-none">
                  <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
                  <span className="truncate">{streamingPhaseLabel}</span>
                </div>
              ) : null}
              {!isStreaming && response.answer ? (
                <CopyButton text={response.answer} />
              ) : null}
            </div>
          </div>
          <div className="mt-4 sm:mt-6">
            {isStreaming ? (
              <div className="rounded-[20px] border border-white/5 bg-black/20 px-5 py-4">
                <div className="whitespace-pre-wrap text-[15px] leading-7 text-slate-200">
                  {response.answer || 'Synthesizing answer from retrieved context...'}
                  <span className="ml-1 inline-block h-5 w-2 animate-pulse rounded-sm bg-cyan-300/70 align-[-0.15em]" />
                </div>
              </div>
            ) : (
              <MarkdownSurface content={response.answer} />
            )}
          </div>
        </motion.div>

        {showPostSynthesisPanels ? (
          <motion.section
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-4 sm:mt-6 rounded-[32px] border border-white/10 bg-black/30"
          >
            {/* Collapsible header */}
            <button
              type="button"
              onClick={() => toggleSection('evalCase')}
              className="flex w-full items-center justify-between gap-3 p-4 sm:p-6 text-left"
              aria-expanded={!collapsed.evalCase}
            >
              <div className="flex items-center gap-3">
                <MessageSquareText className="h-5 w-5 text-cyan-300" />
                <h3 className="text-lg font-bold tracking-tight text-white">Evaluation case</h3>
              </div>
              <motion.span animate={{ rotate: collapsed.evalCase ? -90 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown className="h-4 w-4 text-slate-400" />
              </motion.span>
            </button>

            <AnimatePresence initial={false}>
              {!collapsed.evalCase ? (
                <motion.div
                  key="evalCase-body"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.22, ease: 'easeOut' }}
                  className="overflow-hidden"
                >
                  <div className="px-4 pb-4 sm:px-6 sm:pb-6">
                    <p className="mb-4 text-sm font-medium leading-7 text-slate-400">
                      Track the route, selected perspective, timing, and operator review for this answer.
                    </p>
                    <div className="grid gap-3 grid-cols-2">
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
                        <div className="text-[9px] font-bold uppercase tracking-[0.3em] text-slate-500">case id</div>
                        <div className="mt-2 text-xs font-bold text-slate-200">
                          {response.runId ? response.runId.slice(0, 8) : 'not logged'}
                        </div>
                      </div>
                      <div className="col-span-2 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
                        <div className="text-[9px] font-bold uppercase tracking-[0.3em] text-slate-500 mb-2">latency</div>
                        <LatencyBar totalMs={response.latencyMs} candidates={response.candidates} />
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
                        <div className="text-[9px] font-bold uppercase tracking-[0.3em] text-slate-500">review</div>
                        <div className="mt-2 text-xs font-bold text-slate-200">
                          {response.feedback?.vote ? response.feedback.vote : 'pending'}
                        </div>
                      </div>
                    </div>

                    {response.runId ? (
                      <div className="mt-4 rounded-[28px] border border-white/10 bg-white/[0.02] p-5">
                        <div className="flex flex-wrap items-center justify-between gap-4">
                          <div>
                            <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-slate-500">
                              Operator review
                            </div>
                            <p className="mt-2 hidden sm:block text-sm font-medium leading-6 text-slate-400">
                              Mark whether the final answer is usable. Revisions can carry an optional review note.
                            </p>
                          </div>
                          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3 w-full sm:w-auto">
                            {onRegenerate ? (
                              <button
                                type="button"
                                onClick={onRegenerate}
                                className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm font-bold text-slate-200 transition hover:bg-white/[0.08] sm:w-auto sm:py-2"
                              >
                                <RefreshCw className="h-4 w-4" />
                                Regenerate
                              </button>
                            ) : null}
                            <div className="flex gap-2">
                              <button
                                type="button"
                                disabled={isSubmittingFeedback}
                                onClick={() => void handleVote('up')}
                                className={`inline-flex flex-1 items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-bold transition sm:flex-none sm:py-2 ${
                                  response.feedback?.vote === 'up'
                                    ? 'bg-emerald-400 text-slate-950'
                                    : 'border border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.08]'
                                }`}
                              >
                                <ThumbsUp className="h-4 w-4" />
                                Approve
                              </button>
                              <button
                                type="button"
                                disabled={isSubmittingFeedback}
                                onClick={() => void handleVote('down')}
                                className={`inline-flex flex-1 items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-bold transition sm:flex-none sm:py-2 ${
                                  response.feedback?.vote === 'down'
                                    ? 'bg-amber-300 text-slate-950'
                                    : 'border border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.08]'
                                }`}
                              >
                                <ThumbsDown className="h-4 w-4" />
                                Revision
                              </button>
                            </div>
                          </div>
                        </div>

                        {response.feedback?.vote === 'down' ? (
                          <div className="mt-5 space-y-3">
                            <label className="sr-only" htmlFor={`feedback-note-${response.runId}`}>
                              Revision note
                            </label>
                            <textarea
                              id={`feedback-note-${response.runId}`}
                              value={note}
                              onChange={(event) => setNote(event.target.value)}
                              placeholder="What was missing, off-target, or worth correcting?"
                              className="min-h-[96px] w-full resize-none rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-400/30"
                            />
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div className="text-xs font-medium text-slate-500">
                                {response.feedback?.updatedAt
                                  ? `Last saved ${response.feedback.updatedAt}`
                                  : 'No note saved yet.'}
                              </div>
                              <button
                                type="button"
                                disabled={isSubmittingFeedback}
                                onClick={() => void handleNoteSave()}
                                className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-bold text-slate-200 transition hover:bg-white/[0.08] disabled:opacity-50"
                              >
                                {isSubmittingFeedback ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                                Save note
                              </button>
                            </div>
                          </div>
                        ) : null}

                        {feedbackError ? (
                          <div className="mt-4 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                            {feedbackError}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </motion.section>
        ) : null}

        {showPostSynthesisPanels && response.candidates.length ? (
          <motion.section
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="group/verdict relative mt-4 sm:mt-6 overflow-hidden rounded-[28px] border border-white/8 bg-black/30 shadow-xl backdrop-blur-2xl"
          >
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-500/10 to-transparent" />
            {/* Collapsible header */}
            <button
              type="button"
              onClick={() => toggleSection('candidates')}
              className="relative flex w-full items-center justify-between gap-4 p-4 sm:p-7 text-left"
              aria-expanded={!collapsed.candidates}
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-400/15 bg-emerald-400/5">
                  <ShieldCheck className="h-4.5 w-4.5 text-emerald-400" />
                </div>
                <h3 className="text-lg font-bold tracking-tight text-white">
                  {response.judge ? 'Decision rationale' : 'Candidate perspectives'}
                </h3>
              </div>
              <div className="flex items-center gap-3">
                {response.judge ? (
                  <>
                    <div className="hidden sm:block rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-3 text-right shadow-sm">
                      <div className="text-[9px] font-bold uppercase tracking-[0.3em] text-slate-500">decision engine</div>
                      <div className="mt-1 text-xs font-bold tracking-widest text-cyan-300/80">
                        {response.judge.judgeModelId?.split('/').pop() ?? 'Judge'}
                      </div>
                    </div>
                    <div className="sm:hidden rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2.5 py-1 text-[9px] font-bold text-cyan-300/80 truncate max-w-[120px]" title={response.judge.judgeModelId ?? 'Judge'}>
                      {response.judge.judgeModelId?.split('/').pop() ?? 'Judge'}
                    </div>
                  </>
                ) : null}
                <motion.span animate={{ rotate: collapsed.candidates ? -90 : 0 }} transition={{ duration: 0.2 }}>
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                </motion.span>
              </div>
            </button>

            <AnimatePresence initial={false}>
              {!collapsed.candidates ? (
                <motion.div
                  key="candidates-body"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.22, ease: 'easeOut' }}
                  className="overflow-hidden"
                >
                  <div className="px-4 pb-4 sm:px-7 sm:pb-7">
                    <p className="mb-5 text-[14px] font-medium leading-[1.7] text-slate-400">
                      {response.judge?.rationale ||
                        'Arena candidates are arriving. Magnio will score them and synthesize the final answer when the judge completes.'}
                    </p>
                    <div className="grid items-start gap-3 sm:gap-5 sm:grid-cols-2 lg:grid-cols-3">
                      {response.candidates.map((candidate, idx) => (
                        <CandidateCard
                          key={candidate.modelId}
                          candidate={candidate}
                          winnerModelId={response.judge?.winnerModelId}
                          score={getScoreForModel(response.judge?.scores ?? [], candidate.modelId)}
                          index={idx}
                        />
                      ))}
                    </div>
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </motion.section>
        ) : null}

        {showPostSynthesisPanels && response.topic.reasoning?.length ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-4 sm:mt-6 rounded-3xl border border-white/10 bg-white/[0.02] px-4 sm:px-6 py-4 sm:py-5"
          >
            <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-slate-500">
              Routing rationale
            </div>
            <ul className="mt-3 space-y-2.5">
              {response.topic.reasoning.map((reason) => (
                <li key={reason} className="flex items-start gap-3 text-xs font-medium text-slate-400">
                  <div className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-500/30" />
                  {reason}
                </li>
              ))}
            </ul>
          </motion.div>
        ) : null}

        {showPostSynthesisPanels && response.warnings.length ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.55 }}
            className="mt-4 sm:mt-6 rounded-3xl border border-amber-500/20 bg-amber-500/10 px-4 sm:px-6 py-4 sm:py-5 text-sm leading-6 text-amber-100"
          >
            <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-amber-400/80">
              System Warnings
            </div>
            <ul className="mt-3 space-y-2">
              {response.warnings.map((warning) => (
                <li key={warning} className="flex items-start gap-3 text-xs font-medium">
                  <span className="text-amber-400">●</span>
                  {warning}
                </li>
              ))}
            </ul>
          </motion.div>
        ) : null}

        {showPostSynthesisPanels && response.retrieval.length ? (
          <motion.section
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mt-4 sm:mt-6 rounded-[24px] border border-white/8 bg-black/25"
          >
            {/* Collapsible header */}
            <button
              type="button"
              onClick={() => toggleSection('retrieval')}
              className="flex w-full items-center justify-between gap-3 p-4 sm:p-6 text-left"
              aria-expanded={!collapsed.retrieval}
            >
              <div className="flex items-center gap-3">
                <DatabaseZap className="h-5 w-5 text-cyan-400" />
                <h3 className="text-lg font-bold tracking-tight text-white">
                  Context Retrieval
                  <span className="ml-2 text-[11px] font-semibold text-slate-500">
                    {response.retrieval.length}
                  </span>
                </h3>
              </div>
              <motion.span animate={{ rotate: collapsed.retrieval ? -90 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown className="h-4 w-4 text-slate-400" />
              </motion.span>
            </button>

            <AnimatePresence initial={false}>
              {!collapsed.retrieval ? (
                <motion.div
                  key="retrieval-body"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.22, ease: 'easeOut' }}
                  className="overflow-hidden"
                >
                  <div className="grid gap-2 sm:gap-4 px-4 pb-4 sm:px-6 sm:pb-6 sm:grid-cols-2">
                    {response.retrieval.map((item, idx) => (
                      <RetrievalCard key={item.id} item={item} index={idx} />
                    ))}
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </motion.section>
        ) : null}

        {showPostSynthesisPanels && response.answer && onFollowUp ? (
          <div className="px-4 sm:px-6 pb-4 sm:pb-6">
            <FollowUpSuggestions
              answer={response.answer}
              topicLabel={response.topic.label}
              mode={response.requestedMode}
              onSelect={onFollowUp}
            />
          </div>
        ) : null}
      </div>
    </motion.article>
  )
}

export default AssistantTurn
