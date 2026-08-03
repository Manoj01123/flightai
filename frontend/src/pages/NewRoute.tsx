import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createRoute } from '../lib/api'
import { Map } from 'lucide-react'
import toast from 'react-hot-toast'

const AIRPORTS = ['JFK','LAX','ORD','MIA','SFO','DFW','ATL','SEA','BOS','LAS','DEN','PHX']

export default function NewRoute() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    origin: '', destination: '', departure_date: '', target_price: '', booking_mode: 'B'
  })
  const [loading, setLoading] = useState(false)

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (form.origin === form.destination) { toast.error('Origin and destination must differ'); return }
    setLoading(true)
    try {
      await createRoute({
        origin: form.origin,
        destination: form.destination,
        date_from: form.departure_date,
        date_to: form.departure_date,
        target_price: parseFloat(form.target_price),
        booking_mode: form.booking_mode,
      })
      toast.success('Route added! AI agent is now watching.')
      navigate('/routes')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create route')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2"><Map className="w-6 h-6" />New Route</h1>
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">From</label>
              <select value={form.origin} onChange={set('origin')} required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Select airport</option>
                {AIRPORTS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">To</label>
              <select value={form.destination} onChange={set('destination')} required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Select airport</option>
                {AIRPORTS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Departure date</label>
            <input type="date" value={form.departure_date} onChange={set('departure_date')} required
              min={new Date().toISOString().split('T')[0]}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target price (USD)</label>
            <input type="number" value={form.target_price} onChange={set('target_price')} required min={1}
              placeholder="e.g. 250"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Booking mode</label>
            <div className="grid grid-cols-2 gap-3">
              {[
                { mode: 'A', title: 'Mode A — Alert', desc: 'AI finds a deal → sends you a link to confirm' },
                { mode: 'B', title: 'Mode B — Auto', desc: 'AI finds a deal → books automatically for you' },
              ].map(({ mode, title, desc }) => (
                <button key={mode} type="button" onClick={() => setForm(f => ({ ...f, booking_mode: mode }))}
                  className={`text-left p-3 rounded-lg border-2 transition-colors ${form.booking_mode === mode ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}>
                  <div className="font-medium text-sm text-gray-900">{title}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{desc}</div>
                </button>
              ))}
            </div>
          </div>

          <button type="submit" disabled={loading}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {loading ? 'Creating…' : 'Start watching this route'}
          </button>
        </form>
      </div>
    </div>
  )
}
