import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getBookings } from '../lib/api'
import { BookOpen, Download, ChevronRight } from 'lucide-react'
import { jsPDF } from 'jspdf'

interface Booking {
  id: string; status: string; price: string; airline: string
  origin: string; destination: string; departure_at: string
  pnr_encrypted?: string; created_at: string
}

const statusColor: Record<string, string> = {
  confirmed: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  failed: 'bg-red-100 text-red-700',
  refunded: 'bg-gray-100 text-gray-500',
}

export default function Bookings() {
  const [bookings, setBookings] = useState<Booking[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getBookings().then(r => setBookings(r.data)).finally(() => setLoading(false))
  }, [])

  const downloadReceipt = (b: Booking) => {
    const doc = new jsPDF()
    doc.setFontSize(20)
    doc.text('FlightAI Booking Receipt', 20, 20)
    doc.setFontSize(12)
    doc.text(`Booking ID: ${b.id}`, 20, 40)
    doc.text(`Route: ${b.origin} → ${b.destination}`, 20, 52)
    doc.text(`Departure: ${b.departure_at ? new Date(b.departure_at).toLocaleDateString() : '—'}`, 20, 64)
    doc.text(`Airline: ${b.airline || '—'}`, 20, 76)
    doc.text(`Amount paid: $${parseFloat(b.price).toFixed(2)} + $5.00 agent fee`, 20, 88)
    doc.text(`Status: ${b.status}`, 20, 100)
    doc.text(`Booked on: ${new Date(b.created_at).toLocaleDateString()}`, 20, 112)
    doc.save(`flightai-receipt-${b.id.slice(0, 8)}.pdf`)
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2"><BookOpen className="w-6 h-6" />My Bookings</h1>

      {loading ? (
        <div className="text-center py-20 text-gray-400">Loading…</div>
      ) : bookings.length === 0 ? (
        <div className="text-center py-20">
          <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-2 font-medium">No bookings yet</p>
          <p className="text-gray-400 text-sm mb-6">Add a route and let the AI find you a deal.</p>
          <Link to="/routes/new" className="bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700">
            Add a route
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {bookings.map(b => (
            <div key={b.id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="text-lg font-bold text-gray-900">{b.origin} → {b.destination}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColor[b.status] || 'bg-gray-100'}`}>
                      {b.status}
                    </span>
                  </div>
                  <div className="text-sm text-gray-500 space-y-0.5">
                    <div>Departure: {b.departure_at ? new Date(b.departure_at).toLocaleDateString() : '—'}</div>
                    <div>Airline: {b.airline || '—'}</div>
                    <div className="font-medium text-gray-800">Paid: ${parseFloat(b.price).toFixed(2)}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3 ml-4 shrink-0">
                  {b.status === 'confirmed' && (
                    <button onClick={() => downloadReceipt(b)}
                      className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800">
                      <Download className="w-4 h-4" /> Receipt
                    </button>
                  )}
                  <Link to={`/bookings/${b.id}`}
                    className="flex items-center gap-1 text-sm text-blue-600 hover:underline">
                    Details <ChevronRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>

              {b.status === 'failed' && (
                <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between">
                  <p className="text-sm text-red-600">Booking failed — seat may have sold out</p>
                  <Link to={`/error?type=booking_failed`} className="text-xs text-gray-400 hover:text-gray-600">
                    What happened?
                  </Link>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
