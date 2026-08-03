const CACHE = 'flightai-v2'
const PRECACHE = ['/', '/index.html', '/offline.html']

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return
  const url = new URL(e.request.url)
  // Network-first for API requests, cache-first for static assets
  if (url.pathname.startsWith('/v1/')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    )
  } else {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
        const clone = res.clone()
        caches.open(CACHE).then(c => c.put(e.request, clone))
        return res
      }).catch(() => caches.match('/offline.html')))
    )
  }
})

// FCM push notification handler
self.addEventListener('push', e => {
  const data = e.data?.json() ?? {}
  const title = data.notification?.title || 'FlightAI Alert'
  const options = {
    body: data.notification?.body || 'Your agent has an update.',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    data: data.data || {},
  }
  e.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', e => {
  e.notification.close()
  const routeId = e.notification.data?.route_id
  const url = routeId ? `/routes/${routeId}` : '/'
  e.waitUntil(clients.openWindow(url))
})
