import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { confirmBooking } from '../lib/api'
import { CheckCircle, XCircle, Loader } from 'lucide-react'

export default function ConfirmBooking() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) return
    confirmBooking(token)
      .then(r => {
        setStatus('success')
        setMessage(`Booking confirmed! Your booking ID is ${r.data.booking_id}`)
      })
      .catch(err => {
        setStatus('error')
        setMessage(err.response?.data?.detail || 'This link has expired or already been used.')
      })
  }, [token])

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-10 w-full max-w-md text-center">
        {status === 'loading' && (
          <>
            <Loader className="w-12 h-12 text-blue-500 mx-auto mb-4 animate-spin" />
            <h2 className="text-xl font-semibold text-gray-800">Confirming your booking…</h2>
          </>
        )}
        {status === 'success' && (
          <>
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Booking Confirmed!</h2>
            <p className="text-gray-500 mb-6">{message}</p>
            <button onClick={() => navigate('/bookings')}
              className="bg-blue-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-blue-700">
              View my bookings
            </button>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Link Invalid</h2>
            <p className="text-gray-500 mb-6">{message}</p>
            <button onClick={() => navigate('/dashboard')}
              className="bg-gray-100 text-gray-700 px-6 py-2.5 rounded-lg font-medium hover:bg-gray-200">
              Go to dashboard
            </button>
          </>
        )}
      </div>
    </div>
  )
}
