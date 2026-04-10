import type { PromptPreset } from './types'

export const PROMPT_PRESETS: PromptPreset[] = [
  {
    id: 'arena-programming',
    title: 'Programming Arena',
    description: 'Route a coding question to the top category models and judge the result.',
    mode: 'arena',
    prompt:
      'Design a TypeScript architecture for a multi-tenant agentic AI dashboard with model routing, audit logs, and evaluation tracing.',
  },
  {
    id: 'arena-compare',
    title: 'Model Comparison',
    description: 'Run a general reasoning prompt through the arena pipeline.',
    mode: 'arena',
    prompt:
      'What is the best way for a mid-market operations team to introduce agentic AI without creating reliability issues?',
  },
  {
    id: 'advisor-immersion',
    title: 'AI Immersion Plan',
    description: 'Ask Magnio Advisor for a grounded rollout recommendation.',
    mode: 'advisor',
    prompt:
      'How should a 40-person operations team approach AI immersion if their workflows still live across email, spreadsheets, and two CRMs?',
  },
  {
    id: 'advisor-fit',
    title: 'Lead Qualification',
    description: 'See how the advisor frames the best Magnio entry point.',
    mode: 'advisor',
    prompt:
      'What kind of client is Magnio the best fit for, and what should that lead bring to the first conversation?',
  },
  {
    id: 'advisor-proof',
    title: 'Case Study Pull',
    description: 'Ground an answer in Magnio proof points and service positioning.',
    mode: 'advisor',
    prompt:
      'Summarize Magnio in a way that a COO would care about. Focus on measured impact, workflow discipline, and where AI fits.',
  },
  {
    id: 'auto-blend',
    title: 'Auto Routing',
    description: 'Let the chat decide between the arena and advisor paths.',
    mode: 'auto',
    prompt:
      'I know I want AI in the business, but I do not know whether I need an agent, a workflow redesign, or a simple automation first. How would you approach that?',
  },
]
