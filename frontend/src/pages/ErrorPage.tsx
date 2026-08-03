import { Link, useSearchParams } from 'react-router-dom'
import { XCircle, AlertTriangle, Clock, Wallet } from 'lucide-react'

type ErrorType = 'booking_failed' | 'insufficient_funds' | 'route_expired' | 'generic'

const CONFIG: Record<ErrorType, {
  icon: any; iconBg: string; iconColor: string
  title: string; description: string
  primaryCta: string; primaryPath: string
  secondaryCta?: string; secondaryPath?: string
}> = {
  booking_failed: {
    icon: XCircle,
    iconBg: 'bg-red-100', iconColor: 'text-red-500',
    title: 'Booking failed',
    description: 'The AI agent found a deal but the booking couldn\'t be completed — the seat may have sold out, or there was a payment error. Your wallet has not been charged.',
    primaryCta: 'Try again with a new route',
    primaryPath: '/routes/new',
    secondaryCta: 'View my routes',
    secondaryPath: '/routes',
  },
  insufficient_funds: {
    icon: Wallet,
    iconBg: 'bg-amber-100', iconColor: 'text-amber-500',
    title: 'Insufficient wallet funds',
    description: 'Your wallet balance is too low to complete this booking. The AI agent found a deal but couldn\'t charge your wallet. Top up now to avoid missing the next opportunity.',
    primaryCta: 'Top up wallet',
    primaryPath: '/wallet',
    secondaryCta: 'View my routes',
    secondaryPath: '/routes',
  },
  route_expired: {
    icon: Clock,
    iconBg: 'bg-blue-100', iconColor: 'text-blue-500',
    title: 'Route expired',
    description: 'This route\'s departure date has passed. The AI agent has stopped watching it. Create a new route to track upcoming flights.',
    primaryCta: 'Create a new route',
    primaryPath: '/routes/new',
    secondaryCta: 'View booking history',
    secondaryPath: '/bookings',
  },
  generic: {
    icon: AlertTriangle,
    iconBg: 'bg-gray-100', iconColor: 'text-gray-500',
    title: 'Something went wrong',
    description: 'An unexpected error occurred. Please try again or contact support if the problem persists.',
    primaryCta: 'Go to dashboard',
    primaryPath: '/dashboard',
  },
}

export default function ErrorPage({ type }: { type?: ErrorType }) {
  const [params] = useSearchParams()
  const errorType: ErrorType = type || (params.get('type') as ErrorType) || 'generic'
  const config = CONFIG[errorType] || CONFIG.generic
  const Icon = config.icon
  const reason = params.get('reason')

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className={`w-20 h-20 ${config.iconBg} rounded-full flex items-center justify-center mx-auto mb-6`}>
          <Icon className={`w-10 h-10 ${config.iconColor}`} />
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-3">{config.title}</h1>
        <p className="text-gray-500 mb-4 leading-relaxed">{config.description}</p>

        {reason && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-6 text-left">
            <p className="text-xs font-semibold text-gray-400 mb-1">Error detail</p>
            <p className="text-sm text-gray-600">{reason}</p>
          </div>
        )}

        <div className="flex flex-col gap-3">
          <Link to={config.primaryPath}
            className="bg-blue-600 text-white px-6 py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors">
            {config.primaryCta}
          </Link>
          {config.secondaryCta && config.secondaryPath && (
            <Link to={config.secondaryPath}
              className="border border-gray-200 text-gray-600 px-6 py-3 rounded-xl font-medium hover:bg-gray-50 transition-colors">
              {config.secondaryCta}
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
