import { ArrowDown, ArrowLeft, Download, Loader2, PanelLeft, Search, Send, X } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  useDeferredValue,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react'

import MagnioLogo from '../components/MagnioLogo'
import AssistantTurn from './components/AssistantTurn'
import DesktopControlPanel from './components/DesktopControlPanel'
import EmptyState from './components/EmptyState'
import LoadingIndicator from './components/LoadingIndicator'
import MobileControlCenter from './components/MobileControlCenter'
import { ComposerModeButton } from './components/ModeControls'
import { MODE_OPTIONS } from './constants'
import { PROMPT_PRESETS } from './prompts'
import type { ChatMode } from './types'
import { isAssistantMessage, isUserMessage } from './types'
import { exportToMarkdown, triggerMarkdownDownload } from './utils'
import { useChatEngine } from './useChatEngine'
import { useConversationHistory } from './hooks/useConversationHistory'

const PROMPT_HISTORY_KEY = 'magnio-prompt-history'
const PROMPT_HISTORY_MAX = 50

function readPromptHistory(): string[] {
  try {
    const raw = localStorage.getItem(PROMPT_HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? (parsed as string[]) : []
  } catch {
    return []
  }
}

function savePromptHistory(history: string[]) {
  try {
    localStorage.setItem(PROMPT_HISTORY_KEY, JSON.stringify(history.slice(0, PROMPT_HISTORY_MAX)))
  } catch {
    // Ignore storage failures
  }
}

function ChatPage() {
  const {
    messages,
    query,
    mode,
    isLoading,
    error,
    health,
    healthError,
    analyticsSummary,
    analyticsError,
    recentCases,
    recentCasesError,
    recentCasesLoading,
    setQuery,
    setMode,
    clearMessages,
    loadSession: engineLoadSession,
    loadCase,
    submitPrompt,
    submitFeedback,
  } = useChatEngine()

  const {
    sessions,
    currentSessionId,
    saveSession,
    loadSession: historyLoadSession,
    deleteSession,
    newSession,
  } = useConversationHistory()

  // Auto-save completed messages to session history
  useEffect(() => {
    const completed = messages.filter(
      (m) => !isAssistantMessage(m) || !m.response.isStreaming,
    )
    if (completed.length > 0) {
      saveSession(completed, mode)
    }
  }, [messages, mode, saveSession])

  const [isDesktopPanelOpen, setIsDesktopPanelOpen] = useState(false)
  const [isMobileControlOpen, setIsMobileControlOpen] = useState(false)
  const [promptSearch, setPromptSearch] = useState('')

  const deferredPromptSearch = useDeferredValue(promptSearch)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const contentRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const shouldStickToBottomRef = useRef(true)
  const wasLoadingRef = useRef(isLoading)
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)
  const [promptHistory, setPromptHistory] = useState<string[]>(readPromptHistory)
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchOpen, setIsSearchOpen] = useState(false)

  const hasStreamingAssistant = messages.some(
    (message) => isAssistantMessage(message) && message.response.isStreaming,
  )

  function isNearBottom(container: HTMLDivElement) {
    return container.scrollHeight - container.scrollTop - container.clientHeight < 120
  }

  // ResizeObserver-based auto-scroll: fires whenever inner content grows
  useEffect(() => {
    const content = contentRef.current
    const container = scrollContainerRef.current
    if (!content || !container) return

    const observer = new ResizeObserver(() => {
      if (!shouldStickToBottomRef.current) return
      const behavior = hasStreamingAssistant ? 'instant' : 'smooth'
      container.scrollTo({ top: container.scrollHeight, behavior })
    })

    observer.observe(content)
    return () => observer.disconnect()
  }, [hasStreamingAssistant])

  useLayoutEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 132), 260)
    textarea.style.height = `${nextHeight}px`
  }, [query])

  useEffect(() => {
    if (wasLoadingRef.current && !isLoading) {
      requestAnimationFrame(() => textareaRef.current?.focus())
    }
    wasLoadingRef.current = isLoading
  }, [isLoading])

  useEffect(() => {
    function onGlobalKeyDown(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key === 'f') {
        event.preventDefault()
        setIsSearchOpen((prev) => {
          if (prev) setSearchQuery('')
          return !prev
        })
      }
      if (event.key === 'Escape') {
        setSearchQuery('')
        setIsSearchOpen(false)
      }
    }
    document.addEventListener('keydown', onGlobalKeyDown)
    return () => document.removeEventListener('keydown', onGlobalKeyDown)
  }, [])

  const filteredPresets = PROMPT_PRESETS.filter((preset) => {
    const normalized = deferredPromptSearch.trim().toLowerCase()
    if (!normalized) return true

    const haystack =
      `${preset.title} ${preset.description} ${preset.prompt} ${preset.mode}`.toLowerCase()
    return haystack.includes(normalized)
  })

  const activeModeOption = MODE_OPTIONS.find((option) => option.value === mode) ?? MODE_OPTIONS[0]
  const queryWordCount = query.trim() ? query.trim().split(/\s+/).filter(Boolean).length : 0

  const searchQueryNorm = searchQuery.trim().toLowerCase()
  const filteredMessages = searchQueryNorm
    ? messages.filter((message) => {
        if (isAssistantMessage(message)) {
          return message.response.answer?.toLowerCase().includes(searchQueryNorm)
        }
        return message.content.toLowerCase().includes(searchQueryNorm)
      })
    : messages
  function handleMessagesScroll() {
    const container = scrollContainerRef.current
    if (!container) return
    const nearBottom = isNearBottom(container)
    shouldStickToBottomRef.current = nearBottom
    setShowScrollToBottom(!nearBottom && messages.length > 0)
  }

  function handleScrollToBottom() {
    const container = scrollContainerRef.current
    if (!container) return
    shouldStickToBottomRef.current = true
    setShowScrollToBottom(false)
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
  }

  async function handleSubmitPrompt(prompt?: string, nextMode?: ChatMode) {
    shouldStickToBottomRef.current = true
    const submitted = (prompt ?? query).trim()
    if (submitted) {
      const newHistory = [submitted, ...promptHistory.filter((h) => h !== submitted)].slice(0, PROMPT_HISTORY_MAX)
      setPromptHistory(newHistory)
      savePromptHistory(newHistory)
      setHistoryIndex(-1)
    }
    await submitPrompt(prompt, nextMode)
  }

  function handleExport() {
    const markdown = exportToMarkdown(messages)
    const date = new Date().toISOString().slice(0, 10)
    triggerMarkdownDownload(markdown, `magnio-chat-${date}.md`)
  }

  function handlePresetSelect(prompt: string, nextMode: ChatMode) {
    setIsDesktopPanelOpen(false)
    setIsMobileControlOpen(false)
    void handleSubmitPrompt(prompt, nextMode)
  }

  function handleLoadCase(item: (typeof recentCases)[number]) {
    loadCase(item)
    setIsDesktopPanelOpen(false)
    setIsMobileControlOpen(false)
    shouldStickToBottomRef.current = true
    requestAnimationFrame(() => textareaRef.current?.focus())
  }

  function handleLoadSession(session: Parameters<typeof historyLoadSession>[0]) {
    const { messages: sessionMessages, mode: sessionMode } = historyLoadSession(session)
    engineLoadSession(sessionMessages, sessionMode)
    setIsDesktopPanelOpen(false)
    setIsMobileControlOpen(false)
    shouldStickToBottomRef.current = true
    requestAnimationFrame(() => textareaRef.current?.focus())
  }

  function handleNewSession() {
    newSession()
    clearMessages()
    setIsDesktopPanelOpen(false)
    setIsMobileControlOpen(false)
    requestAnimationFrame(() => textareaRef.current?.focus())
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void handleSubmitPrompt()
      return
    }

    if (event.key === 'ArrowUp') {
      const textarea = textareaRef.current
      if (!textarea) return
      const firstNewline = textarea.value.indexOf('\n')
      const firstLineEnd = firstNewline === -1 ? textarea.value.length : firstNewline
      if (textarea.selectionStart > firstLineEnd) return
      event.preventDefault()
      const nextIndex = Math.min(historyIndex + 1, promptHistory.length - 1)
      if (nextIndex >= 0 && promptHistory[nextIndex] !== undefined) {
        setHistoryIndex(nextIndex)
        setQuery(promptHistory[nextIndex])
      }
      return
    }

    if (event.key === 'ArrowDown' && historyIndex >= 0) {
      event.preventDefault()
      const nextIndex = historyIndex - 1
      setHistoryIndex(nextIndex)
      setQuery(nextIndex < 0 ? '' : (promptHistory[nextIndex] ?? ''))
      return
    }

    if (historyIndex !== -1 && event.key !== 'ArrowDown') {
      setHistoryIndex(-1)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#03070b] text-slate-100">
      <div className="pointer-events-none fixed inset-0 z-0">
        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.15, 0.25, 0.15] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute -top-24 left-1/4 h-[500px] w-[500px] rounded-full bg-cyan-500/20 blur-[120px]"
        />
        <motion.div
          animate={{ scale: [1, 1.3, 1], opacity: [0.1, 0.2, 0.1] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
          className="absolute top-1/2 -right-24 h-[600px] w-[600px] rounded-full bg-emerald-400/15 blur-[140px]"
        />
        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.05, 0.15, 0.05] }}
          transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
          className="absolute -bottom-24 left-1/3 h-[450px] w-[450px] rounded-full bg-amber-300/10 blur-[100px]"
        />
      </div>

      <header className="sticky top-0 z-50 border-b border-white/10 bg-black/40 backdrop-blur-3xl">
        <div className="magnio-container flex h-14 sm:h-20 items-center justify-between">
          <div className="flex items-center gap-4">
            <motion.a
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              href="/"
              className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/[0.05] px-3 py-2 transition hover:bg-white/[0.08]"
            >
              <MagnioLogo size="small" />
            </motion.a>
            <div className="hidden sm:block">
              <div className="text-[10px] font-bold uppercase tracking-[0.4em] text-cyan-400/60">
                Agentic Showcase
              </div>
              <div className="text-sm font-medium text-slate-300">
                Multi-model arena + hybrid advisor
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <motion.button
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={() => setIsDesktopPanelOpen(true)}
              className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08] xl:inline-flex"
            >
              <PanelLeft className="h-4 w-4" />
              Panel
            </motion.button>
            {messages.length > 0 && (
              <>
                <motion.button
                  whileHover={{ y: -1 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  onClick={() => setIsSearchOpen((prev) => !prev)}
                  aria-label="Search conversation"
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08] sm:px-4"
                >
                  <Search className="h-4 w-4" />
                  <span className="hidden sm:inline">Search</span>
                </motion.button>
                <motion.button
                  whileHover={{ y: -1 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  onClick={handleExport}
                  aria-label="Export conversation"
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08] sm:px-4"
                >
                  <Download className="h-4 w-4" />
                  <span className="hidden sm:inline">Export</span>
                </motion.button>
              </>
            )}
            <motion.a
              whileHover={{ x: -2 }}
              href="/"
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
            >
              <ArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">Home</span>
            </motion.a>
          </div>
        </div>
        <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent" />
      </header>

      <AnimatePresence>
        {isDesktopPanelOpen ? (
          <>
            <motion.button
              type="button"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsDesktopPanelOpen(false)}
              className="fixed inset-0 z-40 hidden bg-black/30 backdrop-blur-md xl:block"
              aria-label="Close drawer overlay"
            />
            <motion.aside
              initial={{ x: -28, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -28, opacity: 0 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
              className="fixed bottom-6 left-6 top-28 z-50 hidden w-[320px] overflow-hidden rounded-[32px] border border-white/8 bg-black/20 shadow-2xl backdrop-blur-3xl xl:flex xl:flex-col"
            >
              <div className="flex items-center justify-between border-b border-white/5 px-6 py-5">
                <div>
                  <div className="text-[9px] font-bold uppercase tracking-[0.3em] text-cyan-300/60">
                    Control Panel
                  </div>
                  <div className="mt-1 text-xs font-semibold text-white">Engine parameters</div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsDesktopPanelOpen(false)}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-slate-300 transition hover:bg-white/[0.08] hover:text-white"
                  aria-label="Close desktop panel"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="custom-scrollbar flex-1 overflow-y-auto p-5">
                <DesktopControlPanel
                  mode={mode}
                  onModeChange={setMode}
                  health={health}
                  healthError={healthError}
                  analyticsSummary={analyticsSummary}
                  analyticsError={analyticsError}
                  promptSearch={promptSearch}
                  onPromptSearchChange={setPromptSearch}
                  filteredPresets={filteredPresets}
                  onPreset={handlePresetSelect}
                  sessions={sessions}
                  currentSessionId={currentSessionId}
                  onLoadSession={handleLoadSession}
                  onDeleteSession={deleteSession}
                  onNewSession={handleNewSession}
                />
              </div>
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>

      <main className="magnio-container relative z-10 py-6 sm:py-10">
        <div className="grid gap-6">
          <section className="order-1 relative flex min-h-0 flex-col overflow-hidden rounded-[28px] border border-white/10 bg-black/40 shadow-[0_40px_120px_rgba(0,0,0,0.4)] backdrop-blur-2xl sm:min-h-[82vh] sm:rounded-none sm:border-0 sm:bg-transparent sm:shadow-none sm:backdrop-blur-0">
            <div className="border-b border-white/8 bg-white/[0.02] p-4 xl:hidden">
              <MobileControlCenter
                open={isMobileControlOpen}
                onToggle={() => setIsMobileControlOpen((current) => !current)}
                health={health}
                healthError={healthError}
                analyticsSummary={analyticsSummary}
                analyticsError={analyticsError}
                recentCases={recentCases}
                recentCasesError={recentCasesError}
                recentCasesLoading={recentCasesLoading}
                promptSearch={promptSearch}
                onPromptSearchChange={setPromptSearch}
                quickPresets={PROMPT_PRESETS.slice(0, 4)}
                filteredPresets={filteredPresets}
                onPreset={handlePresetSelect}
                onLoadCase={handleLoadCase}
                sessions={sessions}
                currentSessionId={currentSessionId}
                onLoadSession={handleLoadSession}
                onDeleteSession={deleteSession}
                onNewSession={handleNewSession}
              />
            </div>

            <div className="relative" style={{ display: 'flex', flexDirection: 'column', flex: '1 1 0%', minHeight: 0 }}>
              <AnimatePresence>
                {isSearchOpen && (
                  <motion.div
                    key="search-bar"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden border-b border-white/5 bg-black/20 px-4 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <Search className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                      <input
                        autoFocus
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search messages…"
                        className="flex-1 bg-transparent text-sm font-medium text-slate-200 outline-none placeholder:text-slate-500"
                      />
                      {searchQueryNorm && (
                        <span className="shrink-0 text-[10px] font-semibold text-slate-400">
                          {filteredMessages.length} match{filteredMessages.length !== 1 ? 'es' : ''}
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => { setSearchQuery(''); setIsSearchOpen(false) }}
                        className="shrink-0 text-slate-500 transition hover:text-slate-300"
                        aria-label="Close search"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div
                ref={scrollContainerRef}
                onScroll={handleMessagesScroll}
                className="custom-scrollbar flex-1 overflow-y-auto p-4 sm:px-0 sm:pb-8 sm:pt-2"
              >
                <div ref={contentRef} className="space-y-6 sm:space-y-8">
                  <AnimatePresence>
                    {!messages.length ? (
                      <motion.div
                        key="empty"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                      >
                        <EmptyState onPreset={handlePresetSelect} />
                      </motion.div>
                    ) : (
                      filteredMessages.map((message) =>
                        isAssistantMessage(message) ? (
                          <AssistantTurn
                            key={message.id}
                            response={message.response}
                            onFeedbackSubmitted={submitFeedback}
                            onFollowUp={(suggestion) => {
                              setQuery(suggestion)
                              void handleSubmitPrompt(suggestion)
                            }}
                            onRegenerate={(() => {
                              const idx = messages.indexOf(message)
                              for (let i = idx - 1; i >= 0; i--) {
                                const prev = messages[i]
                                if (isUserMessage(prev)) {
                                  return () => void handleSubmitPrompt(prev.content)
                                }
                              }
                              return undefined
                            })()}
                          />
                        ) : (
                          <motion.div
                            key={message.id}
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            className="flex justify-end"
                          >
                            <div className="max-w-2xl rounded-[18px] border border-white/5 bg-white/[0.03] px-4 py-2.5 shadow-md backdrop-blur-lg sm:rounded-[22px] sm:px-5 sm:py-3.5">
                              <p className="whitespace-pre-line text-[15px] font-medium leading-relaxed text-slate-100">
                                {message.content}
                              </p>
                            </div>
                          </motion.div>
                        ),
                      )
                    )}

                    {isLoading && !hasStreamingAssistant ? (
                      <motion.div key="loading" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <LoadingIndicator mode={mode} />
                      </motion.div>
                    ) : null}

                    {error ? (
                      <motion.div
                        key="error"
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="rounded-[28px] border border-rose-500/20 bg-rose-500/10 px-6 py-5 text-sm font-medium leading-7 text-rose-200"
                        role="alert"
                      >
                        <div className="mb-1 flex items-center gap-2">
                          <span className="font-bold text-rose-400">ERR:</span>
                          <span className="text-[10px] uppercase tracking-widest">
                            Pipeline Interruption
                          </span>
                        </div>
                        {error}
                      </motion.div>
                    ) : null}
                  </AnimatePresence>

                  <div className="h-4" />
                </div>
              </div>

              <AnimatePresence>
                {showScrollToBottom && (
                  <motion.button
                    key="scroll-to-bottom"
                    type="button"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.18 }}
                    onClick={handleScrollToBottom}
                    className="absolute bottom-4 left-1/2 z-20 -translate-x-1/2 inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-black/60 px-3.5 py-2 text-xs font-semibold text-slate-300 shadow-lg backdrop-blur-xl transition hover:border-white/20 hover:bg-black/80 hover:text-white"
                    aria-label="Scroll to bottom"
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                    New messages
                  </motion.button>
                )}
              </AnimatePresence>
            </div>

            <div
              className="border-t border-white/5 p-4 backdrop-blur-3xl sm:border-t-0 sm:bg-transparent sm:px-0 sm:pb-0 sm:pt-4 sm:backdrop-blur-0"
            >
              <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div
                  className="custom-scrollbar inline-flex max-w-full items-center gap-2.5 overflow-x-auto rounded-[32px] border border-white/6 bg-black/25 p-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
                  role="radiogroup"
                  aria-label="Composer mode"
                >
                  {MODE_OPTIONS.map((option) => (
                    <ComposerModeButton
                      key={`composer-${option.value}`}
                      option={option}
                      active={mode === option.value}
                      onClick={() => setMode(option.value)}
                    />
                  ))}
                </div>
                <div className="inline-flex items-center gap-2 self-start rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-300">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      health?.openrouterConfigured
                        ? 'bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.8)]'
                        : 'bg-amber-300 shadow-[0_0_18px_rgba(252,211,77,0.55)]'
                    }`}
                  />
                  {activeModeOption.eyebrow}
                </div>
              </div>

              <div className="group/composer relative overflow-hidden rounded-[42px] border border-white/5 bg-black/25 shadow-2xl backdrop-blur-2xl">
                <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.06),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(251,191,36,0.04),transparent_28%)]" />

                <div className="relative px-4 pb-4 pt-4 sm:px-5 sm:pb-5">
                  <div className="rounded-[32px] border border-white/5 bg-black/25 px-4 py-2.5 transition-all group-focus-within/composer:border-cyan-300/20 group-focus-within/composer:shadow-[0_0_0_1px_rgba(125,211,252,0.08)]">
                    <label className="sr-only" htmlFor="magnio-chat-query">
                      Ask Magnio a question
                    </label>
                    <textarea
                      id="magnio-chat-query"
                      ref={textareaRef}
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder={activeModeOption.placeholder}
                      aria-label="Ask Magnio a question"
                      aria-describedby="magnio-chat-composer-help"
                      className="custom-scrollbar min-h-[72px] max-h-[180px] w-full resize-none overflow-y-auto bg-transparent py-1.5 text-[15px] font-medium leading-7 text-white outline-none placeholder:text-slate-500/90 focus-visible:ring-0 focus-visible:ring-offset-0 sm:min-h-[88px] sm:max-h-[220px]"
                    />
                  </div>

                  <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div
                      id="magnio-chat-composer-help"
                      className="flex flex-wrap items-center gap-3 text-xs font-medium text-slate-500"
                    >
                      <span>{queryWordCount ? `${queryWordCount} words` : 'Enter sends'}</span>
                      <span className="h-1 w-1 rounded-full bg-white/10" />
                      <span>Shift + Enter for a line break</span>
                    </div>
                    <motion.button
                      whileHover={{ scale: 1.02, y: -1 }}
                      whileTap={{ scale: 0.98 }}
                      type="button"
                      disabled={isLoading || !query.trim()}
                      onClick={() => void handleSubmitPrompt()}
                      className="inline-flex w-full items-center justify-center gap-2.5 rounded-[18px] bg-[linear-gradient(135deg,#ecfeff,#67e8f9_45%,#34d399)] px-5 py-3 text-sm font-bold text-slate-950 shadow-lg transition hover:shadow-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none lg:w-auto lg:min-w-[168px]"
                    >
                      {isLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                      <span>{activeModeOption.actionLabel}</span>
                    </motion.button>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}

export default ChatPage
