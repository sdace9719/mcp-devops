import React, { useEffect, useMemo, useState } from 'react'
import { CheckCircleIcon, PlusIcon, ArrowRightOnRectangleIcon } from '@heroicons/react/24/solid'

const API_BASE = import.meta.env.VITE_API_BASE || ''

type Todo = {
  id: number
  title: string
  isDone: boolean
  createdAt: string
}

function useToken() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const save = (t: string | null) => {
    if (t) localStorage.setItem('token', t)
    else localStorage.removeItem('token')
    setToken(t)
  }
  return { token, setToken: save }
}

export const App: React.FC = () => {
  const { token, setToken } = useToken()
  return token ? (
    <TodoPage token={token} onLogout={() => setToken(null)} />
  ) : (
    <LoginPage onLogin={setToken} />
  )
}

const LoginPage: React.FC<{ onLogin: (token: string) => void }> = ({ onLogin }) => {
  const [email, setEmail] = useState('demo@example.com')
  const [password, setPassword] = useState('demo123')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      if (!res.ok) throw new Error('Invalid credentials')
      const data = await res.json()
      onLogin(data.token)
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container-page">
      <div className="section w-full max-w-md mx-auto">
        <div className="mb-6 text-center">
          <h1 className="text-3xl font-bold">Welcome back</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Sign in to your account</p>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="block text-sm mb-1">Email</label>
            <input className="input" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="block text-sm mb-1">Password</label>
            <input className="input" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
          </div>
          {error && <div className="text-red-600 text-sm">{error}</div>}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}

const TodoPage: React.FC<{ token: string; onLogout: () => void }> = ({ token, onLogout }) => {
  const [todos, setTodos] = useState<Todo[]>([])
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const authHeader = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token])

  async function loadTodos() {
    const res = await fetch(`${API_BASE}/api/todos`, { headers: authHeader })
    if (res.ok) {
      const data = await res.json()
      setTodos(data)
    }
    setLoading(false)
  }

  useEffect(() => {
    loadTodos()
  }, [])

  async function addTodo(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    const res = await fetch(`${API_BASE}/api/todos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader },
      body: JSON.stringify({ title: title.trim() })
    })
    if (res.ok) {
      const item = await res.json()
      setTodos(prev => [item, ...prev])
      setTitle('')
    }
  }

  async function toggle(todo: Todo) {
    const res = await fetch(`${API_BASE}/api/todos/${todo.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeader },
      body: JSON.stringify({ isDone: !todo.isDone })
    })
    if (res.ok) {
      const updated = await res.json()
      setTodos(prev => prev.map(t => (t.id === updated.id ? updated : t)))
    }
  }

  return (
    <div className="container-page">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">Your Todos</h1>
        <button className="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300 hover:underline" onClick={onLogout}>
          <ArrowRightOnRectangleIcon className="w-4 h-4" /> Logout
        </button>
      </div>

      <form className="section mb-6 flex gap-3" onSubmit={addTodo}>
        <input className="input flex-1" placeholder="Add a new task…" value={title} onChange={e => setTitle(e.target.value)} />
        <button className="btn-primary inline-flex items-center gap-2" type="submit">
          <PlusIcon className="w-4 h-4" /> Add
        </button>
      </form>

      <div className="section divide-y divide-gray-100 dark:divide-gray-700">
        {loading ? (
          <div className="p-4 text-sm text-gray-500">Loading…</div>
        ) : todos.length === 0 ? (
          <div className="p-4 text-sm text-gray-500">No items yet.</div>
        ) : (
          todos.map(t => (
            <label key={t.id} className="group flex items-center gap-3 p-4 cursor-pointer">
              <input type="checkbox" className="rounded" checked={t.isDone} onChange={() => toggle(t)} />
              <span className={t.isDone ? 'line-through text-gray-400' : 'group-hover:text-gray-900 dark:group-hover:text-white transition-colors'}>{t.title}</span>
              {t.isDone && <CheckCircleIcon className="w-5 h-5 text-green-500 ml-auto" />}
              <span className="ml-auto text-xs text-gray-400">{new Date(t.createdAt).toLocaleString()}</span>
            </label>
          ))
        )}
      </div>
    </div>
  )
}


