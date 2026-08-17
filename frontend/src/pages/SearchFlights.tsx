import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchFlights, createRoute } from '../lib/api'
import { Plane, ArrowLeftRight, Search, Clock, Loader, ChevronDown } from 'lucide-react'
import toast from 'react-hot-toast'

// Major US + international airports
const AIRPORTS = [
  { code: 'ATL', city: 'Atlanta', name: 'Hartsfield-Jackson' },
  { code: 'LAX', city: 'Los Angeles', name: 'Los Angeles Intl' },
  { code: 'ORD', city: 'Chicago', name: "O'Hare Intl" },
  { code: 'DFW', city: 'Dallas', name: 'Dallas/Fort Worth' },
  { code: 'DEN', city: 'Denver', name: 'Denver Intl' },
  { code: 'JFK', city: 'New York', name: 'John F. Kennedy' },
  { code: 'SFO', city: 'San Francisco', name: 'San Francisco Intl' },
  { code: 'SEA', city: 'Seattle', name: 'Seattle-Tacoma' },
  { code: 'LAS', city: 'Las Vegas', name: 'Harry Reid Intl' },
  { code: 'MCO', city: 'Orlando', name: 'Orlando Intl' },
  { code: 'EWR', city: 'Newark', name: 'Newark Liberty' },
  { code: 'MIA', city: 'Miami', name: 'Miami Intl' },
  { code: 'PHX', city: 'Phoenix', name: 'Phoenix Sky Harbor' },
  { code: 'IAH', city: 'Houston', name: 'George Bush Intercontinental' },
  { code: 'BOS', city: 'Boston', name: 'Logan Intl' },
  { code: 'MSP', city: 'Minneapolis', name: 'Minneapolis-St Paul' },
  { code: 'DTW', city: 'Detroit', name: 'Detroit Metropolitan' },
  { code: 'FLL', city: 'Fort Lauderdale', name: 'Fort Lauderdale-Hollywood' },
  { code: 'PHL', city: 'Philadelphia', name: 'Philadelphia Intl' },
  { code: 'LGA', city: 'New York', name: 'LaGuardia' },
  { code: 'BWI', city: 'Baltimore', name: 'Baltimore/Washington' },
  { code: 'SLC', city: 'Salt Lake City', name: 'Salt Lake City Intl' },
  { code: 'DCA', city: 'Washington DC', name: 'Reagan National' },
  { code: 'IAD', city: 'Washington DC', name: 'Dulles Intl' },
  { code: 'MDW', city: 'Chicago', name: 'Midway Intl' },
  { code: 'HNL', city: 'Honolulu', name: 'Daniel K. Inouye Intl' },
  { code: 'SAN', city: 'San Diego', name: 'San Diego Intl' },
  { code: 'TPA', city: 'Tampa', name: 'Tampa Intl' },
  { code: 'PDX', city: 'Portland', name: 'Portland Intl' },
  { code: 'STL', city: 'St. Louis', name: 'Lambert Intl' },
  { code: 'LHR', city: 'London', name: 'Heathrow' },
  { code: 'CDG', city: 'Paris', name: 'Charles de Gaulle' },
  { code: 'CUN', city: 'Cancun', name: 'Cancun Intl' },
  { code: 'NRT', city: 'Tokyo', name: 'Narita Intl' },
  { code: 'GRU', city: 'São Paulo', name: 'Guarulhos Intl' },
]

interface FlightResult {
  id: string; price: number; currency: string; airline: string; airline_iata: string
  stops: number; origin: string; destination: string
  departing_at: string | null; arriving_at: string | null; duration: string
  segments: { origin: string; destination: string; departing_at: string; arriving_at: string; flight_number: string; airline: string }[]
}

function AirportInput({ label, value, onChange, exclude }: {
  label: string; value: string; onChange: (code: string) => void; exclude?: string
}) {
  const [query, setQuery] = useState(value)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ap = AIRPORTS.find(a => a.code === value)
    setQuery(ap ? `${ap.code} — ${ap.city}` : value)
  }, [value])

  useEffect(() => {
    const handler = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const matches = AIRPORTS.filter(a =>
    a.code !== exclude &&
    (a.code.includes(query.toUpperCase()) || a.city.toLowerCase().includes(query.toLowerCase()) || a.name.toLowerCase().includes(query.toLowerCase()))
  ).slice(0, 6)

  return (
    <div ref={ref} className="relative">
      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">{label}</label>
      <input
        value={query}
        onChange={e => { setQuery(e.target.value); setOpen(true) }}
        onFocus={() => { setQuery(''); setOpen(true) }}
        placeholder="City or airport"
        className="w-full text-lg font-semibold text-gray-900 bg-transparent border-0 border-b-2 border-gray-200 focus:border-blue-500 focus:outline-none pb-1 transition-colors"
      />
      {open && matches.length > 0 && (
        <div className="absolute top-full left-0 right-0 bg-white rounded-xl shadow-xl border border-gray-100 z-50 mt-1 overflow-hidden">
          {matches.map(a => (
            <button
              key={a.code}
              onMouseDown={() => { onChange(a.code); setQuery(`${a.code} — ${a.city}`); setOpen(false) }}
              className="w-full text-left px-4 py-3 hover:bg-blue-50 flex items-center gap-3 transition-colors"
            >
              <span className="font-bold text-blue-600 w-10 shrink-0">{a.code}</span>
              <div>
                <p className="text-sm font-medium text-gray-900">{a.city}</p>
                <p className="text-xs text-gray-400">{a.name}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function formatTime(dt: string | null) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })
}

function formatDuration(dur: string) {
  const match = dur.match(/PT(?:(\d+)H)?(?:(\d+)M)?/)
  if (!match) return dur
  const h = match[1] ? `${match[1]}h` : ''
  const m = match[2] ? ` ${match[2]}m` : ''
  return `${h}${m}`.trim()
}

const STOPS_LABELS: Record<number, string> = { 0: 'Nonstop', 1: '1 stop', 2: '2 stops' }

export default function SearchFlights() {
  const navigate = useNavigate()
  const [tripType, setTripType] = useState<'one-way' | 'round-trip'>('one-way')
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [date, setDate] = useState('')
  const [returnDate, setReturnDate] = useState('')
  const [adults, setAdults] = useState(1)
  const [cabinClass, setCabinClass] = useState('economy')
  const [stopsFilter, setStopsFilter] = useState<number | null>(null)
  const [results, setResults] = useState<FlightResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [watchingId, setWatchingId] = useState<string | null>(null)
  const [watchModal, setWatchModal] = useState<{ flight: FlightResult; budget: string } | null>(null)

  const swap = () => { const t = origin; setOrigin(destination); setDestination(t) }

  const handleSearch = async () => {
    if (!origin || !destination || !date) { toast.error('Fill in all required fields'); return }
    setLoading(true); setSearched(true); setResults([])
    try {
      const res = await searchFlights({
        origin, destination, date: date,
        adults, cabin_class: cabinClass,
        max_connections: stopsFilter ?? undefined,
      })
      setResults(res.data)
      if (res.data.length === 0) toast('No flights found — try different dates')
    } catch {
      toast.error('Search failed — please try again')
    } finally {
      setLoading(false)
    }
  }

  const confirmWatch = async () => {
    if (!watchModal) return
    const { flight, budget } = watchModal
    const target = parseFloat(budget)
    if (!budget || isNaN(target) || target <= 0) { toast.error('Enter a valid budget'); return }
    setWatchingId(flight.id)
    setWatchModal(null)
    try {
      await createRoute({
        origin: flight.origin,
        destination: flight.destination,
        date_from: date,
        date_to: date,
        target_price: target,
        booking_mode: 'A',
        max_connections: stopsFilter ?? undefined,
      } as any)
      const stopsLabel = stopsFilter === 0 ? 'nonstop ' : stopsFilter === 1 ? '1-stop ' : ''
      toast.success(`Watching ${stopsLabel}${flight.origin} → ${flight.destination} — you'll be notified when price drops below $${target}`)
      setTimeout(() => navigate('/routes'), 1500)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to set up watch')
    } finally {
      setWatchingId(null)
    }
  }

  const filtered = stopsFilter !== null
    ? results.filter(r => r.stops <= stopsFilter)
    : results

  const today = new Date().toISOString().split('T')[0]

  return (
    <div className="max-w-2xl mx-auto px-4 py-4">
      {/* Search card */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 mb-4">

        {/* Trip type + cabin */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex bg-gray-100 rounded-xl p-1 gap-1">
            {(['one-way', 'round-trip'] as const).map(t => (
              <button key={t} onClick={() => setTripType(t)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${tripType === t ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'}`}>
                {t === 'one-way' ? 'One way' : 'Round trip'}
              </button>
            ))}
          </div>
          <div className="relative">
            <select value={cabinClass} onChange={e => setCabinClass(e.target.value)}
              className="appearance-none bg-gray-100 text-gray-700 text-xs font-semibold pl-3 pr-7 py-2 rounded-xl focus:outline-none">
              <option value="economy">Economy</option>
              <option value="premium_economy">Premium Economy</option>
              <option value="business">Business</option>
              <option value="first">First</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-500 pointer-events-none" />
          </div>
        </div>

        {/* From / To */}
        <div className="flex items-end gap-2 mb-4">
          <div className="flex-1">
            <AirportInput label="From" value={origin} onChange={setOrigin} exclude={destination} />
          </div>
          <button onClick={swap} className="mb-1 p-2 rounded-full hover:bg-gray-100 transition-colors shrink-0">
            <ArrowLeftRight className="w-4 h-4 text-gray-400" />
          </button>
          <div className="flex-1">
            <AirportInput label="To" value={destination} onChange={setDestination} exclude={origin} />
          </div>
        </div>

        {/* Dates + pax */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
              {tripType === 'round-trip' ? 'Depart' : 'Date'}
            </label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)} min={today}
              className="w-full text-sm font-medium text-gray-900 border-b-2 border-gray-200 focus:border-blue-500 focus:outline-none pb-1 bg-transparent" />
          </div>
          {tripType === 'round-trip' ? (
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Return</label>
              <input type="date" value={returnDate} onChange={e => setReturnDate(e.target.value)} min={date || today}
                className="w-full text-sm font-medium text-gray-900 border-b-2 border-gray-200 focus:border-blue-500 focus:outline-none pb-1 bg-transparent" />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Passengers</label>
              <div className="flex items-center gap-3 border-b-2 border-gray-200 pb-1">
                <button onClick={() => setAdults(Math.max(1, adults - 1))} className="w-6 h-6 rounded-full bg-gray-100 text-gray-600 font-bold text-sm flex items-center justify-center">−</button>
                <span className="text-sm font-semibold text-gray-900 w-4 text-center">{adults}</span>
                <button onClick={() => setAdults(Math.min(9, adults + 1))} className="w-6 h-6 rounded-full bg-gray-100 text-gray-600 font-bold text-sm flex items-center justify-center">+</button>
                <span className="text-xs text-gray-400">adult{adults > 1 ? 's' : ''}</span>
              </div>
            </div>
          )}
        </div>

        {/* Stops filter */}
        <div className="flex gap-2 mb-4 flex-wrap">
          {[null, 0, 1].map(s => (
            <button key={String(s)} onClick={() => setStopsFilter(stopsFilter === s ? null : s)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${stopsFilter === s ? 'bg-blue-600 text-white border-blue-600' : 'text-gray-600 border-gray-200 hover:border-gray-300'}`}>
              {s === null ? 'Any stops' : s === 0 ? 'Nonstop' : '1 stop or fewer'}
            </button>
          ))}
        </div>

        <button onClick={handleSearch} disabled={loading}
          className="w-full bg-blue-600 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-blue-700 disabled:opacity-60 transition-colors">
          {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          {loading ? 'Searching…' : 'Search flights'}
        </button>
      </div>

      {/* Results */}
      {searched && !loading && filtered.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <Plane className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="font-medium">No flights found</p>
          <p className="text-sm mt-1">Try different dates or remove the stops filter</p>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500 font-medium px-1">{filtered.length} flight{filtered.length !== 1 ? 's' : ''} found</p>
          {filtered.map(f => (
            <div key={f.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <div className="p-4">
                {/* Airline + stops badge */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                      <span className="text-xs font-bold text-blue-600">{f.airline_iata}</span>
                    </div>
                    <span className="text-sm font-medium text-gray-700">{f.airline}</span>
                  </div>
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${f.stops === 0 ? 'bg-green-100 text-green-700' : f.stops === 1 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                    {STOPS_LABELS[f.stops] ?? `${f.stops} stops`}
                  </span>
                </div>

                {/* Times */}
                <div className="flex items-center gap-3">
                  <div className="text-center">
                    <p className="text-xl font-bold text-gray-900">{formatTime(f.departing_at)}</p>
                    <p className="text-xs text-gray-400 font-medium">{f.origin}</p>
                  </div>
                  <div className="flex-1 flex flex-col items-center gap-1">
                    <div className="flex items-center gap-1 w-full">
                      <div className="flex-1 h-px bg-gray-200" />
                      <Plane className="w-3.5 h-3.5 text-gray-300 rotate-90" />
                      <div className="flex-1 h-px bg-gray-200" />
                    </div>
                    {f.duration && (
                      <p className="text-xs text-gray-400 flex items-center gap-0.5">
                        <Clock className="w-3 h-3" />{formatDuration(f.duration)}
                      </p>
                    )}
                  </div>
                  <div className="text-center">
                    <p className="text-xl font-bold text-gray-900">{formatTime(f.arriving_at)}</p>
                    <p className="text-xs text-gray-400 font-medium">{f.destination}</p>
                  </div>
                </div>

                {/* Stops detail */}
                {f.stops > 0 && f.segments.length > 1 && (
                  <p className="text-xs text-gray-400 mt-2 text-center">
                    via {f.segments.slice(0, -1).map(s => s.destination).join(', ')}
                  </p>
                )}
              </div>

              {/* Price + CTA */}
              <div className="border-t border-gray-100 px-4 py-3 flex items-center justify-between bg-gray-50/50">
                <div>
                  <p className="text-2xl font-bold text-gray-900">${f.price.toFixed(0)}</p>
                  <p className="text-xs text-gray-400">per person</p>
                </div>
                <button
                  onClick={() => setWatchModal({ flight: f, budget: String(Math.floor(f.price * 0.95)) })}
                  disabled={watchingId === f.id}
                  className="flex items-center gap-2 bg-blue-600 text-white text-sm font-semibold px-4 py-2.5 rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-colors"
                >
                  {watchingId === f.id ? (
                    <><Loader className="w-3.5 h-3.5 animate-spin" />Setting up…</>
                  ) : (
                    <>Watch price</>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Budget modal */}
      {watchModal && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 px-4 pb-8"
          onClick={() => setWatchModal(null)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <h3 className="font-bold text-gray-900 text-lg mb-1">Set your budget</h3>
            <p className="text-sm text-gray-500 mb-1">
              {watchModal.flight.airline} · {watchModal.flight.origin} → {watchModal.flight.destination}
              {stopsFilter === 0 ? ' · Nonstop only' : stopsFilter === 1 ? ' · 1 stop or fewer' : ''}
            </p>
            <p className="text-xs text-gray-400 mb-4">
              Current price: <span className="font-semibold text-gray-700">${watchModal.flight.price.toFixed(0)}</span>
              {' — '}you'll get a push notification with the airline name when the price drops to your target.
            </p>
            <div className="relative mb-4">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 font-semibold">$</span>
              <input
                type="number"
                value={watchModal.budget}
                onChange={e => setWatchModal(m => m ? { ...m, budget: e.target.value } : null)}
                placeholder="e.g. 250"
                className="w-full pl-7 pr-4 py-3 border-2 border-gray-200 rounded-xl text-lg font-semibold focus:border-blue-500 focus:outline-none"
                autoFocus
              />
            </div>
            <div className="flex gap-3">
              <button onClick={() => setWatchModal(null)}
                className="flex-1 py-3 rounded-xl border border-gray-200 text-gray-600 font-semibold text-sm">
                Cancel
              </button>
              <button onClick={confirmWatch}
                className="flex-1 py-3 rounded-xl bg-blue-600 text-white font-semibold text-sm hover:bg-blue-700 transition-colors">
                Watch this price
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
