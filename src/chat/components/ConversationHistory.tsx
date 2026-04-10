import { MessageSquare, Plus, Trash2 } from 'lucide-react'

import type { SavedConversation } from '../types'

function ConversationHistory({
  sessions,
  currentSessionId,
  onLoad,
  onDelete,
  onNew,
}: {
  sessions: SavedConversation[]
  currentSessionId: string
  onLoad: (session: SavedConversation) => void
  onDelete: (id: string) => void
  onNew: () => void
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <MessageSquare className="h-4 w-4 text-violet-400" />
          <span className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400">Sessions</span>
        </div>
        <button
          type="button"
          onClick={onNew}
          className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-semibold text-slate-300 transition hover:bg-white/[0.08] hover:text-white"
        >
          <Plus className="h-3 w-3" />
          New chat
        </button>
      </div>

      {sessions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 px-4 py-5 text-center text-xs text-slate-500">
          No saved sessions yet
        </div>
      ) : (
        <div className="max-h-[220px] space-y-1.5 overflow-y-auto pr-1 custom-scrollbar">
          {sessions.map((session) => {
            const isActive = session.id === currentSessionId
            const date = new Date(session.updatedAt).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
            })
            const msgCount = session.messages.length
            return (
              <div
                key={session.id}
                className={`flex items-center gap-2 rounded-xl border px-3 py-2.5 transition ${
                  isActive
                    ? 'border-violet-400/20 bg-violet-400/10'
                    : 'border-white/5 bg-white/[0.02] hover:bg-white/[0.05]'
                }`}
              >
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onLoad(session)}
                >
                  <div className="truncate text-xs font-semibold text-slate-200">{session.name}</div>
                  <div className="mt-0.5 text-[10px] text-slate-500">
                    {date} · {msgCount} msg{msgCount !== 1 ? 's' : ''}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(session.id)}
                  aria-label="Delete session"
                  className="shrink-0 rounded-lg p-1 text-slate-600 transition hover:bg-white/5 hover:text-rose-400"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default ConversationHistory
