import { initializeApp, getApps, type FirebaseApp } from 'firebase/app'
import { getAuth, type Auth } from 'firebase/auth'
import { getMessaging, isSupported } from 'firebase/messaging'

let app: FirebaseApp | null = null
let auth: Auth | null = null

function getFirebaseApp(): FirebaseApp | null {
  if (app) return app
  const apiKey = import.meta.env.VITE_FIREBASE_API_KEY
  if (!apiKey) return null
  if (getApps().length > 0) {
    app = getApps()[0]
  } else {
    app = initializeApp({
      apiKey,
      authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
      storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
      messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
      appId: import.meta.env.VITE_FIREBASE_APP_ID,
    })
  }
  return app
}

export function getFirebaseAuth(): Auth | null {
  if (auth) return auth
  const a = getFirebaseApp()
  if (!a) return null
  auth = getAuth(a)
  return auth
}

export const getMessagingInstance = async () => {
  const a = getFirebaseApp()
  if (!a) return null
  try {
    const supported = await isSupported()
    return supported ? getMessaging(a) : null
  } catch {
    return null
  }
}
