import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { getToken } from 'firebase/messaging'
import { loginApi, registerApi } from '../lib/api'
import api from '../lib/api'
import { getMessagingInstance } from '../lib/firebase'

interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  sms_notifications: boolean
  email_notifications: boolean
}

interface AuthContextType {
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, firstName: string, lastName: string) => Promise<void>
  logout: () => void
  loading: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

async function registerFcmToken() {
  try {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') return
    const messaging = await getMessagingInstance()
    if (!messaging) return
    const fcmToken = await getToken(messaging, {
      vapidKey: import.meta.env.VITE_FIREBASE_VAPID_KEY,
      serviceWorkerRegistration: await navigator.serviceWorker.ready,
    })
    if (fcmToken) {
      await api.patch('/v1/users/me', { fcm_token: fcmToken })
    }
  } catch {
    // Non-critical — push notifications are best-effort
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('jwt_token'))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem('jwt_user')
    if (stored && token) {
      try {
        const parsed = JSON.parse(stored)
        if (parsed && typeof parsed === 'object') setUser(parsed)
        else localStorage.removeItem('jwt_user')
      } catch {
        localStorage.removeItem('jwt_user')
        localStorage.removeItem('jwt_token')
      }
    }
    setLoading(false)
  }, [token])

  const login = async (email: string, password: string) => {
    const res = await loginApi(email, password)
    const { access_token, user: u } = res.data
    localStorage.setItem('jwt_token', access_token)
    localStorage.setItem('jwt_user', JSON.stringify(u))
    setToken(access_token)
    setUser(u)
    registerFcmToken()
  }

  const register = async (email: string, password: string, firstName: string, lastName: string) => {
    const res = await registerApi(email, password, firstName, lastName)
    const { access_token, user: u } = res.data
    localStorage.setItem('jwt_token', access_token)
    localStorage.setItem('jwt_user', JSON.stringify(u))
    setToken(access_token)
    setUser(u)
    registerFcmToken()
  }

  const logout = () => {
    localStorage.removeItem('jwt_token')
    localStorage.removeItem('jwt_user')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
