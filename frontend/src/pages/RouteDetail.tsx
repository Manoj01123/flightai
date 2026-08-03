import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getPriceSnapshots, getAgentLogs } from '../lib/api'
import api from '../lib/api'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { TrendingDown, Bot, Zap, Bell } from 'lucide-react'
import toast from 'react-hot-toast'

interface Route {
  id: string; origin: string; destination: string; target_price: number
  booking_mode: string; status: string; departure_date: string
}

export default function RouteDetail() {
  const { id } = useParams<{ id: string }>()
  const [snapshots, setSnapshots] = useState<any[]>([])
  const [logs, setLogs] = useState<any[]>([])
  const [route, setRoute] = useState<Route | null>(null)
  const [updatingMode, setUpdatingMode] = useState(false)
  const [showModeModal, setShowModeModal] = useState(false)

  useEffect(() => {
    if (!id) return
    api.get(`/v1/routes/${id}`).then(r => setRoute(r.data)).catch(() => {})
    getPriceSnapshots(id).then(r => setSnapshots(r.data)).catch(() => {})
    getAgentLogs(id).then(r => setLogs(r.data)).catch(() => {})
  }, [id])

  const handleModeChange = async (newMode: string) => {
    if (!route) return
    if (newMode === 'B') {
      setShowModeModal(true)
      return
    }
    applyModeChange(newMode)
  }

  const applyModeChange = async (newMode: string) => {
    if (!id) return
    setShowModeModal(false)
    setUpdatingMode(true)
    try {
      const res = await api.patch(`/v1/routes/${id}`, { booking_mode: newMode })
      setRoute(res.data)
      toast.success(`Switched to Mode ${newMode}`)
    } catch {
      toast.error('Failed to update booking mode')
    } finally {
      setUpdatingMode(false)
    }
  }

  const chartData = snapshots.map((s: any) => ({
    date: new Date(s.fetched_at).toLocaleDateString(),
    price: parseFloat(s.price),
  }))

  const targetPrice = route?.target_price

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <TrendingDown className="w-6 h-6" />
          {route ? `${route.origin} → ${route.destination}` : 'Price History'}
        </h1>
      </div>

      {/* Booking mode toggle */}
      {route && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-gray-800 text-sm">Booking mode</p>
              <p className="text-xs text-gray-400 mt-0.5">Change how the AI acts when it finds a deal</p>
            </div>
            <div className="flex items-center gap-2">
              {[
                { mode: 'A', icon: Bell, label: 'Alert me' },
                { mode: 'B', icon: Zap, label: 'Auto-book' },
              ].map(({ mode, icon: Icon, label }) => (
                <button key={mode} onClick={() => handleModeChange(mode)} disabled={updatingMode}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border transition-colors
                    ${route.booking_mode === mode
                      ? mode === 'A' ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-purple-600 bg-purple-50 text-purple-700'
                      : 'border-gray-200 text-gray-500 hover:border-gray-300'}`}>
                  <Icon className="w-3.5 h-3.5" />{label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Price chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold text-gray-800 mb-4">Price over time</h2>
        {chartData.length === 0 ? (
          <p className="text-center text-gray-400 py-12">No price data yet — agent is watching</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData}>
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `$${v}`} />
              <Tooltip formatter={(v) => [`$${v}`, 'Price']} />
              {targetPrice && <ReferenceLine y={targetPrice} stroke="#2563eb" strokeDasharray="4 4" label={{ value: 'Target', fill: '#2563eb', fontSize: 12 }} />}
              <Line type="monotone" dataKey="price" stroke="#6366f1" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Agent decisions */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2"><Bot className="w-4 h-4" />Agent Decisions</h2>
        {logs.length === 0 ? (
          <p className="text-center text-gray-400 py-8">No decisions logged yet</p>
        ) : (
          <div className="space-y-2">
            {logs.map((l: any) => (
              <div key={l.id} className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
                <span className={`mt-0.5 text-xs font-bold px-2 py-0.5 rounded-full shrink-0 ${l.action === 'buy' || l.action === 'booked' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                  {l.action.toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700">{l.reasoning || '—'}</p>
                  <p className="text-xs text-gray-400 mt-0.5">ML Score: {l.ml_score?.toFixed(0)}% · {new Date(l.created_at).toLocaleString()}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Mode B confirmation modal */}
      {showModeModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl">
            <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center mb-4">
              <Zap className="w-6 h-6 text-purple-600" />
            </div>
            <h3 className="font-bold text-gray-900 text-lg mb-2">Enable Auto-book?</h3>
            <p className="text-gray-500 text-sm mb-5">
              With <span className="font-semibold text-purple-700">Mode B — Auto-book</span>, the AI will
              charge your wallet and complete the booking automatically the moment it finds a price at or
              below your target. <span className="font-semibold text-gray-700">No confirmation from you is needed.</span>
            </p>
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-5">
              <p className="text-xs text-amber-700">Make sure your wallet has sufficient funds. The AI acts fast — deals can disappear in minutes.</p>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setShowModeModal(false)}
                className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm font-medium hover:bg-gray-50">
                Keep Mode A
              </button>
              <button onClick={() => applyModeChange('B')}
                className="flex-1 bg-purple-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-purple-700">
                Enable Auto-book
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
