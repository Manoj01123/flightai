const CACHE = 'flightai-v4'
const PRECACHE = ['/', '/index.html', '/offline.html', '/manifest.json']

// ── Install ───────────────────────────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  )
})

// ── Activate ──────────────────────────────────────────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

// ── Fetch (network-first API, cache-first assets) ─────────────────────────────
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return
  const url = new URL(e.request.url)
  if (url.hostname !== self.location.hostname) return

  if (url.pathname.startsWith('/v1/') || url.hostname.includes('run.app')) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)))
    return
  }

  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached
      return fetch(e.request).then(res => {
        if (res.ok) {
          const clone = res.clone()
          caches.open(CACHE).then(c => c.put(e.request, clone))
        }
        return res
      }).catch(() => caches.match('/offline.html'))
    })
  )
})

// ── Web Push notifications ────────────────────────────────────────────────────
self.addEventListener('push', e => {
  let payload = {}
  try { payload = e.data?.json() ?? {} } catch { payload = { title: 'FlightAI', body: e.data?.text() ?? '' } }

  const title   = payload.title ?? 'FlightAI Alert'
  const options = {
    body:     payload.body ?? 'Your agent has an update.',
    icon:     '/icon-192.png',
    badge:    '/icon-192.png',
    vibrate:  [200, 100, 200],
    tag:      payload.tag ?? 'flightai-alert',
    renotify: true,
    data:     payload.data ?? {},
    actions:  payload.actions ?? [],
  }
  e.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', e => {
  e.notification.close()
  const action = e.action
  const data   = e.notification.data ?? {}
  let target   = '/dashboard'

  if (action === 'dismiss') return
  if (data.booking_id) target = `/bookings/${data.booking_id}/pay`
  else if (data.route_id) target = `/routes/${data.route_id}`

  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(cs => {
      const w = cs.find(c => c.url.includes(self.location.origin))
      if (w) { w.focus(); return w.navigate(target) }
      return clients.openWindow(target)
    })
  )
})
