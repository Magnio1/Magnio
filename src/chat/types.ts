export type ChatMode = 'auto' | 'arena' | 'advisor'

export type ResolvedChatMode = 'arena' | 'advisor'

export type ChatTopic = {
  id: string
  label: string
  reasoning?: string[]
}

export type RetrievalItem = {
  id: string
  title: string
  excerpt: string
  score: number
  tags: string[]
  source?: string
}

export type CandidateUsage = {
  promptTokens?: number | null
  completionTokens?: number | null
  totalTokens?: number | null
}

export type CandidateResult = {
  modelId: string
  modelName: string
  provider: string
  content: string
  latencyMs: number
  status: 'ok' | 'error'
  error?: string
  usage?: CandidateUsage
}

export type JudgeScore = {
  modelId?: string
  usefulness?: number
  groundedness?: number
  clarity?: number
  decisiveness?: number
  total?: number
  notes?: string
}

export type JudgeResult = {
  winnerModelId?: string
  confidence?: string
  rationale?: string
  judgeModelId?: string
  scores: JudgeScore[]
}

export type ChatDiagnostics = {
  strategy: string
  advisorModelId?: string | null
  answerModelId?: string | null
  evaluationType?: string | null
  groundingMode?: string | null
  selectedModels: string[]
}

export type StructuredAdvisorItem = {
  text: string
  citations: string[]
}

export type StructuredAdvisorFitAnswer = {
  overall_fit: string
  strengths: StructuredAdvisorItem[]
  gaps: StructuredAdvisorItem[]
  interview_answer: StructuredAdvisorItem
  extracted_facts?: StructuredAdvisorItem[]
  rendered?: string
  renderedWordCount?: number
}

export type StructuredAdvisorOpportunityScorecardItem = {
  dimension: string
  score: string
  evidence_text: string
  evidence_citations: string[]
  inference_text: string
}

export type StructuredAdvisorOpportunityRiskItem = {
  text: string
  citations: string[]
  inference_text: string
}

export type StructuredAdvisorPursuitDecision = {
  decision: string
  text: string
  citations: string[]
}

export type StructuredAdvisorOpportunityAnswer = {
  overall_fit: StructuredAdvisorItem
  scorecard: StructuredAdvisorOpportunityScorecardItem[]
  strongest_evidence: StructuredAdvisorItem[]
  gaps_or_risks: StructuredAdvisorOpportunityRiskItem[]
  role_reality_check: StructuredAdvisorOpportunityRiskItem
  pursuit_decision: StructuredAdvisorPursuitDecision
  positioning_strategy: StructuredAdvisorItem
  do_not_overclaim: string[]
  final_verdict: string
  signal_analysis?: string
  role_decomposition?: string
  strategic_value?: string
  hire_signal?: string
  temperature_classification?: string
  extracted_facts?: StructuredAdvisorItem[]
  rendered?: string
  renderedWordCount?: number
}

export type ChatFeedbackVote = 'up' | 'down'

export type ChatFeedbackState = {
  runId: string
  vote: ChatFeedbackVote
  note?: string | null
  updatedAt?: string | null
}

export type ChatResponse = {
  requestedMode: ChatMode
  resolvedMode: ResolvedChatMode
  answer: string
  topic: ChatTopic
  retrieval: RetrievalItem[]
  candidates: CandidateResult[]
  judge: JudgeResult | null
  diagnostics: ChatDiagnostics
  warnings: string[]
  structuredAnswer?: StructuredAdvisorFitAnswer | StructuredAdvisorOpportunityAnswer | null
  runId: string | null
  latencyMs: number
  feedback: ChatFeedbackState | null
  isStreaming?: boolean
  streamingPhase?: string | null
}

export type ChatUserMessage = {
  id: string
  role: 'user'
  content: string
}

export type ChatAssistantMessage = {
  id: string
  role: 'assistant'
  response: ChatResponse
}

export type ChatMessage = ChatUserMessage | ChatAssistantMessage

export type PromptPreset = {
  id: string
  title: string
  description: string
  prompt: string
  mode: ChatMode
}

export type ChatHealth = {
  ok: boolean
  openrouterConfigured: boolean
  knowledgeChunkCount: number
  judgeModelId: string
  advisorModelId: string
  analyticsDbPath: string
}

export type ChatAnalyticsSummary = {
  dbPath: string
  totalRuns: number
  successfulRuns: number
  failedRuns: number
  arenaRuns: number
  advisorRuns: number
  feedbackCount: number
  upvotes: number
  downvotes: number
  topTopics: Array<{
    topicId: string
    label: string
    runCount: number
  }>
  topWinningModels: Array<{
    modelId: string
    winCount: number
  }>
}

export type RecentEvaluationCase = {
  runId: string
  createdAt?: string | null
  status?: string | null
  query?: string | null
  queryPreview: string
  requestedMode?: string | null
  resolvedMode?: string | null
  topicId?: string | null
  topicLabel?: string | null
  strategy?: string | null
  winnerModelId?: string | null
  judgeModelId?: string | null
  latencyMs?: number | null
  answerPreview?: string | null
  review?: {
    vote?: ChatFeedbackVote | null
    note?: string | null
    updatedAt?: string | null
  } | null
}

export type RecentEvaluationCasesResponse = {
  backend: string
  cases: RecentEvaluationCase[]
}

export type ModelTrendPoint = {
  winnerModelId: string
  createdAt: string | null
}

export type SavedConversation = {
  id: string
  name: string
  createdAt: string
  updatedAt: string
  messages: ChatMessage[]
  mode: ChatMode
}

export const isAssistantMessage = (
  message: ChatMessage,
): message is ChatAssistantMessage => message.role === 'assistant'

export const isUserMessage = (
  message: ChatMessage,
): message is ChatUserMessage => message.role === 'user'

export type ChatStreamStartedEvent = {
  type: 'started'
  requestedMode: ChatMode
  resolvedMode: ResolvedChatMode
  topic?: ChatTopic
  diagnostics?: ChatDiagnostics
}

export type ChatStreamStatusEvent = {
  type: 'status'
  phase: string
  message: string
}

export type ChatStreamRetrievalEvent = {
  type: 'retrieval'
  items: RetrievalItem[]
}

export type ChatStreamCandidateEvent = {
  type: 'candidate'
  candidate: CandidateResult
}

export type ChatStreamAnswerDeltaEvent = {
  type: 'answer_delta'
  text: string
}

export type ChatStreamCompleteEvent = {
  type: 'complete'
  response: ChatResponse
}

export type ChatStreamErrorEvent = {
  type: 'error'
  detail: string
  latencyMs?: number
}

export type ChatStreamEvent =
  | ChatStreamStartedEvent
  | ChatStreamStatusEvent
  | ChatStreamRetrievalEvent
  | ChatStreamCandidateEvent
  | ChatStreamAnswerDeltaEvent
  | ChatStreamCompleteEvent
  | ChatStreamErrorEvent
