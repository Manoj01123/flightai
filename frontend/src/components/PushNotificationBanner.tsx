import { useState, useEffect } from 'react'
import { Bell, X } from 'lucide-react'
import api from '../lib/api'

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || ''

function urlBase64ToUint8Array(base64: string) {
  const pad = '='.repeat((4 - (base64.length % 4)) % 4)
  const b64 = (base64 + pad).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(b64)
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)))
}

export default function PushNotificationBanner() {
  const [status, setStatus] = useState<'idle' | 'asking' | 'granted' | 'denied'>('idle')
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return
    if (localStorage.getItem('push-dismissed')) { setDismissed(true); return }
    if (Notification.permission === 'granted') { setStatus('granted'); return }
    if (Notification.permission === 'denied')  { setStatus('denied');  return }
    setTimeout(() => setStatus('idle'), 4000)
  }, [])

  const subscribe = async () => {
    if (!VAPID_PUBLIC_KEY) { console.warn('VAPID_PUBLIC_KEY not set'); return }
    setStatus('asking')
    try {
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') { setStatus('denied'); return }

      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      })
      await api.post('/v1/notifications/push-subscribe', sub.toJSON())
      setStatus('granted')
    } catch (err) {
      console.error('Push subscribe failed', err)
      setStatus('idle')
    }
  }

  const dismiss = () => {
    setDismissed(true)
    localStorage.setItem('push-dismissed', '1')
  }

  if (dismissed || status === 'granted' || status === 'denied') return null
  if (status === 'idle' && Notification.permission !== 'default') return null

  return (
    <div className="mx-4 mb-3 bg-blue-50 border border-blue-200 rounded-xl p-3 flex items-center gap-3">
      <Bell className="w-5 h-5 text-blue-600 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-blue-900">Get price drop alerts</p>
        <p className="text-xs text-blue-600">We'll notify you when a fare hits your target</p>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={subscribe}
          disabled={status === 'asking'}
          className="text-xs font-semibold bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {status === 'asking' ? '...' : 'Enable'}
        </button>
        <button onClick={dismiss} className="text-blue-400 hover:text-blue-600">
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
