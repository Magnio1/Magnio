import type { ModelTrendPoint } from '../types'

// Assign a stable color to each model by hashing its id
const PALETTE = [
  '#22d3ee', // cyan-400
  '#34d399', // emerald-400
  '#fb923c', // orange-400
  '#a78bfa', // violet-400
  '#f472b6', // pink-400
  '#facc15', // yellow-400
]

function modelColor(modelId: string, modelIds: string[]): string {
  const idx = modelIds.indexOf(modelId)
  return PALETTE[idx % PALETTE.length] ?? PALETTE[0]
}

function shortName(modelId: string): string {
  return modelId.split('/').pop() ?? modelId
}

function ModelTrendChart({ trends }: { trends: ModelTrendPoint[] }) {
  if (!trends.length) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 px-4 py-5 text-center text-xs text-slate-500">
        No arena runs yet
      </div>
    )
  }

  // Reverse so oldest → left, newest → right
  const ordered = [...trends].reverse()
  const modelIds = [...new Set(ordered.map((p) => p.winnerModelId))]

  const W = 220
  const H = 56
  const dotR = 3
  const n = ordered.length

  // x positions evenly spaced
  const xs = ordered.map((_, i) => (n === 1 ? W / 2 : (i / (n - 1)) * W))

  // Each model gets a fixed y lane
  const laneH = H / (modelIds.length + 1)
  const modelY = Object.fromEntries(modelIds.map((m, i) => [m, laneH * (i + 1)]))

  // Build per-model polyline paths
  const modelPoints: Record<string, { x: number; y: number }[]> = {}
  for (const id of modelIds) modelPoints[id] = []
  ordered.forEach((pt, i) => {
    modelPoints[pt.winnerModelId].push({ x: xs[i], y: modelY[pt.winnerModelId] })
  })

  // Win count per model for legend
  const winCounts = Object.fromEntries(
    modelIds.map((id) => [id, ordered.filter((p) => p.winnerModelId === id).length]),
  )

  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height={H}
        className="overflow-visible"
        aria-label="Model win trend"
      >
        {/* Grid lines */}
        {modelIds.map((id) => (
          <line
            key={`grid-${id}`}
            x1={0}
            y1={modelY[id]}
            x2={W}
            y2={modelY[id]}
            stroke="rgba(255,255,255,0.04)"
            strokeWidth={1}
          />
        ))}

        {/* Dots for each data point */}
        {ordered.map((pt, i) => {
          const color = modelColor(pt.winnerModelId, modelIds)
          return (
            <circle
              key={i}
              cx={xs[i]}
              cy={modelY[pt.winnerModelId]}
              r={dotR}
              fill={color}
              opacity={0.85}
            >
              <title>
                {shortName(pt.winnerModelId)}
                {pt.createdAt ? ` · ${new Date(pt.createdAt).toLocaleDateString()}` : ''}
              </title>
            </circle>
          )
        })}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1.5">
        {modelIds.map((id) => (
          <div key={id} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ background: modelColor(id, modelIds) }}
            />
            <span className="truncate text-[10px] font-medium text-slate-400" title={id}>
              {shortName(id)}
            </span>
            <span className="text-[10px] font-bold text-slate-500">{winCounts[id]}W</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ModelTrendChart
