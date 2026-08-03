import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getRoutes, deleteRoute } from '../lib/api'
import { Map, Plus, Trash2, TrendingDown } from 'lucide-react'
import toast from 'react-hot-toast'

interface Route {
  id: string; origin: string; destination: string; departure_date: string
  target_price: number; booking_mode: string; status: string; current_price?: number
}

const statusColor: Record<string, string> = {
  active: 'bg-blue-100 text-blue-700',
  booked: 'bg-green-100 text-green-700',
  expired: 'bg-red-100 text-red-700',
  paused: 'bg-gray-400 text-white',
  cancelled: 'bg-gray-100 text-gray-500',
}

export default function Routes() {
  const [routes, setRoutes] = useState<Route[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => getRoutes().then(r => setRoutes(r.data)).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('Remove this route?')) return
    try {
      await deleteRoute(id)
      toast.success('Route removed')
      load()
    } catch {
      toast.error('Failed to remove route')
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Map className="w-6 h-6" />My Routes</h1>
        <Link to="/routes/new"
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
          <Plus className="w-4 h-4" /> New Route
        </Link>
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400">Loading…</div>
      ) : routes.length === 0 ? (
        <div className="text-center py-20">
          <TrendingDown className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-4">No routes yet. Add a route and let the AI watch for deals.</p>
          <Link to="/routes/new" className="bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700">
            Add your first route
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {routes.map(r => (
            <div key={r.id} className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-1">
                  <span className="text-lg font-bold text-gray-900">{r.origin} → {r.destination}</span>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColor[r.status] || 'bg-gray-100'}`}>
                    {r.status}
                  </span>
                  <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">
                    Mode {r.booking_mode}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-sm text-gray-500">
                  <span>Departs: {r.departure_date}</span>
                  <span>Target: <span className="font-medium text-gray-700">${r.target_price}</span></span>
                  {r.current_price && (
                    <span>Current: <span className={`font-medium ${r.current_price <= r.target_price ? 'text-green-600' : 'text-gray-700'}`}>
                      ${r.current_price}
                    </span></span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Link to={`/routes/${r.id}`} className="text-sm text-blue-600 hover:underline">View</Link>
                <button onClick={() => handleDelete(r.id)} className="p-2 text-gray-400 hover:text-red-500 transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
