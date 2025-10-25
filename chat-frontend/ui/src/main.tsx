import React, { useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

type Provider = 'gpt' | 'gemini'

type ChatMessage = {
  role: 'system' | 'user' | 'assistant'
  content: string
}

function App() {
  const [provider, setProvider] = useState<Provider>('gpt')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [current, setCurrent] = useState<string>('')
  const endRef = useRef<HTMLDivElement | null>(null)

  async function sendMessage() {
    if (!input.trim()) return
    const nextMessages = [...messages, { role: 'user', content: input }]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    try {
      setCurrent('Queued')
      const res = await fetch('/api/chat_stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, messages: nextMessages })
      })
      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      if (!reader) throw new Error('No stream')
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, idx).trim()
          buffer = buffer.slice(idx + 1)
          if (!line) continue
          try {
            const evt = JSON.parse(line)
            if (evt.type === 'stage') {
              const label = evt.stage === 'registry_loaded' ? 'Loaded tool registry' : evt.stage === 'model_invoked' ? `Invoking model${evt.turn !== undefined ? ` (turn ${evt.turn})` : ''}` : evt.stage
              setCurrent(label)
            } else if (evt.type === 'tool_call') {
              setCurrent(`Calling ${evt.name}`)
            } else if (evt.type === 'tool_result') {
              setCurrent(`${evt.name} done`)
            } else if (evt.type === 'final') {
              const messageContent = typeof evt.message === 'string' ? evt.message : JSON.stringify(evt.message);
              setMessages(m => [...m, { role: 'assistant', content: messageContent || '' }])
              setCurrent('Completed')
            } else if (evt.type === 'error') {
              setMessages(m => [...m, { role: 'assistant', content: `Error: ${evt.error}` }])
              setCurrent('Error')
            }
          } catch (e) {
            console.error('Failed to parse or process stream event:', line, e)
          }
        }
      }
    } catch (e: any) {
      setMessages(m => [...m, { role: 'assistant', content: `Error: ${e?.message || e}` }])
    } finally {
      setLoading(false)
      endRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="max-w-4xl mx-auto p-4">
        <h1 className="text-2xl font-bold mb-4 text-center">Chat</h1>
        <div className="h-[40vh] overflow-y-auto p-4 space-y-3">
          {messages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
              <div className={"inline-block px-3 py-2 rounded " + (m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-100')}>
                <span className="whitespace-pre-wrap">{m.content}</span>
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <div className="flex gap-3 mt-4 items-center">
          <input className="border rounded px-3 py-2 flex-1" placeholder="Type a message..." value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') sendMessage() }} />
          <button className="bg-blue-600 text-white rounded px-4 py-2 h-10 flex-none" onClick={sendMessage} disabled={loading}>{loading ? 'Sending...' : 'Send'}</button>
          <div className="ml-auto min-w-[200px] flex items-center gap-2 justify-end text-sm">
            {loading && <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse" />}
            <span className="text-slate-600 truncate" title={current}>{current}</span>
          </div>
        </div>
        <div className="mt-2">
          <select className="border rounded px-3 py-2" value={provider} onChange={e => setProvider(e.target.value as Provider)}>
            <option value="gpt">OpenAI GPT</option>
            <option value="gemini">Google Gemini</option>
          </select>
        </div>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(<App />)


