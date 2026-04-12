import { Children, isValidElement, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type MarkdownSurfaceProps = {
  content: string
}

function getSectionRows(sectionNode: ReactNode) {
  if (!isValidElement<{ children?: ReactNode }>(sectionNode)) {
    return [] as ReactNode[][]
  }

  return Children.toArray(sectionNode.props.children).flatMap((rowNode) => {
    if (!isValidElement<{ children?: ReactNode }>(rowNode)) {
      return []
    }

    const cells = Children.toArray(rowNode.props.children).map((cellNode) =>
      isValidElement<{ children?: ReactNode }>(cellNode) ? cellNode.props.children : cellNode,
    )

    return cells.length ? [cells] : []
  })
}

function MarkdownSurface({ content }: MarkdownSurfaceProps) {
  return (
    <div className="magnio-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children, ...props }) => {
            const sections = Children.toArray(children)
            const headerRows = getSectionRows(sections[0])
            const headers = headerRows[0] ?? []
            const bodyRows = sections.slice(1).flatMap(getSectionRows)

            return (
              <div className="my-6 overflow-hidden rounded-[24px] border border-white/10 bg-[#050b12]/80 shadow-[0_18px_60px_rgba(0,0,0,0.22)]">
                <div className="overflow-x-auto custom-scrollbar max-md:hidden">
                  <table
                    {...props}
                    className="min-w-[720px] w-full border-collapse text-left text-[14px] leading-6"
                  >
                    {children}
                  </table>
                </div>
                <div className="space-y-3 p-3 md:hidden">
                  {bodyRows.map((cells, rowIndex) => (
                    <div
                      key={`table-row-${rowIndex}`}
                      className="rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3"
                    >
                      {cells.map((cell, cellIndex) => (
                        <div
                          key={`table-row-${rowIndex}-cell-${cellIndex}`}
                          className={`grid grid-cols-[minmax(0,112px)_1fr] gap-3 ${
                            cellIndex === 0 ? '' : 'mt-3 border-t border-white/6 pt-3'
                          }`}
                        >
                          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                            {headers[cellIndex] ?? `Column ${cellIndex + 1}`}
                          </div>
                          <div
                            className={`text-sm leading-6 ${
                              cellIndex === 0 ? 'font-semibold text-white' : 'text-slate-300'
                            }`}
                          >
                            {cell}
                          </div>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )
          },
          thead: ({ ...props }) => <thead {...props} className="bg-white/[0.04]" />,
          tbody: ({ ...props }) => <tbody {...props} className="divide-y divide-white/6" />,
          tr: ({ ...props }) => <tr {...props} className="align-top" />,
          th: ({ ...props }) => (
            <th
              {...props}
              className="px-4 py-3 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-300 first:w-[170px] first:text-slate-200"
            />
          ),
          td: ({ ...props }) => (
            <td
              {...props}
              className="px-4 py-3 text-[15px] leading-7 text-slate-300 first:font-semibold first:text-white"
            />
          ),
          a: ({ ...props }) => (
            <a
              {...props}
              className="font-medium text-cyan-200 underline decoration-cyan-400/40 underline-offset-4 hover:text-white"
              rel="noreferrer"
              target="_blank"
            />
          ),
          code: ({ className, children, ...props }) => {
            const isBlock = Boolean(className)
            if (!isBlock) {
              return (
                <code
                  {...props}
                  className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[0.9em] font-bold text-cyan-300/90"
                >
                  {children}
                </code>
              )
            }

            return (
              <pre className="my-6 overflow-x-auto rounded-[24px] border border-white/10 bg-[#03080e]/80 p-4 sm:p-6 text-sm text-slate-200 shadow-xl custom-scrollbar">
                <code {...props} className={`${className} font-medium`}>
                  {children}
                </code>
              </pre>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default MarkdownSurface
