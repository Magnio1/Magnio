import type { ChatMessage, JudgeScore } from './types'
import { isAssistantMessage } from './types'

export function createId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function formatLatency(latencyMs: number): string {
  if (!latencyMs) return '--'
  if (latencyMs < 1000) return `${latencyMs} ms`
  return `${(latencyMs / 1000).toFixed(1)} s`
}

export function formatRate(value: number, total: number): string {
  if (!total) return '0%'
  return `${Math.round((value / total) * 100)}%`
}

export function getScoreForModel(
  scores: JudgeScore[],
  modelId: string,
): JudgeScore | undefined {
  return scores.find((score) => score.modelId === modelId)
}

export function exportToMarkdown(messages: ChatMessage[]): string {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  const lines: string[] = [`# Magnio Chat — ${date}`, '']

  for (const message of messages) {
    if (isAssistantMessage(message)) {
      const { response } = message
      lines.push(`## Assistant (${response.resolvedMode} · ${response.topic.label})`)
      lines.push('')
      if (response.answer) {
        lines.push(response.answer)
        lines.push('')
      }
      if (response.retrieval.length) {
        lines.push('### Context Retrieval')
        for (const item of response.retrieval) {
          lines.push(`- **${item.title}** (${Math.round(item.score * 100)}% match)`)
          if (item.excerpt) lines.push(`  > ${item.excerpt.slice(0, 120)}…`)
        }
        lines.push('')
      }
      if (response.latencyMs) {
        lines.push(`*Latency: ${formatLatency(response.latencyMs)}*`)
        lines.push('')
      }
    } else {
      lines.push(`## User`)
      lines.push('')
      lines.push(message.content)
      lines.push('')
    }
  }

  return lines.join('\n')
}

export function triggerMarkdownDownload(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
