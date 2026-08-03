import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Plane, Wallet, Map, BookOpen, LayoutDashboard, LogOut } from 'lucide-react'

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/routes', label: 'Routes', icon: Map },
  { to: '/bookings', label: 'Bookings', icon: BookOpen },
  { to: '/wallet', label: 'Wallet', icon: Wallet },
]

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between sticky top-0 z-50 shadow-sm">
      <Link to="/dashboard" className="flex items-center gap-2 font-bold text-blue-600 text-lg">
        <Plane className="w-5 h-5" />
        FlightAI
      </Link>
      <div className="flex items-center gap-1">
        {links.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors
              ${location.pathname === to
                ? 'bg-blue-50 text-blue-600'
                : 'text-gray-600 hover:bg-gray-100'}`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-600">{user?.first_name}</span>
        <button onClick={handleLogout} className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-500 transition-colors">
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </nav>
  )
}
