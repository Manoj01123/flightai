import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Navbar from './components/Navbar'

import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Wallet from './pages/Wallet'
import RoutesPage from './pages/Routes'
import NewRoute from './pages/NewRoute'
import RouteDetail from './pages/RouteDetail'
import Bookings from './pages/Bookings'
import BookingDetail from './pages/BookingDetail'
import ConfirmBooking from './pages/ConfirmBooking'
import Settings from './pages/Settings'
import Admin from './pages/Admin'
import Onboarding from './pages/Onboarding'
import ErrorPage from './pages/ErrorPage'
import ErrorBoundary from './components/ErrorBoundary'

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main>{children}</main>
    </div>
  )
}

function Protected({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute><AppLayout>{children}</AppLayout></ProtectedRoute>
}

export default function App() {
  return (
    <ErrorBoundary>
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/confirm/:token" element={<ConfirmBooking />} />
          <Route path="/error" element={<AppLayout><ErrorPage /></AppLayout>} />

          {/* Protected */}
          <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
          <Route path="/wallet" element={<Protected><Wallet /></Protected>} />
          <Route path="/routes" element={<Protected><RoutesPage /></Protected>} />
          <Route path="/routes/new" element={<Protected><NewRoute /></Protected>} />
          <Route path="/routes/:id" element={<Protected><RouteDetail /></Protected>} />
          <Route path="/bookings" element={<Protected><Bookings /></Protected>} />
          <Route path="/bookings/:id" element={<Protected><BookingDetail /></Protected>} />
          <Route path="/settings" element={<Protected><Settings /></Protected>} />
          <Route path="/admin" element={<Protected><Admin /></Protected>} />

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ErrorBoundary>
  )
}
