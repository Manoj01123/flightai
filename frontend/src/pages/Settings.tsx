import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { Settings as SettingsIcon, Bell } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'

export default function Settings() {
  const { user } = useAuth()
  const [sms, setSms] = useState(user?.sms_notifications ?? true)
  const [email, setEmail] = useState(user?.email_notifications ?? true)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await api.patch('/v1/users/me', { sms_notifications: sms, email_notifications: email })
      toast.success('Settings saved')
    } catch {
      toast.error('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <SettingsIcon className="w-6 h-6" />Settings
      </h1>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-6">
        <div>
          <h2 className="font-semibold text-gray-800 flex items-center gap-2 mb-4">
            <Bell className="w-4 h-4" />Notification Preferences
          </h2>
          <div className="space-y-4">
            <Toggle label="SMS notifications" description="Receive deal alerts and booking confirmations via text" checked={sms} onChange={setSms} />
            <Toggle label="Email notifications" description="Receive booking confirmations and receipts via email" checked={email} onChange={setEmail} />
          </div>
        </div>

        <div className="border-t pt-4">
          <h2 className="font-semibold text-gray-800 mb-3">Account</h2>
          <div className="text-sm text-gray-600 space-y-1">
            <div><span className="text-gray-400">Name:</span> {user?.first_name} {user?.last_name}</div>
            <div><span className="text-gray-400">Email:</span> {user?.email}</div>
          </div>
        </div>

        <button onClick={save} disabled={saving}
          className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
          {saving ? 'Saving…' : 'Save settings'}
        </button>
      </div>
    </div>
  )
}

function Toggle({ label, description, checked, onChange }: {
  label: string; description: string; checked: boolean; onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <div className="text-sm font-medium text-gray-800">{label}</div>
        <div className="text-xs text-gray-500 mt-0.5">{description}</div>
      </div>
      <button onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors shrink-0 ${checked ? 'bg-blue-600' : 'bg-gray-200'}`}>
        <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-6' : 'translate-x-1'}`} />
      </button>
    </div>
  )
}
