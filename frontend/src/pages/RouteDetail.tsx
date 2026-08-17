import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getPriceSnapshots, getAgentLogs, getBookings } from '../lib/api'
import api from '../lib/api'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, CartesianGrid
} from 'recharts'
import { TrendingDown, Bot, CreditCard, ArrowLeft, ChevronDown, ChevronUp } from 'lucide-react'

interface Route {
  id: string; origin: string; destination: string
  target_price: number; booking_mode: string; status: string
  date_from: string; max_connections: number | null
}

interface PendingBooking {
  id: string; price: string; airline: string | null
  departure_at: string | null; origin: string; destination: string
}

interface Snapshot {
  id: string; price: string; airline: string | null
  flight_number: string | null; fetched_at: string; departure_at: string | null
}

interface AgentLog {
  id: string; action: string; ml_score: number
  reasoning: string | null; created_at: string
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-3 text-xs">
      <p className="font-semibold text-gray-900">${parseFloat(d.price).toFixed(0)}</p>
      {d.airline && <p className="text-gray-500 mt-0.5">{d.airline} {d.flight_number}</p>}
      <p className="text-gray-400 mt-0.5">{d.dateLabel}</p>
    </div>
  )
}

const CustomDot = (props: any) => {
  const { cx, cy, isMin } = props
  if (!isMin) return null
  return (
    <g>
      <circle cx={cx} cy={cy} r={6} fill="#16a34a" stroke="white" strokeWidth={2} />
      <text x={cx} y={cy - 12} textAnchor="middle" fontSize={10} fill="#16a34a" fontWeight="600">
        Best
      </text>
    </g>
  )
}

export default function RouteDetail() {
  const { id } = useParams<{ id: string }>()
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [logs, setLogs] = useState<AgentLog[]>([])
  const [route, setRoute] = useState<Route | null>(null)
  const [pendingBooking, setPendingBooking] = useState<PendingBooking | null>(null)
  const [expandedLog, setExpandedLog] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api.get(`/v1/routes/${id}`).then(r => setRoute(r.data)).catch(() => {})
    getPriceSnapshots(id).then(r => setSnapshots(r.data)).catch(() => {})
    getAgentLogs(id).then(r => setLogs(r.data)).catch(() => {})
    getBookings(id).then(r => {
      const pending = r.data.find((b: any) => b.status === 'pending')
      if (pending) setPendingBooking(pending)
    }).catch(() => {})
  }, [id])

  const prices = snapshots.map(s => parseFloat(s.price))
  const minPrice = prices.length ? Math.min(...prices) : null
  const currentPrice = prices.length ? prices[prices.length - 1] : null
  const targetPrice = route?.target_price ?? null

  const chartData = snapshots.map((s) => ({
    price: parseFloat(s.price),
    airline: s.airline,
    flight_number: s.flight_number,
    dateLabel: new Date(s.fetched_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    isMin: parseFloat(s.price) === minPrice,
  }))

  const yMin = minPrice ? Math.floor(minPrice * 0.97 / 10) * 10 : undefined
  const yMax = prices.length ? Math.ceil(Math.max(...prices) * 1.03 / 10) * 10 : undefined

  const savings = targetPrice && currentPrice ? targetPrice - currentPrice : null
  const stopsLabel = route?.max_connections === 0 ? 'Nonstop' : route?.max_connections === 1 ? '≤1 stop' : 'Any stops'

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 pb-24">

      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <Link to="/routes" className="p-2 rounded-full hover:bg-gray-100 transition-colors">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            {route ? `${route.origin} → ${route.destination}` : 'Price History'}
          </h1>
          {route && (
            <p className="text-xs text-gray-500 mt-0.5">
              {stopsLabel} · Target ${route.target_price}
              {route.date_from && ` · ${new Date(route.date_from).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`}
            </p>
          )}
        </div>
      </div>

      {/* Stats row */}
      {prices.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-white rounded-xl border border-gray-200 p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">Current</p>
            <p className="text-lg font-bold text-gray-900">${currentPrice?.toFixed(0)}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">Best seen</p>
            <p className="text-lg font-bold text-green-600">${minPrice?.toFixed(0)}</p>
          </div>
          <div className={`rounded-xl border p-3 text-center ${savings && savings > 0 ? 'bg-green-50 border-green-200' : 'bg-white border-gray-200'}`}>
            <p className="text-xs text-gray-500 mb-1">vs Target</p>
            <p className={`text-lg font-bold ${savings && savings > 0 ? 'text-green-600' : savings && savings < 0 ? 'text-red-500' : 'text-gray-900'}`}>
              {savings !== null ? `${savings > 0 ? '-' : '+'}$${Math.abs(savings).toFixed(0)}` : '—'}
            </p>
          </div>
        </div>
      )}

      {/* Deal ready banner */}
      {pendingBooking && (
        <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-2xl p-4 mb-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 bg-green-500 rounded-full flex items-center justify-center shrink-0">
              <CreditCard className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="font-bold text-green-900 text-sm">Deal found — ready to pay!</p>
              <p className="text-green-700 text-xs mt-0.5">
                <span className="font-semibold">${parseFloat(pendingBooking.price).toFixed(2)}</span>
                {pendingBooking.airline && ` via ${pendingBooking.airline}`}
                {pendingBooking.departure_at && ` · ${new Date(pendingBooking.departure_at).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}`}
              </p>
            </div>
          </div>
          <Link
            to={`/bookings/${pendingBooking.id}/pay`}
            className="w-full flex items-center justify-center gap-2 bg-black text-white font-semibold py-3 rounded-xl text-sm"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5 fill-white">
              <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
            </svg>
            Pay with Apple Pay
          </Link>
        </div>
      )}

      {/* Price chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
        <h2 className="font-semibold text-gray-800 text-sm mb-4 flex items-center gap-2">
          <TrendingDown className="w-4 h-4 text-indigo-500" />
          Price history
        </h2>
        {chartData.length === 0 ? (
          <p className="text-center text-gray-400 py-12 text-sm">Agent is watching — price data will appear here</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={chartData} margin={{ top: 20, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
              <XAxis
                dataKey="dateLabel"
                tick={{ fontSize: 10, fill: '#9ca3af' }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#9ca3af' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={v => `$${v}`}
                domain={[yMin ?? 'auto', yMax ?? 'auto']}
                width={40}
              />
              <Tooltip content={<CustomTooltip />} />
              {targetPrice && (
                <ReferenceLine
                  y={targetPrice}
                  stroke="#2563eb"
                  strokeDasharray="5 3"
                  strokeWidth={1.5}
                  label={{ value: `Target $${targetPrice}`, fill: '#2563eb', fontSize: 10, position: 'insideTopRight' }}
                />
              )}
              <Area
                type="monotone"
                dataKey="price"
                stroke="#6366f1"
                strokeWidth={2.5}
                fill="url(#priceGrad)"
                dot={(props: any) => <CustomDot {...props} isMin={props.payload.isMin} />}
                activeDot={{ r: 4, fill: '#6366f1', stroke: 'white', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Agent decisions */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="font-semibold text-gray-800 text-sm mb-3 flex items-center gap-2">
          <Bot className="w-4 h-4 text-indigo-500" />
          AI Decisions
          <span className="ml-auto text-xs font-normal text-gray-400">{logs.length} logged</span>
        </h2>
        {logs.length === 0 ? (
          <p className="text-center text-gray-400 py-8 text-sm">No decisions yet — agent is monitoring</p>
        ) : (
          <div className="space-y-1">
            {logs.map((l) => {
              const isBuy = l.action === 'buy' || l.action === 'booked'
              const isExpanded = expandedLog === l.id
              return (
                <button
                  key={l.id}
                  className="w-full text-left"
                  onClick={() => setExpandedLog(isExpanded ? null : l.id)}
                >
                  <div className="flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0">
                    <span className={`mt-0.5 text-xs font-bold px-2 py-0.5 rounded-full shrink-0 ${isBuy ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
                      {l.action.toUpperCase()}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs text-gray-700 ${isExpanded ? '' : 'line-clamp-2'}`}>
                        {l.reasoning || '—'}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        Confidence {(l.ml_score * 100).toFixed(0)}%
                        · {new Date(l.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                      </p>
                    </div>
                    <div className="shrink-0 mt-0.5 text-gray-400">
                      {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>

    </div>
  )
}
