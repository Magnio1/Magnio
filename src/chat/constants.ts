import type { ChatMode } from './types'

export type ModeOption = {
  value: ChatMode
  label: string
  description: string
  eyebrow: string
  actionLabel: string
  placeholder: string
}

export const MODE_OPTIONS: ModeOption[] = [
  {
    value: 'auto',
    label: 'Auto',
    description: 'Let Magnio choose between the arena and advisor pipelines.',
    eyebrow: 'Adaptive router',
    actionLabel: 'Route Query',
    placeholder:
      'Drop in a business question, product idea, or implementation problem. Magnio will route it to the right path.',
  },
  {
    value: 'arena',
    label: 'Arena',
    description: 'Run 3 ranked models, then synthesize with a judge model.',
    eyebrow: '3-model vote',
    actionLabel: 'Run Arena',
    placeholder:
      'Compare an architecture, strategy, or technical question across ranked models and a final judge.',
  },
  {
    value: 'advisor',
    label: 'Advisor',
    description: 'Use hybrid retrieval over Magnio knowledge and AI immersion guidance.',
    eyebrow: 'Grounded advisor',
    actionLabel: 'Ask Advisor',
    placeholder:
      'Ask for the smartest next step, rollout path, offer shape, or practical recommendation grounded in Magnio context.',
  },
]

export const STORAGE_KEY = 'magnio-chat-messages'
