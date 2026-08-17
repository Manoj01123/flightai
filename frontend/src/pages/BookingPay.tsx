import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { loadStripe } from '@stripe/stripe-js'
import { Elements, useStripe, PaymentRequestButtonElement } from '@stripe/react-stripe-js'
import { CheckCircle, Plane, Loader } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || '')

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

function PaymentForm({ booking }: { booking: Booking }) {
  const stripe = useStripe()
  const navigate = useNavigate()
  const [clientSecret, setClientSecret] = useState<string | null>(null)
  const [paymentRequest, setPaymentRequest] = useState<any>(null)
  const [paid, setPaid] = useState(false)
  const [paying, setPaying] = useState(false)

  useEffect(() => {
    api.post(`/v1/bookings/${booking.id}/payment-intent`)
      .then(r => setClientSecret(r.data.client_secret))
      .catch(() => toast.error('Could not initialize payment'))
  }, [booking.id])

  useEffect(() => {
    if (!stripe || !clientSecret) return

    const pr = stripe.paymentRequest({
      country: 'US',
      currency: 'usd',
      total: {
        label: `${booking.origin} → ${booking.destination}`,
        amount: Math.round(parseFloat(booking.price) * 100),
      },
      requestPayerName: true,
      requestPayerEmail: true,
    })

    pr.canMakePayment().then(result => {
      if (result) setPaymentRequest(pr)
    })

    pr.on('paymentmethod', async (ev: any) => {
      setPaying(true)
      try {
        const { error, paymentIntent } = await stripe.confirmCardPayment(
          clientSecret,
          { payment_method: ev.paymentMethod.id },
          { handleActions: false }
        )

        if (error) {
          ev.complete('fail')
          toast.error(error.message || 'Payment failed')
          setPaying(false)
          return
        }

        ev.complete('success')

        if (paymentIntent!.status === 'requires_action') {
          await stripe.confirmCardPayment(clientSecret)
        }

        await api.post(`/v1/bookings/${booking.id}/pay`, {
          payment_intent_id: paymentIntent!.id,
        })

        setPaid(true)
        toast.success('Booking confirmed!')
        setTimeout(() => navigate('/bookings'), 2500)
      } catch {
        ev.complete('fail')
        toast.error('Payment failed — please try again')
        setPaying(false)
      }
    })

    setPaymentRequest(pr)
  }, [stripe, clientSecret, booking])

  if (paid) {
    return (
      <div className="flex flex-col items-center py-16">
        <CheckCircle className="w-20 h-20 text-green-500 mb-4" />
        <h2 className="text-2xl font-bold text-gray-900 mb-2">You're booked!</h2>
        <p className="text-gray-500 text-sm">Taking you to your bookings…</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Flight card */}
      <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl p-6 text-white shadow-lg">
        <p className="text-xs font-semibold uppercase tracking-widest opacity-70 mb-4">Your AI agent found this deal</p>
        <div className="flex items-center justify-between mb-6">
          <div className="text-center">
            <p className="text-4xl font-bold tracking-tight">{booking.origin}</p>
          </div>
          <div className="flex flex-col items-center gap-1.5 flex-1 px-4">
            <div className="w-full flex items-center gap-1">
              <div className="flex-1 h-px bg-white/30" />
              <Plane className="w-4 h-4 rotate-90 opacity-80" />
              <div className="flex-1 h-px bg-white/30" />
            </div>
            {booking.airline && (
              <p className="text-xs opacity-70">{booking.airline}</p>
            )}
          </div>
          <div className="text-center">
            <p className="text-4xl font-bold tracking-tight">{booking.destination}</p>
          </div>
        </div>
        {booking.departure_at && (
          <p className="text-center text-sm opacity-80 mb-4">
            {new Date(booking.departure_at).toLocaleDateString('en-US', {
              weekday: 'long', month: 'short', day: 'numeric',
            })}
          </p>
        )}
        <div className="border-t border-white/20 pt-4 flex items-center justify-between">
          <p className="text-sm opacity-80">Total to pay</p>
          <p className="text-3xl font-bold">${parseFloat(booking.price).toFixed(2)}</p>
        </div>
      </div>

      {/* Pay section */}
      {!clientSecret ? (
        <div className="flex items-center justify-center py-6">
          <Loader className="w-5 h-5 animate-spin text-blue-600" />
          <span className="ml-2 text-sm text-gray-500">Loading payment…</span>
        </div>
      ) : paying ? (
        <div className="flex items-center justify-center py-6 gap-2">
          <Loader className="w-5 h-5 animate-spin text-blue-600" />
          <span className="text-sm text-gray-600">Processing…</span>
        </div>
      ) : paymentRequest ? (
        <div className="space-y-3">
          <PaymentRequestButtonElement
            options={{
              paymentRequest,
              style: {
                paymentRequestButton: { type: 'buy', theme: 'dark', height: '54px' },
              },
            }}
          />
          <p className="text-center text-xs text-gray-400">
            Tap above · Authenticate with Face ID or Touch ID
          </p>
          <p className="text-center text-xs text-gray-300">Secured by Stripe</p>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 text-sm text-amber-800">
          <p className="font-semibold mb-1">Apple Pay not available here</p>
          <p>Open this page in <strong>Safari on your iPhone</strong> to pay with Apple Pay and Face ID.</p>
          <p className="mt-2 text-xs text-amber-600">
            URL: <span className="font-mono">frontend-t7zk5pacvq-uc.a.run.app/bookings/{booking.id}/pay</span>
          </p>
        </div>
      )}
    </div>
  )
}

export default function BookingPay() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [booking, setBooking] = useState<Booking | null>(null)
  const [error, setError] = useState('')

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
      .catch(() => setError('Booking not found or you don\'t have access.'))
  }, [id])

  return (
    <div className="max-w-md mx-auto px-4 py-8">
      <button
        onClick={() => navigate(-1)}
        className="text-sm text-gray-500 hover:text-gray-700 mb-6 flex items-center gap-1"
      >
        ← Back
      </button>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Complete Booking</h1>
      <p className="text-gray-500 text-sm mb-8">
        Pay now to lock in this price before it disappears.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {!booking && !error && (
        <div className="flex justify-center py-16">
          <Loader className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      )}

      {booking && (
        <Elements stripe={stripePromise}>
          <PaymentForm booking={booking} />
        </Elements>
      )}
    </div>
  )
}
