import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Map, Wallet, Zap, CheckCircle, ChevronRight } from 'lucide-react'

const STEPS = [
  {
    id: 1,
    icon: Map,
    title: 'Set up your first route',
    subtitle: 'Tell the AI which flight to watch',
    color: 'blue',
    description: 'Enter your origin, destination, travel date, and a target price. FlightAI will monitor that route 24/7 using real-time data and machine learning.',
    tip: 'Pro tip: set your target price 10–20% below current fares to give the AI room to find a real deal.',
    cta: 'Create a route',
    ctaPath: '/routes/new',
  },
  {
    id: 2,
    icon: Wallet,
    title: 'Top up your wallet',
    subtitle: 'Fund your account so the AI can book instantly',
    color: 'green',
    description: 'FlightAI uses a pre-funded wallet to book your flights without interrupting you. We add a $5 agent fee per booking — everything else goes straight to the airline.',
    tip: 'We recommend keeping at least $300 in your wallet so the AI can act immediately when a deal appears.',
    cta: 'Add funds',
    ctaPath: '/wallet',
  },
  {
    id: 3,
    icon: Zap,
    title: 'Choose your booking mode',
    subtitle: 'Decide how hands-on you want to be',
    color: 'purple',
    description: (
      <div className="space-y-3">
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
          <div className="font-semibold text-blue-800 text-sm">Mode A — Alert me first</div>
          <div className="text-blue-700 text-xs mt-1">When the AI finds a deal, it texts and emails you a confirmation link. You have 30 minutes to approve before the price expires.</div>
        </div>
        <div className="bg-purple-50 border border-purple-100 rounded-lg p-3">
          <div className="font-semibold text-purple-800 text-sm">Mode B — Auto-book</div>
          <div className="text-purple-700 text-xs mt-1">The AI books automatically the moment it finds a price at or below your target. No action needed from you — just check your email for the receipt.</div>
        </div>
      </div>
    ),
    tip: 'You can change the mode any time from the route detail page.',
    cta: 'Go to dashboard',
    ctaPath: '/dashboard',
  },
]

const colorMap: Record<string, string> = {
  blue: 'bg-blue-50 text-blue-600',
  green: 'bg-green-50 text-green-600',
  purple: 'bg-purple-50 text-purple-600',
}
const ringMap: Record<string, string> = {
  blue: 'ring-blue-600',
  green: 'ring-green-600',
  purple: 'ring-purple-600',
}
const btnMap: Record<string, string> = {
  blue: 'bg-blue-600 hover:bg-blue-700',
  green: 'bg-green-600 hover:bg-green-700',
  purple: 'bg-purple-600 hover:bg-purple-700',
}

export default function Onboarding() {
  const [step, setStep] = useState(0)
  const navigate = useNavigate()
  const current = STEPS[step]
  const Icon = current.icon

  const handleCta = () => {
    if (step < STEPS.length - 1) {
      navigate(current.ctaPath)
    } else {
      navigate('/dashboard')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        {/* Progress dots */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {STEPS.map((s, i) => (
            <button key={s.id} onClick={() => setStep(i)}
              className={`transition-all rounded-full ${i === step ? `w-6 h-2.5 ${btnMap[current.color]}` : i < step ? 'w-2.5 h-2.5 bg-gray-400' : 'w-2.5 h-2.5 bg-gray-200'}`} />
          ))}
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          {/* Step icon */}
          <div className={`w-14 h-14 rounded-xl flex items-center justify-center mb-5 ${colorMap[current.color]}`}>
            <Icon className="w-7 h-7" />
          </div>

          <div className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-1">
            Step {step + 1} of {STEPS.length}
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-1">{current.title}</h2>
          <p className="text-gray-500 text-sm mb-5">{current.subtitle}</p>

          <div className="text-gray-700 text-sm mb-5">
            {typeof current.description === 'string' ? <p>{current.description}</p> : current.description}
          </div>

          {current.tip && (
            <div className={`flex items-start gap-2 p-3 rounded-lg ring-1 ${ringMap[current.color]} ring-opacity-30 bg-opacity-5 mb-6 bg-${current.color}-50`}>
              <CheckCircle className="w-4 h-4 mt-0.5 shrink-0 text-gray-400" />
              <p className="text-xs text-gray-600">{current.tip}</p>
            </div>
          )}

          <div className="flex gap-3">
            {step > 0 && (
              <button onClick={() => setStep(s => s - 1)}
                className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm font-medium hover:bg-gray-50">
                Back
              </button>
            )}
            <button onClick={handleCta}
              className={`flex-1 text-white py-2.5 rounded-xl text-sm font-medium flex items-center justify-center gap-1.5 transition-colors ${btnMap[current.color]}`}>
              {current.cta} <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {step < STEPS.length - 1 && (
            <button onClick={() => navigate('/dashboard')}
              className="w-full text-center text-xs text-gray-400 hover:text-gray-600 mt-4">
              Skip setup — I'll explore on my own
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
