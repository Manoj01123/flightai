import { useState } from 'react'
import { loadStripe } from '@stripe/stripe-js'
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js'
import api from '../lib/api'
import toast from 'react-hot-toast'

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY)

const AMOUNTS = [25, 50, 100, 200]

function CheckoutForm({ amount, onSuccess, onCancel }: {
  amount: number; onSuccess: () => void; onCancel: () => void
}) {
  const stripe = useStripe()
  const elements = useElements()
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!stripe || !elements) return
    setLoading(true)
    try {
      const { error, paymentIntent } = await stripe.confirmPayment({
        elements,
        confirmParams: { return_url: window.location.href },
        redirect: 'if_required',
      })
      if (error) {
        toast.error(error.message || 'Payment failed')
      } else if (paymentIntent?.status === 'succeeded') {
        await api.post('/v1/wallet/topup', {
          amount,
          stripe_payment_intent_id: paymentIntent.id,
          idempotency_key: paymentIntent.id,
        })
        toast.success(`$${amount} added to your wallet!`)
        onSuccess()
      }
    } catch {
      toast.error('Payment failed — please try again')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement className="mb-4" />
      <div className="flex gap-3 mt-4">
        <button type="button" onClick={onCancel}
          className="flex-1 border border-gray-300 text-gray-600 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50">
          Cancel
        </button>
        <button type="submit" disabled={!stripe || loading}
          className="flex-1 bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          {loading ? 'Processing…' : `Pay $${amount}`}
        </button>
      </div>
    </form>
  )
}

interface Props {
  onSuccess: () => void
  onCancel: () => void
}

export default function StripeTopupModal({ onSuccess, onCancel }: Props) {
  const [amount, setAmount] = useState(50)
  const [clientSecret, setClientSecret] = useState<string | null>(null)
  const [creatingIntent, setCreatingIntent] = useState(false)

  const createIntent = async (amt: number) => {
    setCreatingIntent(true)
    try {
      const res = await api.post('/v1/wallet/create-payment-intent', { amount: amt })
      setClientSecret(res.data.client_secret)
    } catch {
      toast.error('Could not initialize payment')
    } finally {
      setCreatingIntent(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl">
        <h3 className="font-semibold text-gray-900 text-lg mb-4">Add funds</h3>

        {!clientSecret ? (
          <>
            <div className="grid grid-cols-4 gap-2 mb-4">
              {AMOUNTS.map(a => (
                <button key={a} onClick={() => setAmount(a)}
                  className={`py-2 rounded-lg text-sm font-medium border transition-colors
                    ${amount === a ? 'border-blue-600 bg-blue-50 text-blue-600' : 'border-gray-200 text-gray-600 hover:border-gray-300'}`}>
                  ${a}
                </button>
              ))}
            </div>
            <div className="mb-5">
              <label className="block text-sm text-gray-600 mb-1">Custom amount</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
                <input type="number" value={amount} min={5} max={10000}
                  onChange={e => setAmount(Number(e.target.value))}
                  className="w-full border border-gray-300 rounded-lg pl-7 pr-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={onCancel}
                className="flex-1 border border-gray-300 text-gray-600 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50">
                Cancel
              </button>
              <button onClick={() => createIntent(amount)} disabled={creatingIntent || amount < 5}
                className="flex-1 bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                {creatingIntent ? 'Loading…' : `Continue with $${amount}`}
              </button>
            </div>
          </>
        ) : (
          <Elements stripe={stripePromise} options={{ clientSecret, appearance: { theme: 'stripe' } }}>
            <CheckoutForm amount={amount} onSuccess={onSuccess} onCancel={onCancel} />
          </Elements>
        )}
      </div>
    </div>
  )
}
