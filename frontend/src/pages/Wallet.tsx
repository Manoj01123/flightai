import { useEffect, useState } from 'react'
import { getWallet } from '../lib/api'
import { Wallet as WalletIcon, ArrowUpCircle, ArrowDownCircle, Plus } from 'lucide-react'
import StripeTopupModal from '../components/StripeTopupModal'

interface WalletData {
  id: string; balance: string
  transactions: { id: string; amount: string; transaction_type: string; description: string; created_at: string }[]
}

export default function Wallet() {
  const [wallet, setWallet] = useState<WalletData | null>(null)
  const [showTopup, setShowTopup] = useState(false)

  const load = () => getWallet().then(r => setWallet(r.data)).catch(() => {})

  useEffect(() => {
    load()
    const timer = setInterval(load, 30_000)
    return () => clearInterval(timer)
  }, [])

  const txIcon = (type: string) =>
    type === 'TOPUP' ? <ArrowUpCircle className="w-4 h-4 text-green-500" /> : <ArrowDownCircle className="w-4 h-4 text-red-400" />

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2"><WalletIcon className="w-6 h-6" />Wallet</h1>

      <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl p-8 text-white mb-6">
        <p className="text-blue-200 text-sm mb-1">Available balance</p>
        <p className="text-4xl font-bold">${wallet ? parseFloat(wallet.balance).toFixed(2) : '—'}</p>
        <button onClick={() => setShowTopup(true)}
          className="mt-6 bg-white text-blue-600 font-semibold px-5 py-2.5 rounded-lg flex items-center gap-2 hover:bg-blue-50 transition-colors">
          <Plus className="w-4 h-4" /> Add funds
        </button>
      </div>

      {showTopup && (
        <StripeTopupModal
          onSuccess={() => { setShowTopup(false); load() }}
          onCancel={() => setShowTopup(false)}
        />
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Transaction history</h2>
        {!wallet?.transactions?.length ? (
          <p className="text-gray-400 text-sm text-center py-8">No transactions yet</p>
        ) : (
          <div className="space-y-3">
            {wallet.transactions.map(tx => (
              <div key={tx.id} className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-0">
                {txIcon(tx.transaction_type)}
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-800">{tx.description}</p>
                  <p className="text-xs text-gray-400">{new Date(tx.created_at).toLocaleDateString()}</p>
                </div>
                <span className={`font-semibold text-sm ${tx.transaction_type === 'TOPUP' ? 'text-green-600' : 'text-red-500'}`}>
                  {tx.transaction_type === 'TOPUP' ? '+' : '-'}${Math.abs(parseFloat(tx.amount)).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
