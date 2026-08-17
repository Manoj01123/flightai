import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getWallet, getRoutes, getBookings, getAgentLogs } from '../lib/api'
import { Wallet, Map, BookOpen, Bot, Plus, BellRing, ArrowUpCircle, ArrowDownCircle } from 'lucide-react'

interface WalletData {
  balance: string
  transactions: { id: string; amount: string; transaction_type: string; description: string; created_at: string }[]
}
interface Route { id: string; origin: string; destination: string; status: string; target_price: number; booking_mode?: string }
interface Booking { id: string; status: string; price: string; airline: string; route_id?: string }
interface AgentLog { id: string; action: string; ml_score: number; reasoning: string; created_at: string; route_id?: string }

const statusColor: Record<string, string> = {
  active: 'bg-blue-100 text-blue-700',
  booked: 'bg-green-100 text-green-700',
  expired: 'bg-red-100 text-red-700',
  paused: 'bg-gray-400 text-white',
  cancelled: 'bg-gray-100 text-gray-500',
}

export default function Dashboard() {
  const { user } = useAuth()
  const [wallet, setWallet] = useState<WalletData | null>(null)
  const [routes, setRoutes] = useState<Route[]>([])
  const [bookings, setBookings] = useState<Booking[]>([])
  const [logs, setLogs] = useState<AgentLog[]>([])

  const loadAll = () => {
    getWallet().then(r => setWallet(r.data)).catch(() => {})
    getRoutes().then(r => setRoutes(r.data)).catch(() => {})
    getBookings().then(r => setBookings(r.data)).catch(() => {})
    getAgentLogs().then(r => setLogs(r.data)).catch(() => {})
  }

  useEffect(() => {
    loadAll()
    const timer = setInterval(loadAll, 30_000)
    return () => clearInterval(timer)
  }, [])

  const activeRoutes = routes.filter(r => r.status === 'active').length
  const totalBookings = bookings.filter(b => b.status === 'confirmed').length

  const confirmedRouteIds = new Set(bookings.filter(b => b.status === 'confirmed').map(b => b.route_id))
  const pendingBookings = bookings.filter(b => b.status === 'pending')
  const modeAPendingRoutes = routes.filter(r =>
    r.status === 'active' &&
    !confirmedRouteIds.has(r.id) &&
    pendingBookings.some(b => b.route_id === r.id)
  )

  const recentTransactions = wallet?.transactions?.slice(0, 4) || []

  return (
    <div className="max-w-6xl mx-auto px-4 py-4 md:px-6 md:py-8">
      <div className="mb-4 md:mb-8">
        <h1 className="text-xl md:text-2xl font-bold text-gray-900">Welcome back, {user?.first_name} 👋</h1>
        <p className="text-gray-500 text-sm mt-0.5">Your AI agent is watching your routes 24/7</p>
      </div>

      {/* Mode A pending confirmation alerts */}
      {modeAPendingRoutes.length > 0 && (
        <div className="mb-6 space-y-2">
          {modeAPendingRoutes.map(r => {
            const pb = pendingBookings.find(b => b.route_id === r.id)
            return (
              <div key={r.id} className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl px-5 py-4">
                <BellRing className="w-5 h-5 text-green-600 shrink-0" />
                <div className="flex-1">
                  <p className="font-semibold text-green-900 text-sm">Deal found! {r.origin} → {r.destination}</p>
                  <p className="text-xs text-green-700 mt-0.5">
                    {pb ? `$${parseFloat(pb.price).toFixed(2)} · ` : ''}
                    Tap to pay with Apple Pay and confirm your seat.
                  </p>
                </div>
                <Link to={pb ? `/bookings/${pb.id}/pay` : `/routes/${r.id}`}
                  className="shrink-0 bg-green-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-green-700 transition-colors">
                  Pay Now
                </Link>
              </div>
            )
          })}
        </div>
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard icon={Wallet} label="Wallet Balance" value={wallet ? `$${parseFloat(wallet.balance).toFixed(2)}` : '—'} color="blue" />
        <StatCard icon={Map} label="Active Routes" value={String(activeRoutes)} color="indigo" />
        <StatCard icon={BookOpen} label="Bookings Made" value={String(totalBookings)} color="green" />
        <StatCard icon={Bot} label="Agent Decisions" value={String(logs.length)} color="purple" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Active routes */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-800 flex items-center gap-2"><Map className="w-4 h-4" /> Active Routes</h2>
            <Link to="/routes/new" className="flex items-center gap-1 text-sm text-blue-600 hover:underline"><Plus className="w-3.5 h-3.5" />Add</Link>
          </div>
          {routes.length === 0 ? (
            <EmptyState text="No routes yet" cta="Add your first route" to="/routes/new" />
          ) : (
            <div className="space-y-3">
              {routes.slice(0, 5).map(r => (
                <Link key={r.id} to={`/routes/${r.id}`} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0 hover:bg-gray-50 -mx-2 px-2 rounded-lg">
                  <div>
                    <span className="font-medium text-gray-800">{r.origin} → {r.destination}</span>
                    <div className="text-sm text-gray-500">Target: ${r.target_price}</div>
                  </div>
                  <span className={`text-xs font-medium px-2 py-1 rounded-full ${statusColor[r.status] || 'bg-gray-100 text-gray-600'}`}>
                    {r.status}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent agent decisions */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><Bot className="w-4 h-4" /> Recent AI Decisions</h2>
          {logs.length === 0 ? (
            <EmptyState text="No agent activity yet" cta="Create a route to start" to="/routes/new" />
          ) : (
            <div className="space-y-3">
              {logs.slice(0, 5).map(l => (
                <div key={l.id} className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
                  <span className={`mt-0.5 text-xs font-bold px-2 py-0.5 rounded-full ${l.action === 'buy' || l.action === 'booked' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                    {l.action.toUpperCase()}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-700 leading-snug" style={{display:'-webkit-box',WebkitLineClamp:3,WebkitBoxOrient:'vertical',overflow:'hidden'}}>{l.reasoning || 'Agent evaluated price data'}</p>
                    <p className="text-xs text-gray-400 mt-0.5">ML Score: {l.ml_score?.toFixed(0)}% · {new Date(l.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent charges (Stripe / wallet transactions) */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800 flex items-center gap-2"><Wallet className="w-4 h-4" /> Recent Charges</h2>
          <Link to="/wallet" className="text-sm text-blue-600 hover:underline">View all</Link>
        </div>
        {recentTransactions.length === 0 ? (
          <EmptyState text="No transactions yet" cta="Add funds to your wallet" to="/wallet" />
        ) : (
          <div className="divide-y divide-gray-100">
            {recentTransactions.map(tx => (
              <div key={tx.id} className="flex items-center gap-3 py-3">
                {tx.transaction_type === 'TOPUP'
                  ? <ArrowUpCircle className="w-4 h-4 text-green-500 shrink-0" />
                  : <ArrowDownCircle className="w-4 h-4 text-red-400 shrink-0" />}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 truncate">{tx.description}</p>
                  <p className="text-xs text-gray-400">{new Date(tx.created_at).toLocaleDateString()}</p>
                </div>
                <span className={`text-sm font-semibold ${tx.transaction_type === 'TOPUP' ? 'text-green-600' : 'text-red-500'}`}>
                  {tx.transaction_type === 'TOPUP' ? '+' : '-'}${Math.abs(parseFloat(tx.amount)).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: string; color: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    indigo: 'bg-indigo-50 text-indigo-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
  }
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-2 ${colors[color]}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="text-xl font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500 mt-0.5 leading-tight">{label}</div>
    </div>
  )
}

function EmptyState({ text, cta, to }: { text: string; cta: string; to: string }) {
  return (
    <div className="text-center py-8">
      <p className="text-gray-400 text-sm mb-3">{text}</p>
      <Link to={to} className="text-sm text-blue-600 hover:underline">{cta}</Link>
    </div>
  )
}
