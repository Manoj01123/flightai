import { useState, useEffect } from 'react'
import { X, Download, Share } from 'lucide-react'

type BeforeInstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> }

export default function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [show, setShow] = useState(false)
  const [isIos, setIsIos] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    if (localStorage.getItem('pwa-install-dismissed')) return

    const ios = /iphone|ipad|ipod/i.test(navigator.userAgent)
    const standalone = (window.navigator as { standalone?: boolean }).standalone === true
      || window.matchMedia('(display-mode: standalone)').matches

    if (standalone) return  // already installed

    if (ios) {
      setIsIos(true)
      setTimeout(() => setShow(true), 3000)
      return
    }

    const handler = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
      setTimeout(() => setShow(true), 2000)
    }
    window.addEventListener('beforeinstallprompt', handler)
    return () => window.removeEventListener('beforeinstallprompt', handler)
  }, [])

  const handleInstall = async () => {
    if (!deferredPrompt) return
    await deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    if (outcome === 'accepted') dismiss()
    setDeferredPrompt(null)
  }

  const dismiss = () => {
    setShow(false)
    setDismissed(true)
    localStorage.setItem('pwa-install-dismissed', '1')
  }

  if (!show || dismissed) return null

  return (
    <div className="fixed bottom-20 left-4 right-4 md:left-auto md:right-6 md:w-80 z-50 bg-white rounded-2xl shadow-2xl border border-gray-100 p-4 animate-slide-up">
      <button onClick={dismiss} className="absolute top-3 right-3 text-gray-400 hover:text-gray-600">
        <X className="w-4 h-4" />
      </button>

      <div className="flex items-start gap-3">
        <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center flex-shrink-0">
          <span className="text-white text-xl">✈</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 text-sm">Install FlightAI</p>
          {isIos ? (
            <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
              Tap <Share className="inline w-3 h-3 mx-0.5" /> then <strong>Add to Home Screen</strong> to install
            </p>
          ) : (
            <p className="text-xs text-gray-500 mt-0.5">Get the full app experience</p>
          )}
        </div>
      </div>

      {!isIos && (
        <button
          onClick={handleInstall}
          className="mt-3 w-full flex items-center justify-center gap-2 bg-blue-600 text-white text-sm font-medium py-2.5 rounded-xl hover:bg-blue-700 transition-colors"
        >
          <Download className="w-4 h-4" />
          Install App
        </button>
      )}
    </div>
  )
}
