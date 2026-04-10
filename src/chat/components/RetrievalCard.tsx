import { motion } from 'framer-motion'

import type { RetrievalItem } from '../types'

function RetrievalCard({ item, index }: { item: RetrievalItem; index: number }) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 * index }}
      className="group rounded-2xl border border-white/6 bg-white/[0.02] p-4 transition-all hover:bg-white/[0.04]"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-400/50 transition-colors group-hover:text-cyan-400">
            {item.id}
          </div>
          <h4 className="mt-2 text-base font-semibold text-white transition-colors group-hover:text-cyan-50">
            {item.title}
          </h4>
          {item.source ? (
            <div className="mt-2 text-[10px] font-medium uppercase tracking-[0.16em] text-slate-500">
              {item.source.replace('.json', '')}
            </div>
          ) : null}
        </div>
        <div className="rounded-full border border-white/10 bg-black/40 px-3 py-1 text-[10px] font-bold text-slate-400">
          {(item.score * 10).toFixed(0)}% Match
        </div>
      </div>
      <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-400">
        {item.excerpt}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {item.tags.map((tag) => (
          <span
            key={`${item.id}-${tag}`}
            className="rounded-full border border-white/5 bg-white/[0.02] px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.1em] text-slate-400"
          >
            {tag}
          </span>
        ))}
      </div>
    </motion.article>
  )
}

export default RetrievalCard
