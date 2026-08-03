import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getBooking } from '../lib/api'
import { BookOpen, Download, ArrowLeft, Plane, CreditCard, Hash } from 'lucide-react'
import { jsPDF } from 'jspdf'

interface Booking {
  id: string; status: string; price: string; airline: string
  origin: string; destination: string; departure_at: string
  arrival_at?: string; flight_number?: string
  pnr_encrypted?: string; agent_fee?: string; created_at: string
  route_id?: string
}

const statusColor: Record<string, string> = {
  confirmed: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  failed: 'bg-red-100 text-red-700',
  refunded: 'bg-gray-100 text-gray-500',
}

export default function BookingDetail() {
  const { id } = useParams<{ id: string }>()
  const [booking, setBooking] = useState<Booking | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!id) return
    getBooking(id)
      .then(r => setBooking(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [id])

  const downloadReceipt = () => {
    if (!booking) return
    const doc = new jsPDF()
    const agentFee = parseFloat(booking.agent_fee || '5')
    const fare = parseFloat(booking.price)

    doc.setFillColor(37, 99, 235)
    doc.rect(0, 0, 210, 40, 'F')
    doc.setTextColor(255, 255, 255)
    doc.setFontSize(22)
    doc.text('FlightAI', 20, 18)
    doc.setFontSize(11)
    doc.text('Booking Receipt', 20, 28)
    doc.text(`Generated ${new Date().toLocaleDateString()}`, 140, 28)

    doc.setTextColor(30, 30, 30)
    doc.setFontSize(16)
    doc.text(`${booking.origin}  →  ${booking.destination}`, 20, 58)

    doc.setFontSize(10)
    doc.setTextColor(100, 100, 100)
    const rows = [
      ['Booking ID', booking.id],
      ['Status', booking.status],
      ['Airline', booking.airline || '—'],
      ['Flight', booking.flight_number || '—'],
      ['Departure', booking.departure_at ? new Date(booking.departure_at).toLocaleString() : '—'],
      ['Arrival', booking.arrival_at ? new Date(booking.arrival_at).toLocaleString() : '—'],
      ['PNR', booking.pnr_encrypted ? `****${booking.pnr_encrypted.slice(-4)}` : '—'],
      ['Booked on', new Date(booking.created_at).toLocaleString()],
    ]
    let y = 74
    rows.forEach(([label, val]) => {
      doc.setTextColor(100)
      doc.text(label, 20, y)
      doc.setTextColor(30)
      doc.text(String(val), 90, y)
      y += 12
    })

    doc.setDrawColor(220)
    doc.line(20, y + 4, 190, y + 4)
    y += 14
    doc.setTextColor(100)
    doc.text('Fare', 20, y)
    doc.setTextColor(30)
    doc.text(`$${fare.toFixed(2)}`, 160, y, { align: 'right' })
    y += 12
    doc.setTextColor(100)
    doc.text('Agent fee', 20, y)
    doc.setTextColor(30)
    doc.text(`$${agentFee.toFixed(2)}`, 160, y, { align: 'right' })
    y += 12
    doc.setFontSize(12)
    doc.setTextColor(30)
    doc.text('Total charged', 20, y)
    doc.text(`$${(fare + agentFee).toFixed(2)}`, 160, y, { align: 'right' })

    doc.setFontSize(9)
    doc.setTextColor(150)
    doc.text('Thank you for using FlightAI — powered by Gemini AI', 20, 272)
    doc.save(`flightai-receipt-${booking.id.slice(0, 8)}.pdf`)
  }

  if (loading) return (
    <div className="max-w-2xl mx-auto px-6 py-20 text-center text-gray-400">Loading booking…</div>
  )

  if (error || !booking) return (
    <div className="max-w-2xl mx-auto px-6 py-20 text-center">
      <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <BookOpen className="w-8 h-8 text-red-500" />
      </div>
      <h2 className="text-xl font-bold text-gray-900 mb-2">Booking not found</h2>
      <p className="text-gray-500 mb-6">This booking doesn't exist or you don't have access to it.</p>
      <Link to="/bookings" className="bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700">
        Back to bookings
      </Link>
    </div>
  )

  const fare = parseFloat(booking.price)
  const agentFee = parseFloat(booking.agent_fee || '5')

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <Link to="/bookings" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeft className="w-4 h-4" /> Back to bookings
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{booking.origin} → {booking.destination}</h1>
          <span className={`inline-block mt-1 text-xs font-medium px-2.5 py-1 rounded-full ${statusColor[booking.status] || 'bg-gray-100 text-gray-500'}`}>
            {booking.status}
          </span>
        </div>
        {booking.status === 'confirmed' && (
          <button onClick={downloadReceipt}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700">
            <Download className="w-4 h-4" /> Download receipt
          </button>
        )}
      </div>

      {/* Flight details */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
        <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2"><Plane className="w-4 h-4" />Flight details</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <Detail label="Airline" value={booking.airline || '—'} />
          <Detail label="Flight number" value={booking.flight_number || '—'} />
          <Detail label="Departure" value={booking.departure_at ? new Date(booking.departure_at).toLocaleString() : '—'} />
          <Detail label="Arrival" value={booking.arrival_at ? new Date(booking.arrival_at).toLocaleString() : '—'} />
        </div>
      </div>

      {/* PNR */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
        <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2"><Hash className="w-4 h-4" />Booking reference</h2>
        <div className="text-sm">
          <Detail label="PNR (masked)" value={booking.pnr_encrypted ? `****${booking.pnr_encrypted.slice(-4)}` : '—'} />
          <Detail label="Booking ID" value={booking.id} />
          <Detail label="Booked on" value={new Date(booking.created_at).toLocaleString()} />
        </div>
      </div>

      {/* Price breakdown */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2"><CreditCard className="w-4 h-4" />Price breakdown</h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between text-gray-600">
            <span>Flight fare</span><span>${fare.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-gray-600">
            <span>FlightAI agent fee</span><span>${agentFee.toFixed(2)}</span>
          </div>
          <div className="flex justify-between font-semibold text-gray-900 pt-2 border-t border-gray-100 mt-2">
            <span>Total charged</span><span>${(fare + agentFee).toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="py-1">
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className="text-gray-800 font-medium break-all">{value}</p>
    </div>
  )
}
