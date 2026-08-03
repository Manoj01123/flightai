import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Plane, Wallet, Map, BookOpen, LayoutDashboard, LogOut, Film, Settings } from 'lucide-react'

const links = [
  { to: '/dashboard', label: 'Home',     icon: LayoutDashboard },
  { to: '/routes',    label: 'Routes',   icon: Map },
  { to: '/bookings',  label: 'Bookings', icon: BookOpen },
  { to: '/movies',    label: 'Movies',   icon: Film },
  { to: '/wallet',    label: 'Wallet',   icon: Wallet },
]

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => { logout(); navigate('/login') }
  const isActive = (to: string) => location.pathname === to || location.pathname.startsWith(to + '/')

  return (
    <>
      {/* Desktop top nav */}
      <nav className="hidden md:flex bg-white border-b border-gray-200 px-6 py-3 items-center justify-between sticky top-0 z-50 shadow-sm">
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
                ${isActive(to) ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-100'}`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <Link to="/settings" className="text-sm text-gray-600 hover:text-gray-900">
            {user?.first_name}
          </Link>
          <button onClick={handleLogout} className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-500 transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </nav>

      {/* Mobile top bar */}
      <nav className="md:hidden bg-white border-b border-gray-100 px-4 py-3 flex items-center justify-between sticky top-0 z-50">
        <Link to="/dashboard" className="flex items-center gap-2 font-bold text-blue-600">
          <Plane className="w-5 h-5" />
          FlightAI
        </Link>
        <div className="flex items-center gap-2">
          <Link to="/settings" className="p-2 rounded-full hover:bg-gray-100">
            <Settings className="w-5 h-5 text-gray-500" />
          </Link>
          <button onClick={handleLogout} className="p-2 rounded-full hover:bg-gray-100">
            <LogOut className="w-5 h-5 text-gray-500" />
          </button>
        </div>
      </nav>

      {/* Mobile bottom tab bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 pb-safe">
        <div className="flex items-stretch">
          {links.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 transition-colors
                ${isActive(to) ? 'text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}
            >
              <Icon className={`w-5 h-5 ${isActive(to) ? 'stroke-[2.5]' : 'stroke-[1.5]'}`} />
              <span className="text-[10px] font-medium">{label}</span>
              {isActive(to) && <span className="w-1 h-1 bg-blue-600 rounded-full absolute bottom-1" />}
            </Link>
          ))}
        </div>
      </nav>
    </>
  )
}
