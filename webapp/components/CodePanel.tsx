export function CodePanel({ title, code }: { title: string; code: string }) {
  return (
    <div className="flex flex-col h-full bg-[#0d1117] rounded-lg overflow-hidden border border-white/10">
      <div className="px-4 py-2 text-xs font-mono text-white/60 border-b border-white/10 bg-white/5">
        {title}
      </div>
      <pre className="p-4 text-sm text-white/90 overflow-auto flex-1 font-mono leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  )
}
