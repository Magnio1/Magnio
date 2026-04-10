import { startTransition, useEffect, useReducer } from 'react'

import {
  askMagnioChat,
  getMagnioChatAnalyticsSummary,
  getMagnioChatHealth,
  getRecentMagnioEvaluationCases,
  streamMagnioChat,
  submitMagnioChatFeedback,
} from './api'
import { STORAGE_KEY } from './constants'
import type {
  CandidateResult,
  ChatAnalyticsSummary,
  ChatFeedbackState,
  ChatFeedbackVote,
  ChatHealth,
  ChatMessage,
  ChatMode,
  ChatResponse,
  ChatStreamEvent,
  RecentEvaluationCase,
} from './types'
import { isAssistantMessage } from './types'
import { createId } from './utils'

type ChatEngineState = {
  messages: ChatMessage[]
  query: string
  mode: ChatMode
  isLoading: boolean
  error: string
  health: ChatHealth | null
  healthError: string
  analyticsSummary: ChatAnalyticsSummary | null
  analyticsError: string
  recentCases: RecentEvaluationCase[]
  recentCasesError: string
  recentCasesLoading: boolean
}

type PersistedChatState = Pick<ChatEngineState, 'messages' | 'mode' | 'query'>

type ChatEngineAction =
  | {
      type: 'hydrate'
      payload: PersistedChatState
    }
  | {
      type: 'sidebar_success'
      payload: {
        health: ChatHealth
        analyticsSummary: ChatAnalyticsSummary
        recentCases: RecentEvaluationCase[]
      }
    }
  | { type: 'sidebar_error'; payload: string }
  | {
      type: 'refresh_success'
      payload: {
        analyticsSummary: ChatAnalyticsSummary
        recentCases: RecentEvaluationCase[]
      }
    }
  | { type: 'refresh_error'; payload: string }
  | { type: 'set_query'; payload: string }
  | { type: 'set_mode'; payload: ChatMode }
  | { type: 'load_case'; payload: { query: string; mode?: ChatMode } }
  | {
      type: 'stream_start'
      payload: {
        userMessage: ChatMessage
        assistantMessage: ChatMessage
        mode: ChatMode
      }
    }
  | {
      type: 'stream_event'
      payload: {
        assistantId: string
        event: ChatStreamEvent
      }
    }
  | {
      type: 'submit_error'
      payload: {
        assistantId: string
        error: string
      }
    }
  | {
      type: 'feedback_success'
      payload: {
        runId: string
        feedback: ChatFeedbackState
      }
    }
  | { type: 'clear_messages' }
  | { type: 'load_session'; payload: { messages: ChatMessage[]; mode: ChatMode } }

const INITIAL_STATE: ChatEngineState = {
  messages: [],
  query: '',
  mode: 'auto',
  isLoading: false,
  error: '',
  health: null,
  healthError: '',
  analyticsSummary: null,
  analyticsError: '',
  recentCases: [],
  recentCasesError: '',
  recentCasesLoading: true,
}

function createStreamingResponse(mode: ChatMode): ChatResponse {
  return {
    requestedMode: mode,
    resolvedMode: 'advisor',
    answer: '',
    topic: {
      id: mode === 'arena' ? 'arena' : 'advisor',
      label: mode === 'arena' ? 'Arena' : 'Magnio Advisor',
    },
    retrieval: [],
    candidates: [],
    judge: null,
    diagnostics: {
      strategy: mode === 'arena' ? 'Category-ranked arena with judge synthesis' : 'Hybrid advisor RAG',
      advisorModelId: null,
      selectedModels: [],
    },
    warnings: [],
    structuredAnswer: null,
    runId: null,
    latencyMs: 0,
    feedback: null,
    isStreaming: true,
    streamingPhase: 'queued',
  }
}

function upsertCandidate(candidates: CandidateResult[], nextCandidate: CandidateResult): CandidateResult[] {
  const existingIndex = candidates.findIndex((candidate) => candidate.modelId === nextCandidate.modelId)
  if (existingIndex === -1) {
    return [...candidates, nextCandidate]
  }

  return candidates.map((candidate, index) =>
    index === existingIndex ? nextCandidate : candidate,
  )
}

function updateAssistantResponse(
  state: ChatEngineState,
  assistantId: string,
  update: (response: ChatResponse) => ChatResponse,
): ChatEngineState {
  return {
    ...state,
    messages: state.messages.map((message) => {
      if (!isAssistantMessage(message) || message.id !== assistantId) return message
      return {
        ...message,
        response: update(message.response),
      }
    }),
  }
}

function reducer(state: ChatEngineState, action: ChatEngineAction): ChatEngineState {
  switch (action.type) {
    case 'hydrate':
      return {
        ...state,
        ...action.payload,
      }
    case 'sidebar_success':
      return {
        ...state,
        health: action.payload.health,
        healthError: '',
        analyticsSummary: action.payload.analyticsSummary,
        analyticsError: '',
        recentCases: action.payload.recentCases,
        recentCasesError: '',
        recentCasesLoading: false,
      }
    case 'sidebar_error':
      return {
        ...state,
        healthError: action.payload,
        analyticsError: action.payload,
        recentCasesError: action.payload,
        recentCasesLoading: false,
      }
    case 'refresh_success':
      return {
        ...state,
        analyticsSummary: action.payload.analyticsSummary,
        analyticsError: '',
        recentCases: action.payload.recentCases,
        recentCasesError: '',
        recentCasesLoading: false,
      }
    case 'refresh_error':
      return {
        ...state,
        analyticsError: action.payload,
        recentCasesError: action.payload,
        recentCasesLoading: false,
      }
    case 'set_query':
      return {
        ...state,
        query: action.payload,
      }
    case 'set_mode':
      return {
        ...state,
        mode: action.payload,
      }
    case 'load_case':
      return {
        ...state,
        query: action.payload.query,
        mode: action.payload.mode ?? state.mode,
      }
    case 'stream_start':
      return {
        ...state,
        messages: [
          ...state.messages,
          action.payload.userMessage,
          action.payload.assistantMessage,
        ],
        mode: action.payload.mode,
        query: '',
        error: '',
        isLoading: true,
      }
    case 'stream_event': {
      const { assistantId, event } = action.payload

      if (event.type === 'started') {
        return updateAssistantResponse(state, assistantId, (response) => ({
          ...response,
          requestedMode: event.requestedMode,
          resolvedMode: event.resolvedMode,
          topic: event.topic ?? response.topic,
          diagnostics: event.diagnostics ?? response.diagnostics,
          streamingPhase: 'started',
        }))
      }

      if (event.type === 'status') {
        return updateAssistantResponse(state, assistantId, (response) => ({
          ...response,
          streamingPhase: event.phase,
        }))
      }

      if (event.type === 'retrieval') {
        return updateAssistantResponse(state, assistantId, (response) => ({
          ...response,
          retrieval: event.items,
          streamingPhase: response.streamingPhase ?? 'retrieval',
        }))
      }

      if (event.type === 'candidate') {
        return updateAssistantResponse(state, assistantId, (response) => ({
          ...response,
          candidates: upsertCandidate(response.candidates, event.candidate),
          streamingPhase: response.streamingPhase ?? 'candidates',
        }))
      }

      if (event.type === 'answer_delta') {
        return updateAssistantResponse(state, assistantId, (response) => ({
          ...response,
          answer: `${response.answer}${event.text}`,
          streamingPhase: 'generation',
        }))
      }

      if (event.type === 'complete') {
        return updateAssistantResponse(
          {
            ...state,
            isLoading: false,
          },
          assistantId,
          () => ({
            ...event.response,
            isStreaming: false,
            streamingPhase: null,
          }),
        )
      }

      return state
    }
    case 'submit_error': {
      const nextMessages = state.messages.flatMap((message) => {
        if (!isAssistantMessage(message) || message.id !== action.payload.assistantId) {
          return [message]
        }

        const hasVisibleContent =
          message.response.answer.trim() ||
          message.response.retrieval.length ||
          message.response.candidates.length

        if (!hasVisibleContent) {
          return []
        }

        return [
          {
            ...message,
            response: {
              ...message.response,
              isStreaming: false,
              streamingPhase: 'error',
            },
          },
        ]
      })

      return {
        ...state,
        messages: nextMessages,
        error: action.payload.error,
        isLoading: false,
      }
    }
    case 'feedback_success':
      return {
        ...state,
        messages: state.messages.map((message) => {
          if (!isAssistantMessage(message)) return message
          if (message.response.runId !== action.payload.runId) return message
          return {
            ...message,
            response: {
              ...message.response,
              feedback: action.payload.feedback,
            },
          }
        }),
      }
    case 'clear_messages':
      return {
        ...state,
        messages: [],
        query: '',
        error: '',
      }
    case 'load_session':
      return {
        ...state,
        messages: action.payload.messages,
        mode: action.payload.mode,
        query: '',
        error: '',
      }
    default:
      return state
  }
}

function readPersistedState(): PersistedChatState | null {
  if (typeof window === 'undefined') return null

  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null

    const parsed = JSON.parse(raw) as Partial<PersistedChatState>
    if (!Array.isArray(parsed.messages)) return null
    return {
      messages: parsed.messages,
      mode:
        parsed.mode === 'arena' || parsed.mode === 'advisor' || parsed.mode === 'auto'
          ? parsed.mode
          : 'auto',
      query: typeof parsed.query === 'string' ? parsed.query : '',
    }
  } catch {
    return null
  }
}

function persistState(state: PersistedChatState) {
  if (typeof window === 'undefined') return

  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Ignore storage failures and keep the live session usable.
  }
}

function shouldFallbackToNonStreaming(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err ?? '')
  return (
    message === 'The chat request failed. Please try again.' ||
    /HTTP 5\d\d\b/.test(message) ||
    /Failed to fetch/i.test(message) ||
    /NetworkError/i.test(message) ||
    /Load failed/i.test(message)
  )
}

export function useChatEngine() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE)

  useEffect(() => {
    document.title = 'Magnio Chat'

    const persisted = readPersistedState()
    if (persisted) {
      dispatch({ type: 'hydrate', payload: persisted })
    }

    let cancelled = false

    Promise.all([
      getMagnioChatHealth(),
      getMagnioChatAnalyticsSummary(),
      getRecentMagnioEvaluationCases(12),
    ])
      .then(([healthPayload, analyticsPayload, recentCasesPayload]) => {
        if (!cancelled) {
          dispatch({
            type: 'sidebar_success',
            payload: {
              health: healthPayload,
              analyticsSummary: analyticsPayload,
              recentCases: recentCasesPayload.cases,
            },
          })
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          dispatch({ type: 'sidebar_error', payload: err.message })
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    persistState({
      messages: state.messages.filter(
        (message) => !isAssistantMessage(message) || !message.response.isStreaming,
      ),
      mode: state.mode,
      query: state.query,
    })
  }, [state.messages, state.mode, state.query])

  async function refreshAnalyticsSummary() {
    try {
      const [summary, recentCasesPayload] = await Promise.all([
        getMagnioChatAnalyticsSummary(),
        getRecentMagnioEvaluationCases(12),
      ])
      dispatch({
        type: 'refresh_success',
        payload: {
          analyticsSummary: summary,
          recentCases: recentCasesPayload.cases,
        },
      })
    } catch (err) {
      dispatch({
        type: 'refresh_error',
        payload: err instanceof Error ? err.message : 'Unable to load chat analytics.',
      })
    }
  }

  function loadCase(item: RecentEvaluationCase) {
    let nextMode: ChatMode | undefined

    if (
      item.requestedMode === 'auto' ||
      item.requestedMode === 'arena' ||
      item.requestedMode === 'advisor'
    ) {
      nextMode = item.requestedMode
    } else if (item.resolvedMode === 'arena' || item.resolvedMode === 'advisor') {
      nextMode = item.resolvedMode
    }

    dispatch({
      type: 'load_case',
      payload: {
        query: item.query ?? item.queryPreview,
        mode: nextMode,
      },
    })
  }

  async function submitPrompt(nextQuery?: string, nextMode?: ChatMode) {
    const resolvedQuery = (nextQuery ?? state.query).trim()
    const resolvedMode = nextMode ?? state.mode

    if (!resolvedQuery || state.isLoading) return

    const userMessage: ChatMessage = {
      id: createId(),
      role: 'user',
      content: resolvedQuery,
    }
    const assistantId = createId()
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      response: createStreamingResponse(resolvedMode),
    }

    startTransition(() => {
      dispatch({
        type: 'stream_start',
        payload: {
          userMessage,
          assistantMessage,
          mode: resolvedMode,
        },
      })
    })

    try {
      await streamMagnioChat(resolvedQuery, resolvedMode, (event) => {
        if (event.type === 'complete') {
          startTransition(() => {
            dispatch({
              type: 'stream_event',
              payload: {
                assistantId,
                event,
              },
            })
          })
          void refreshAnalyticsSummary()
          return
        }

        if (event.type === 'error') {
          throw new Error(event.detail)
        }

        startTransition(() => {
          dispatch({
            type: 'stream_event',
            payload: {
              assistantId,
              event,
            },
          })
        })
      })
    } catch (err) {
      if (shouldFallbackToNonStreaming(err)) {
        try {
          const fallbackResponse = await askMagnioChat(resolvedQuery, resolvedMode)
          const recoveredResponse = {
            ...fallbackResponse,
            warnings: [
              ...(fallbackResponse.warnings ?? []),
              'Streaming transport failed, so Magnio recovered with a non-streamed response.',
            ],
          }
          startTransition(() => {
            dispatch({
              type: 'stream_event',
              payload: {
                assistantId,
                event: {
                  type: 'complete',
                  response: recoveredResponse,
                },
              },
            })
          })
          void refreshAnalyticsSummary()
          return
        } catch (fallbackErr) {
          dispatch({
            type: 'submit_error',
            payload: {
              assistantId,
              error:
                fallbackErr instanceof Error
                  ? fallbackErr.message
                  : err instanceof Error
                    ? err.message
                    : 'The chat request failed.',
            },
          })
          return
        }
      }

      dispatch({
        type: 'submit_error',
        payload: {
          assistantId,
          error: err instanceof Error ? err.message : 'The chat request failed.',
        },
      })
    }
  }

  async function submitFeedback(runId: string, vote: ChatFeedbackVote, note?: string) {
    const feedback = await submitMagnioChatFeedback(runId, vote, note)
    startTransition(() => {
      dispatch({
        type: 'feedback_success',
        payload: {
          runId,
          feedback,
        },
      })
    })
    void refreshAnalyticsSummary()
  }

  return {
    ...state,
    setQuery: (query: string) => dispatch({ type: 'set_query', payload: query }),
    setMode: (mode: ChatMode) => dispatch({ type: 'set_mode', payload: mode }),
    clearMessages: () => dispatch({ type: 'clear_messages' }),
    loadSession: (messages: ChatMessage[], mode: ChatMode) =>
      dispatch({ type: 'load_session', payload: { messages, mode } }),
    loadCase,
    submitPrompt,
    submitFeedback,
  }
}
