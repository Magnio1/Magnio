import type {
  ChatAnalyticsSummary,
  ChatFeedbackState,
  ChatFeedbackVote,
  ChatHealth,
  ChatMode,
  ChatResponse,
  ChatStreamEvent,
  ModelTrendPoint,
  RecentEvaluationCasesResponse,
} from './types'

function resolveApiBase(): string {
  const configured = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/$/, '')
  if (!configured) {
    return ''
  }

  if (typeof window === 'undefined') {
    return configured
  }

  try {
    const url = new URL(configured)
    const localHosts = new Set(['localhost', '127.0.0.1'])
    const configuredIsLoopback = localHosts.has(url.hostname)

    // When the configured API target is loopback, always prefer same-origin
    // so Vite/ngrok can proxy `/api/*` correctly for localhost and shared hosts.
    if (configuredIsLoopback) {
      return ''
    }

    return url.origin
  } catch {
    return configured
  }
}

const API_BASE = resolveApiBase()

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  const contentType = response.headers.get('content-type') ?? ''

  if (contentType.includes('application/json')) {
    const payload = await response.json().catch(() => ({}))
    if (typeof payload?.detail === 'string' && payload.detail.trim()) {
      return payload.detail
    }
  } else {
    const bodyText = await response.text().catch(() => '')
    const condensed = bodyText.replace(/\s+/g, ' ').trim()
    if (condensed) {
      const snippet = condensed.slice(0, 180)
      return `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}: ${snippet}`
    }
  }

  if (response.status >= 500) {
    return `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}. ${fallback}`
  }

  return fallback
}

export async function askMagnioChat(query: string, mode: ChatMode): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/chat/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      mode,
    }),
  })

  if (!response.ok) {
    throw new Error(await readErrorDetail(response, 'The chat request failed. Please try again.'))
  }

  return (await response.json()) as ChatResponse
}

export async function streamMagnioChat(
  query: string,
  mode: ChatMode,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat/ask/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      mode,
    }),
  })

  if (!response.ok) {
    throw new Error(await readErrorDetail(response, 'The chat request failed. Please try again.'))
  }

  if (!response.body) {
    throw new Error('Streaming is not available in this browser session.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue

      let event: ChatStreamEvent
      try {
        event = JSON.parse(trimmed) as ChatStreamEvent
      } catch {
        continue
      }
      onEvent(event)
    }
  }

  const trailing = buffer.trim()
  if (trailing) {
    try {
      onEvent(JSON.parse(trailing) as ChatStreamEvent)
    } catch {
      // Ignore trailing malformed fragments and rely on prior complete/error events.
    }
  }
}

export async function getMagnioChatHealth(): Promise<ChatHealth> {
  const response = await fetch(`${API_BASE}/api/chat/health`)
  if (!response.ok) {
    throw new Error('Unable to load chat health.')
  }
  return response.json() as Promise<ChatHealth>
}

export async function getMagnioChatAnalyticsSummary(): Promise<ChatAnalyticsSummary> {
  const response = await fetch(`${API_BASE}/api/chat/analytics/summary`)
  if (!response.ok) {
    throw new Error('Unable to load chat analytics.')
  }
  return response.json() as Promise<ChatAnalyticsSummary>
}

export async function getRecentMagnioEvaluationCases(limit = 20): Promise<RecentEvaluationCasesResponse> {
  const response = await fetch(`${API_BASE}/api/chat/evaluations/recent?limit=${encodeURIComponent(String(limit))}`)
  if (!response.ok) {
    throw new Error('Unable to load recent evaluation cases.')
  }
  return response.json() as Promise<RecentEvaluationCasesResponse>
}

export async function getMagnioModelTrends(limit = 30): Promise<ModelTrendPoint[]> {
  const response = await fetch(
    `${API_BASE}/api/chat/analytics/model-trends?limit=${encodeURIComponent(String(limit))}`,
  )
  if (!response.ok) return []
  const payload = (await response.json().catch(() => ({}))) as { trends?: ModelTrendPoint[] }
  return payload.trends ?? []
}

export async function getMagnioFollowUpSuggestions(
  answer: string,
  topicLabel: string,
  mode: ChatMode,
): Promise<string[]> {
  const response = await fetch(`${API_BASE}/api/chat/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer, topic_label: topicLabel, mode }),
  })
  if (!response.ok) return []
  const payload = (await response.json().catch(() => ({}))) as { suggestions?: string[] }
  return payload.suggestions ?? []
}

export async function submitMagnioChatFeedback(
  runId: string,
  vote: ChatFeedbackVote,
  note?: string,
): Promise<ChatFeedbackState> {
  const response = await fetch(`${API_BASE}/api/chat/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      runId,
      vote,
      note,
    }),
  })

  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail =
      typeof payload?.detail === 'string'
        ? payload.detail
        : 'Unable to submit feedback.'
    throw new Error(detail)
  }

  return payload.feedback as ChatFeedbackState
}
