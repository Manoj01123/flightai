import { useEffect, useState } from 'react'
import api from '../lib/api'
import { Users, BookOpen, Bot, Wallet } from 'lucide-react'

interface AdminUser {
  id: string; email: string; first_name: string; last_name: string
  wallet_balance?: string; created_at: string
}
interface AdminBooking {
  id: string; origin: string; destination: string; status: string
  price: string; airline: string; created_at: string; user_email?: string
}
interface AgentLog {
  id: string; action: string; ml_score: number; reasoning: string
  created_at: string; user_id?: string; route_id?: string
}

type Tab = 'users' | 'bookings' | 'logs'

export default function Admin() {
  const [tab, setTab] = useState<Tab>('users')
  const [users, setUsers] = useState<AdminUser[]>([])
  const [bookings, setBookings] = useState<AdminBooking[]>([])
  const [logs, setLogs] = useState<AgentLog[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    const requests: Promise<any>[] = [
      api.get('/v1/admin/users').then(r => setUsers(r.data)).catch(() => {}),
      api.get('/v1/admin/bookings').then(r => setBookings(r.data)).catch(() => {}),
      api.get('/v1/agent/logs', { params: { limit: 100 } }).then(r => setLogs(r.data)).catch(() => {}),
    ]
    Promise.all(requests).finally(() => setLoading(false))
  }, [])

  const tabs: { key: Tab; label: string; icon: any; count: number }[] = [
    { key: 'users', label: 'Users', icon: Users, count: users.length },
    { key: 'bookings', label: 'Bookings', icon: BookOpen, count: bookings.length },
    { key: 'logs', label: 'Agent Logs', icon: Bot, count: logs.length },
  ]

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
        <p className="text-gray-500 mt-1 text-sm">Platform-wide overview</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <SummaryCard icon={Users} label="Total Users" value={users.length} color="blue" />
        <SummaryCard icon={BookOpen} label="Total Bookings" value={bookings.length} color="green" />
        <SummaryCard icon={Bot} label="Agent Decisions" value={logs.length} color="purple" />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px
              ${tab === t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-800'}`}>
            <t.icon className="w-4 h-4" />
            {t.label}
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${tab === t.key ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'}`}>
              {t.count}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400">Loading…</div>
      ) : (
        <>
          {/* Users table */}
          {tab === 'users' && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {users.length === 0 ? (
                <div className="text-center py-12 text-gray-400 text-sm">No users found — check admin API endpoints</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      {['Name', 'Email', 'Wallet Balance', 'Joined'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {users.map(u => (
                      <tr key={u.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{u.first_name} {u.last_name}</td>
                        <td className="px-4 py-3 text-gray-600">{u.email}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1 text-gray-700">
                            <Wallet className="w-3.5 h-3.5 text-blue-500" />
                            ${u.wallet_balance ? parseFloat(u.wallet_balance).toFixed(2) : '—'}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-400">{new Date(u.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* Bookings table */}
          {tab === 'bookings' && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {bookings.length === 0 ? (
                <div className="text-center py-12 text-gray-400 text-sm">No bookings yet</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      {['Route', 'User', 'Airline', 'Price', 'Status', 'Date'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {bookings.map(b => (
                      <tr key={b.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{b.origin} → {b.destination}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs">{b.user_email || '—'}</td>
                        <td className="px-4 py-3 text-gray-600">{b.airline || '—'}</td>
                        <td className="px-4 py-3 font-medium text-gray-900">${parseFloat(b.price).toFixed(2)}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={b.status} />
                        </td>
                        <td className="px-4 py-3 text-gray-400">{new Date(b.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* Agent logs table */}
          {tab === 'logs' && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {logs.length === 0 ? (
                <div className="text-center py-12 text-gray-400 text-sm">No agent decisions logged yet</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      {['Action', 'ML Score', 'Reasoning', 'Route', 'Time'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {logs.map(l => (
                      <tr key={l.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <span className={`text-xs font-bold px-2 py-0.5 rounded-full
                            ${l.action === 'buy' || l.action === 'booked' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                            {l.action.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-700">{l.ml_score?.toFixed(0)}%</td>
                        <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{l.reasoning || '—'}</td>
                        <td className="px-4 py-3 text-gray-400 text-xs font-mono">{l.route_id?.slice(0, 8) || '—'}</td>
                        <td className="px-4 py-3 text-gray-400">{new Date(l.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function SummaryCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
  }
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${colors[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      <div className="text-sm text-gray-500 mt-0.5">{label}</div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    confirmed: 'bg-green-100 text-green-700',
    pending: 'bg-yellow-100 text-yellow-700',
    failed: 'bg-red-100 text-red-700',
    cancelled: 'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${colors[status] || 'bg-gray-100 text-gray-500'}`}>
      {status}
    </span>
  )
}
