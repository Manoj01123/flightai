import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('jwt_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('jwt_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ──────────────────────────────────────────────────────────────────────
export const loginApi = (email: string, password: string) =>
  api.post('/v1/auth/login', { email, password })

export const registerApi = (email: string, password: string, firstName: string, lastName: string) =>
  api.post('/v1/auth/register', { email, password, first_name: firstName, last_name: lastName })

// ── Wallet ────────────────────────────────────────────────────────────────────
export const getWallet = () => api.get('/v1/wallet')
export const topupWallet = (amount: number, stripePaymentIntentId: string) =>
  api.post('/v1/wallet/topup', {
    amount,
    stripe_payment_intent_id: stripePaymentIntentId,
    idempotency_key: stripePaymentIntentId,
  })

// ── Routes ────────────────────────────────────────────────────────────────────
export const getRoutes = () => api.get('/v1/routes')
export const createRoute = (data: {
  origin: string; destination: string; date_from: string; date_to: string
  target_price: number; booking_mode: string
}) => api.post('/v1/routes', data)
export const patchRoute = (id: string, data: Partial<{ booking_mode: string; target_price: number }>) =>
  api.patch(`/v1/routes/${id}`, data)
export const deleteRoute = (id: string) => api.delete(`/v1/routes/${id}`)
export const getPriceSnapshots = (routeId: string) =>
  api.get(`/v1/routes/${routeId}/snapshots`)

// ── Bookings ──────────────────────────────────────────────────────────────────
export const getBookings = (routeId?: string) =>
  api.get('/v1/bookings', { params: routeId ? { route_id: routeId } : {} })
export const getBooking = (id: string) => api.get(`/v1/bookings/${id}`)
export const confirmBooking = (token: string) =>
  api.post(`/v1/bookings/confirm/${token}`)
export const createPaymentIntent = (bookingId: string) =>
  api.post(`/v1/bookings/${bookingId}/payment-intent`)
export const payBooking = (bookingId: string, paymentIntentId: string) =>
  api.post(`/v1/bookings/${bookingId}/pay`, { payment_intent_id: paymentIntentId })

// ── Flight search ─────────────────────────────────────────────────────────────
export const searchFlights = (params: {
  origin: string; destination: string; date: string
  adults?: number; cabin_class?: string; max_connections?: number
}) => api.get('/v1/flights/search', { params })

// ── Agent logs ────────────────────────────────────────────────────────────────
export const getAgentLogs = (routeId?: string) =>
  api.get('/v1/agent/logs', { params: { route_id: routeId, limit: 50 } })

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminGetUsers = () => api.get('/v1/admin/users')
export const adminGetBookings = () => api.get('/v1/admin/bookings')
