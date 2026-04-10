import { useCallback, useRef, useState } from 'react'

import type { ChatMessage, ChatMode, SavedConversation } from '../types'
import { isAssistantMessage } from '../types'
import { createId } from '../utils'

const SESSIONS_KEY = 'magnio-sessions'
const SESSIONS_MAX = 20

function readSessions(): SavedConversation[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? (parsed as SavedConversation[]) : []
  } catch {
    return []
  }
}

function writeSessions(sessions: SavedConversation[]) {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(0, SESSIONS_MAX)))
  } catch {
    // Ignore storage failures
  }
}

function deriveSessionName(messages: ChatMessage[]): string {
  const first = messages.find((m) => !isAssistantMessage(m))
  const content = first && !isAssistantMessage(first) ? first.content : ''
  return content.length > 60 ? `${content.slice(0, 60)}…` : content || 'Untitled session'
}

export function useConversationHistory() {
  const [sessions, setSessions] = useState<SavedConversation[]>(readSessions)
  const currentIdRef = useRef<string>(createId())

  const saveSession = useCallback((messages: ChatMessage[], mode: ChatMode) => {
    if (!messages.length) return
    const name = deriveSessionName(messages)
    const now = new Date().toISOString()

    setSessions((prev) => {
      const existing = prev.find((s) => s.id === currentIdRef.current)
      const updated: SavedConversation = existing
        ? { ...existing, name, messages, mode, updatedAt: now }
        : { id: currentIdRef.current, name, createdAt: now, updatedAt: now, messages, mode }
      const without = prev.filter((s) => s.id !== currentIdRef.current)
      const next = [updated, ...without].slice(0, SESSIONS_MAX)
      writeSessions(next)
      return next
    })
  }, [])

  const loadSession = useCallback(
    (session: SavedConversation): { messages: ChatMessage[]; mode: ChatMode } => {
      currentIdRef.current = session.id
      return { messages: session.messages, mode: session.mode }
    },
    [],
  )

  const deleteSession = useCallback((id: string) => {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id)
      writeSessions(next)
      return next
    })
    if (currentIdRef.current === id) {
      currentIdRef.current = createId()
    }
  }, [])

  const newSession = useCallback(() => {
    currentIdRef.current = createId()
  }, [])

  return {
    sessions,
    currentSessionId: currentIdRef.current,
    saveSession,
    loadSession,
    deleteSession,
    newSession,
  }
}
