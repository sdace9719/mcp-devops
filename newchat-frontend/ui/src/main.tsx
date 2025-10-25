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
  const endRef = useRef<HTMLDivElement | null>(null)

  async function sendMessage() {
    if (!input.trim()) return
    const nextMessages = [...messages, { role: 'user', content: input }]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, messages: nextMessages })
      })
      const data = await res.json()
      if (res.ok) {
        setMessages(m => [...m, { role: 'assistant', content: data.message || '' }])
      } else {
        setMessages(m => [...m, { role: 'assistant', content: `Error: ${data.detail || 'unknown'}` }])
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
        <h1 className="text-2xl font-bold mb-4">NewChat</h1>
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
        <div className="flex gap-3 mt-4">
          <input className="border rounded px-3 py-2 flex-1" placeholder="Type a message..." value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') sendMessage() }} />
          <button className="bg-blue-600 text-white rounded px-4" onClick={sendMessage} disabled={loading}>{loading ? 'Sending...' : 'Send'}</button>
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


