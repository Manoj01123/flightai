import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Plane, CreditCard, User, Lock, ChevronRight, CheckCircle, Loader, ArrowLeft } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Booking {
  id: string
  route_id: string
  origin: string
  destination: string
  price: string
  airline: string | null
  departure_at: string | null
  status: string
}

const AIRPORT: Record<string, string> = {
  PHX: 'Phoenix Sky Harbor', BOS: 'Boston Logan', ORD: "Chicago O'Hare",
  LAX: 'Los Angeles Intl', MIA: 'Miami Intl', JFK: 'New York JFK',
  SFO: 'San Francisco Intl', DEN: 'Denver Intl', SEA: 'Seattle-Tacoma',
  DFW: 'Dallas/Fort Worth', ATL: 'Atlanta Hartsfield',
}

function airportName(code: string) {
  return AIRPORT[code] ?? code
}

function arrivalTime(dep: string, origin: string, dest: string) {
  const durations: Record<string, number> = {
    'PHX-BOS': 310, 'PHX-ORD': 215, 'PHX-LAX': 70, 'PHX-MIA': 290,
    'PHX-JFK': 300, 'PHX-SFO': 100, 'PHX-DEN': 95,
  }
  const key = `${origin}-${dest}`
  const mins = durations[key] ?? 150
  const d = new Date(dep)
  d.setMinutes(d.getMinutes() + mins)
  return { time: d, mins }
}

function fmt(d: Date, style: 'time' | 'date') {
  if (style === 'time') return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
}

function dur(mins: number) {
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

export default function BookingPay() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [booking, setBooking] = useState<Booking | null>(null)
  const [error, setError] = useState('')
  const [step, setStep] = useState<'details' | 'payment' | 'done'>('details')
  const [paying, setPaying] = useState(false)

  const [passenger, setPassenger] = useState({
    firstName: 'Demo', lastName: 'User', email: 'demo@flightai.dev', phone: '+1 (555) 012-3456',
  })
  const [card, setCard] = useState({
    number: '4242 4242 4242 4242', expiry: '12/28', cvv: '123', name: 'Demo User',
  })

  useEffect(() => {
    if (!id) return
    api.get(`/v1/bookings/${id}`)
      .then(r => {
        if (r.data.status !== 'pending') {
          toast('This booking is already ' + r.data.status)
          navigate('/bookings')
        } else {
          setBooking(r.data)
        }
      })
      .catch(() => setError("Booking not found or you don't have access."))
  }, [id])

  const handlePay = async () => {
    setPaying(true)
    await new Promise(r => setTimeout(r, 2200))
    setPaying(false)
    setStep('done')
  }

  if (!booking && !error) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <Loader className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-md mx-auto px-4 py-12 text-center">
        <p className="text-red-600">{error}</p>
        <Link to="/bookings" className="text-blue-600 text-sm mt-4 inline-block">← Back to bookings</Link>
      </div>
    )
  }

  if (step === 'done') {
    return (
      <div className="max-w-md mx-auto px-4 py-16 text-center">
        <div className="w-24 h-24 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <CheckCircle className="w-12 h-12 text-green-500" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">You're booked!</h1>
        <p className="text-gray-500 mb-1">
          {booking!.origin} → {booking!.destination}
        </p>
        {booking!.departure_at && (
          <p className="text-gray-400 text-sm mb-2">
            {fmt(new Date(booking!.departure_at), 'date')}
          </p>
        )}
        <p className="text-2xl font-bold text-green-600 mb-6">
          ${parseFloat(booking!.price).toFixed(2)} paid
        </p>
        <p className="text-gray-400 text-sm mb-8">
          Confirmation sent to {passenger.email}
        </p>
        <Link
          to="/bookings"
          className="bg-blue-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors"
        >
          View my bookings
        </Link>
      </div>
    )
  }

  const dep = booking!.departure_at ? new Date(booking!.departure_at) : null
  const arr = dep ? arrivalTime(booking!.departure_at!, booking!.origin, booking!.destination) : null
  const baseFare = parseFloat(booking!.price)
  const agentFee = 5.00
  const taxes = parseFloat((baseFare * 0.075).toFixed(2))
  const total = (baseFare + agentFee + taxes).toFixed(2)

  return (
    <div className="max-w-lg mx-auto px-4 py-6 pb-24">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(-1)} className="p-2 rounded-full hover:bg-gray-100 transition-colors">
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-gray-900">Complete Booking</h1>
          <p className="text-xs text-gray-400">AI agent found this deal · lock in the price now</p>
        </div>
      </div>

      {/* Progress steps */}
      <div className="flex items-center gap-2 mb-6">
        {['Passenger', 'Payment', 'Done'].map((label, i) => {
          const idx = ['details', 'payment', 'done'].indexOf(step)
          const active = i === idx
          const done = i < idx
          return (
            <div key={label} className="flex items-center gap-2 flex-1">
              <div className={`w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center shrink-0
                ${done ? 'bg-blue-600 text-white' : active ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-400'}`}>
                {done ? '✓' : i + 1}
              </div>
              <span className={`text-xs ${active ? 'text-blue-600 font-semibold' : 'text-gray-400'}`}>{label}</span>
              {i < 2 && <div className="flex-1 h-px bg-gray-200" />}
            </div>
          )
        })}
      </div>

      {/* Flight card */}
      <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-5 text-white mb-5 shadow-lg">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center shrink-0">
            <Plane className="w-3 h-3 text-white" />
          </div>
          <span className="text-xs text-slate-300 font-medium">
            {booking!.airline ?? 'Airline'} · AI Agent Booked
          </span>
        </div>

        {/* Route row */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-4xl font-black tracking-tight">{booking!.origin}</p>
            <p className="text-xs text-slate-400 mt-0.5">{airportName(booking!.origin)}</p>
            {dep && <p className="text-sm font-semibold mt-1">{fmt(dep, 'time')}</p>}
          </div>

          <div className="flex flex-col items-center flex-1 px-3">
            <div className="w-full flex items-center gap-1 mb-1">
              <div className="flex-1 h-px bg-slate-600" />
              <Plane className="w-4 h-4 text-slate-400 rotate-90" />
              <div className="flex-1 h-px bg-slate-600" />
            </div>
            {arr && <p className="text-xs text-slate-400">{dur(arr.mins)}</p>}
            <p className="text-xs text-slate-500 mt-0.5">Nonstop</p>
          </div>

          <div className="text-right">
            <p className="text-4xl font-black tracking-tight">{booking!.destination}</p>
            <p className="text-xs text-slate-400 mt-0.5">{airportName(booking!.destination)}</p>
            {arr && <p className="text-sm font-semibold mt-1">{fmt(arr.time, 'time')}</p>}
          </div>
        </div>

        {dep && (
          <div className="border-t border-slate-700 pt-3 flex items-center justify-between text-xs text-slate-300">
            <span>{fmt(dep, 'date')}</span>
            <span className="text-green-400 font-semibold text-base">${baseFare.toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* STEP 1 — Passenger details */}
      {step === 'details' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-200 p-5">
            <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <User className="w-4 h-4 text-blue-500" />
              Passenger details
            </h2>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">First name</label>
                <input
                  value={passenger.firstName}
                  onChange={e => setPassenger(p => ({ ...p, firstName: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Last name</label>
                <input
                  value={passenger.lastName}
                  onChange={e => setPassenger(p => ({ ...p, lastName: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
              <input
                type="email"
                value={passenger.email}
                onChange={e => setPassenger(p => ({ ...p, email: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Phone</label>
              <input
                value={passenger.phone}
                onChange={e => setPassenger(p => ({ ...p, phone: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Order summary */}
          <div className="bg-white rounded-2xl border border-gray-200 p-5">
            <h2 className="font-semibold text-gray-800 mb-3">Order summary</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between text-gray-600">
                <span>Base fare</span><span>${baseFare.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>Taxes &amp; fees</span><span>${taxes.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>FlightAI agent fee</span><span>$5.00</span>
              </div>
              <div className="flex justify-between font-bold text-gray-900 pt-2 border-t border-gray-100 text-base">
                <span>Total</span><span>${total}</span>
              </div>
            </div>
          </div>

          <button
            onClick={() => setStep('payment')}
            className="w-full bg-blue-600 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-blue-700 transition-colors"
          >
            Continue to payment <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* STEP 2 — Payment */}
      {step === 'payment' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-200 p-5">
            <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-blue-500" />
              Card details
            </h2>
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-500 mb-1">Card number</label>
              <div className="relative">
                <input
                  value={card.number}
                  onChange={e => setCard(c => ({ ...c, number: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 pr-16"
                  placeholder="1234 5678 9012 3456"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex gap-1">
                  <div className="w-6 h-4 bg-blue-600 rounded-sm opacity-80" />
                  <div className="w-6 h-4 bg-red-500 rounded-sm opacity-80 -ml-2" />
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Expiry</label>
                <input
                  value={card.expiry}
                  onChange={e => setCard(c => ({ ...c, expiry: e.target.value }))}
                  placeholder="MM/YY"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">CVV</label>
                <input
                  value={card.cvv}
                  onChange={e => setCard(c => ({ ...c, cvv: e.target.value }))}
                  placeholder="123"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Name on card</label>
              <input
                value={card.name}
                onChange={e => setCard(c => ({ ...c, name: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Total reminder */}
          <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 flex items-center justify-between">
            <span className="text-sm text-blue-700 font-medium">Total charge</span>
            <span className="text-xl font-bold text-blue-700">${total}</span>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-gray-400 justify-center">
            <Lock className="w-3 h-3" />
            Secured by Stripe · 256-bit SSL encryption
          </div>

          <button
            onClick={handlePay}
            disabled={paying}
            className="w-full bg-black text-white py-4 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-gray-900 disabled:opacity-60 transition-colors"
          >
            {paying ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Processing…
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" className="h-5 w-5 fill-white">
                  <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
                </svg>
                Pay ${total} with Apple Pay
              </>
            )}
          </button>

          <button onClick={() => setStep('details')} className="w-full text-sm text-gray-400 hover:text-gray-600 py-1">
            ← Back to passenger details
          </button>
        </div>
      )}
    </div>
  )
}
